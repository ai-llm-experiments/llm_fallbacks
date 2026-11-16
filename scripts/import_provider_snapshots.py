#!/usr/bin/env python3
"""Build offline multi-provider catalogs and review-only OmniRoute proposals."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
FLAGS = ("pricesComplete", "freeOnlyEnforced", "requestSucceeded", "toolsVerified")
CHECK_KEYS = {
    "provider",
    "model",
    "verifiedAt",
    "evidence",
    "privacy",
    "purposes",
    "purposeEvidence",
    "endpoints",
    "priority",
    "quotaGroup",
    "routeName",
    "embeddingSpace",
    "mode",
    "modeEvidence",
    "verifiedPricing",
    *FLAGS,
}


def strict_object(value, allowed, label):
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"{label} has unsupported fields or is not an object")
    return value


def references(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def exact(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 500:
        raise ValueError("Exact nonblank identity required")
    return value


def moment(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp must be a nonblank ISO string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp requires a UTC offset")
    return result.astimezone(timezone.utc)


def read_json(path, *, decoder=json.loads):
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds 16 MiB")
    return decoder(raw), hashlib.sha256(raw).hexdigest()


def encoded(value):
    """Exact artifact bytes used for both serialization and provenance hashes."""
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def validate_references(value, label):
    if not references(value):
        raise ValueError(f"{label} must contain nonblank string receipt references")


def load_module(repository, name):
    path = repository / "src" / "llm_fallbacks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"offline_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_entry(provider, path, providers, cache, *, expected_folder=None):
    """Freeze saved bytes and parse each provider/path/folder scope independently."""
    if provider == "yandex":
        expected_folder = exact(expected_folder)
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char in "/?#@:%\\" for char in expected_folder):
            raise ValueError("Yandex snapshots require an exact expected folder ID")
    elif expected_folder is not None:
        raise ValueError("Expected folder scope applies only to Yandex snapshots")
    identity = str(path.resolve())
    raw_cache = cache.setdefault("raw", {})
    parsed_cache = cache.setdefault("parsed", {})
    if identity not in raw_cache:
        decoder = getattr(providers, "decode_provider_snapshot", None)
        if not callable(decoder):
            raise ValueError("Provider parser must supply an exact snapshot number decoder")
        raw_cache[identity] = read_json(path, decoder=decoder)
    raw, digest = raw_cache[identity]
    key = (provider, identity, expected_folder)
    if key not in parsed_cache:
        if isinstance(raw, dict) and providers.PROVIDER_CATALOGS[provider]["schema"] == "openai":
            for row in raw.get("data", []) if isinstance(raw.get("data"), list) else []:
                if (
                    isinstance(row, dict)
                    and "pricing" in row
                    and row["pricing"] is not None
                    and not isinstance(row["pricing"], dict)
                ):
                    raise ValueError("Current provider pricing must be an object or explicit null")
        parse_options = {"qualify_ids": False}
        if expected_folder is not None:
            parse_options["expected_folder"] = expected_folder
        parsed_cache[key] = providers.parse_provider_models(provider, raw, **parse_options)
    return digest, parsed_cache[key]


def index_accounts(account_rows, providers, fresh):
    accounts = {}
    for account in account_rows:
        strict_object(account, {"provider", "connected", "providerScopeApproved", "verifiedAt", "evidence"}, "account")
        provider = exact(account.get("provider"))
        if provider not in providers.PROVIDER_CATALOGS or provider in accounts:
            raise ValueError("Unsupported or duplicate account provider")
        if "evidence" in account:
            validate_references(account["evidence"], "account evidence")
        for flag in ("connected", "providerScopeApproved"):
            if flag in account and type(account[flag]) is not bool:
                raise ValueError("Account flags must be booleans")
        if account.get("verifiedAt") is not None:
            fresh(account["verifiedAt"])
        accounts[provider] = account
    return accounts


def index_model_checks(checks, providers, routing, fresh):
    check_index = {}
    for check in checks:
        strict_object(check, CHECK_KEYS, "model check")
        identity = (exact(check.get("provider")), exact(check.get("model")))
        if identity[0] not in providers.PROVIDER_CATALOGS or identity in check_index:
            raise ValueError("Unsupported or duplicate model identity")
        for field in ("evidence", "modeEvidence"):
            if field in check:
                validate_references(check[field], field)
        for flag in FLAGS:
            if flag in check and type(check[flag]) is not bool:
                raise ValueError("Model flags must be booleans")
        if "privacy" in check and check["privacy"] not in ("unknown", "private-approved", "public-demo"):
            raise ValueError("Unknown privacy classification")
        for field in ("purposes", "endpoints"):
            values = check.get(field, [])
            if not isinstance(values, list) or not all(isinstance(x, str) and x.strip() for x in values):
                raise ValueError("Purpose and endpoint lists must contain strings")
        if any(value not in routing.ROUTES for value in check.get("purposes", [])):
            raise ValueError("Unsupported route purpose")
        purpose_evidence = check.get("purposeEvidence", {})
        strict_object(purpose_evidence, set(routing.ROUTES), "purpose evidence")
        if not all(isinstance(value, str) and value.strip() for value in purpose_evidence.values()):
            raise ValueError("Purpose evidence values must be nonblank receipt strings")
        if "embeddingSpace" in check:
            space = strict_object(check["embeddingSpace"], {"identity", "dimensions", "evidence"}, "embedding space")
            exact(space.get("identity"))
            if type(space.get("dimensions")) is not int or space["dimensions"] < 1:
                raise ValueError("Embedding dimensions must be a positive integer")
            validate_references(space.get("evidence"), "embedding evidence")
        for field in ("quotaGroup", "routeName"):
            if field in check:
                exact(check[field])
        if "priority" in check and (
            type(check["priority"]) not in (int, float) or not math.isfinite(check["priority"])
        ):
            raise ValueError("Priority must be a finite number")
        if "mode" in check and (not isinstance(check["mode"], str) or check["mode"] not in providers.MODES):
            raise ValueError("Unsupported model mode")
        if check.get("verifiedAt") is not None:
            fresh(check["verifiedAt"])
        proof = check.get("verifiedPricing")
        if proof is not None:
            strict_object(proof, {"prices", "verifiedAt", "evidence"}, "pricing proof")
            fresh(proof.get("verifiedAt"))
            validate_references(proof.get("evidence"), "pricing evidence")
            if not isinstance(proof.get("prices"), dict) or not proof["prices"]:
                raise ValueError("Pricing must be a nonempty object")
            if any(key not in providers.PRICE_FIELDS for key in proof["prices"]):
                raise ValueError("Unsupported local pricing dimension")
        check_index[identity] = check

    return check_index


def prepare_model_spec(provider, model, original, check, account, observed, providers, fresh, metadata_ref):
    account_ok = references(account.get("evidence")) and account.get("verifiedAt") is not None
    spec = dict(original)
    check_ok = references(check.get("evidence")) and check.get("verifiedAt") is not None
    times = [observed]
    if account_ok:
        times.append(fresh(account["verifiedAt"]))
    if check_ok:
        times.append(fresh(check["verifiedAt"]))
    provenance = [metadata_ref]
    if account_ok:
        provenance += account["evidence"]
    if check_ok:
        provenance += check["evidence"]
    if spec.get("mode", "unknown") == "unknown" and check_ok and references(check.get("modeEvidence")):
        spec["mode"] = check.get("mode", "unknown")
        provenance += check["modeEvidence"]
    proof = check.get("verifiedPricing")
    reported = spec.get("pricing_evidence", {}).get("reported_prices")
    if proof is not None and reported is None and check_ok and references(proof.get("evidence")):
        # Current declared positive/partial provider prices are never overridden.
        row = {"id": model, "mode": spec.get("mode"), "pricing": proof.get("prices")}
        local_prices = providers.parse_openai_models(provider, {"data": [row]}, qualify_ids=False)[model]
        spec.update(local_prices)
        provenance += proof["evidence"]
        times.append(fresh(proof["verifiedAt"]))
        spec["pricing_evidence"]["origin"] = "local-pricing-attestation"
    return spec, check_ok, times, provenance


def build_unmapped(manifest, evidence, repository, as_of, *, snapshot_cache=None):
    strict_object(manifest, {"version", "snapshots"}, "manifest")
    strict_object(
        evidence,
        {"version", "maxAgeHours", "accounts", "modelChecks", "comboEndpoints", "maxGlobalAttempts", "comboTimeoutMs"},
        "evidence",
    )
    if (
        type(manifest.get("version")) is not int
        or manifest["version"] != 1
        or type(evidence.get("version")) is not int
        or evidence["version"] != 1
    ):
        raise ValueError("Input version must be 1")
    max_age = evidence.get("maxAgeHours", 24)
    if type(max_age) not in (int, float) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("maxAgeHours must be positive and finite")

    def fresh(value):
        parsed = moment(value)
        hours = (as_of - parsed).total_seconds() / 3600
        if not 0 <= hours <= max_age:
            raise ValueError("Every supplied timestamp must independently be fresh and nonfuture")
        return parsed

    if snapshot_cache is None:
        snapshot_cache = {}
    providers = load_module(repository, "provider_catalogs")
    pricing = load_module(repository, "pricing")
    quality = load_module(repository, "quality")
    routing = load_module(repository, "omniroute")
    accounts = {}
    account_rows = evidence.get("accounts", [])
    checks = evidence.get("modelChecks", [])
    snapshots = manifest.get("snapshots")
    for rows in (account_rows, checks, snapshots):
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError("Input arrays must be bounded")
    accounts = index_accounts(account_rows, providers, fresh)
    check_index = index_model_checks(checks, providers, routing, fresh)

    catalog, targets, dispositions, sources = [], [], [], []
    seen_providers = set()
    for snapshot in snapshots:
        strict_object(snapshot, {"provider", "path", "observedAt", "expectedFolder"}, "snapshot")
        provider = exact(snapshot.get("provider"))
        if provider not in providers.PROVIDER_CATALOGS or provider in seen_providers:
            raise ValueError("Exactly one complete snapshot per known provider is required")
        seen_providers.add(provider)
        observed = fresh(snapshot.get("observedAt"))
        path = Path(exact(snapshot.get("path")))
        expected_folder = snapshot.get("expectedFolder")
        digest, parsed = snapshot_entry(provider, path, providers, snapshot_cache, expected_folder=expected_folder)
        sources.append(
            {
                "provider": provider,
                "snapshotSha256": digest,
                "observedAt": observed.isoformat(),
                "source": providers.PROVIDER_CATALOGS[provider]["models_url"],
                "rows": len(parsed),
            }
        )
        metadata_ref = f"{provider} catalog sha256={digest} observed={observed.isoformat()}"
        if expected_folder is not None:
            sources[-1]["expectedFolder"] = expected_folder
            metadata_ref += f" expected-folder={expected_folder}"
        account = accounts.get(provider, {})
        account_ok = references(account.get("evidence")) and account.get("verifiedAt") is not None
        for model, original in sorted(parsed.items()):
            check = check_index.get((provider, model), {})
            spec, check_ok, times, provenance = prepare_model_spec(
                provider, model, original, check, account, observed, providers, fresh, metadata_ref
            )
            reasons = []
            if not pricing.has_explicit_zero_cost(spec):
                reasons.append("complete-explicit-zero-pricing-unverified")
            if not routing.is_exact_target(model):
                reasons.append("model-target-syntax-not-exact")
            if routing.is_dynamic_router(provider, model):
                reasons.append("dynamic-router-policy-unbounded")
            dispositions.append({"provider": provider, "model": model, "excluded": reasons})
            if reasons:
                continue
            score, score_source = quality.compute_quality_score(spec)
            canonical = dict(spec)
            canonical.update(
                {
                    "id": model,
                    "provider": provider,
                    "is_free": True,
                    "input_cost_per_token": spec.get("input_cost_per_token"),
                    "output_cost_per_token": spec.get("output_cost_per_token"),
                    "context_length": spec.get("max_input_tokens", 0),
                    "quality_score": score,
                    "quality_source": score_source,
                }
            )
            # The existing route adapter requires two token dimensions even for
            # embeddings. Retain null when absent so it stays fail-closed.
            catalog.append(canonical)
            target = {
                "catalogProvider": provider,
                "catalogId": model,
                "providerId": provider,
                "model": model,
                "connected": account_ok and account.get("connected") is True,
                "providerScopeApproved": account_ok and account.get("providerScopeApproved") is True,
                "verifiedAt": min(times).isoformat(),
                "evidence": provenance,
                "prices": spec.get("pricing_evidence", {}).get("reported_prices") or {},
                "privacy": check.get("privacy", "unknown") if check_ok else "unknown",
                "purposes": check.get("purposes", []) if check_ok else [],
                "endpoints": check.get("endpoints", []) if check_ok else [],
                "purposeEvidence": check.get("purposeEvidence", {}) if check_ok else {},
                "quotaGroup": check.get("quotaGroup", f"{provider}-shared-account"),
            }
            # Route adapter uses numeric zero values. Preserve strings in source
            # evidence, translating only already verified exact-zero prices.
            target["prices"] = dict.fromkeys(target["prices"], 0)
            for flag in FLAGS:
                target[flag] = check_ok and check.get(flag) is True
            for field in ("priority", "embeddingSpace", "routeName"):
                if check_ok and field in check:
                    target[field] = check[field]
            targets.append(target)
    catalog.sort(key=lambda row: (-row["quality_score"], row["provider"], row["id"]))
    targets.sort(key=lambda row: (row["providerId"], row["model"]))
    if len(catalog) > MAX_ROWS or len(targets) > MAX_ROWS:
        raise ValueError("Combined catalog exceeds route adapter bound")
    access = {
        "version": 1,
        "maxAgeHours": max_age,
        "targets": targets,
        "comboEndpoints": evidence.get("comboEndpoints", []),
        "maxGlobalAttempts": evidence.get("maxGlobalAttempts", 200),
        "comboTimeoutMs": evidence.get("comboTimeoutMs", 600000),
    }
    proposal = routing.generate(
        catalog,
        access,
        as_of,
        hashlib.sha256(encoded(catalog)).hexdigest(),
        hashlib.sha256(encoded(access)).hexdigest(),
    )
    report = {
        "asOf": as_of.isoformat(),
        "sources": sorted(sources, key=lambda x: x["provider"]),
        "ranking": "canonical quality heuristic descending, provider, exact model ID",
        "dispositions": sorted(dispositions, key=lambda x: (x["provider"], x["model"])),
        "unmatchedChecks": [
            {"provider": p, "model": m}
            for p, m in sorted(set(check_index) - {(x["provider"], x["model"]) for x in dispositions})
        ],
    }
    return catalog, access, proposal, report


def runtime_indexes(mappings, accounts, checks, providers, fresh):
    bindings = {}
    node_owners = {}
    for mapping in mappings:
        strict_object(mapping, {"provider", "providerId", "quotaGroup", "verifiedAt", "evidence"}, "runtime mapping")
        provider, node = exact(mapping.get("provider")), exact(mapping.get("providerId"))
        if provider not in providers.PROVIDER_CATALOGS:
            raise ValueError("Unknown canonical provider")
        identity = (provider, node)
        if identity in bindings or (node in node_owners and node_owners[node] != provider):
            raise ValueError("Duplicate or conflicting runtime mapping")
        if node in providers.PROVIDER_CATALOGS and node != provider:
            raise ValueError("Runtime identity collides with a different canonical provider")
        exact(mapping.get("quotaGroup"))
        validate_references(mapping.get("evidence"), "mapping evidence")
        fresh(mapping.get("verifiedAt"))
        bindings[identity] = mapping
        node_owners[node] = provider
    grouped_accounts, grouped_checks = {}, {}
    for account in accounts:
        strict_object(
            account,
            {"provider", "providerId", "connected", "providerScopeApproved", "verifiedAt", "evidence"},
            "account",
        )
        provider = exact(account.get("provider"))
        node = exact(account.get("providerId", provider))
        identity = (provider, node)
        if identity in grouped_accounts:
            raise ValueError("Duplicate runtime account scope")
        grouped_accounts[identity] = {key: value for key, value in account.items() if key != "providerId"}
    seen_checks = set()
    for check in checks:
        strict_object(check, CHECK_KEYS | {"providerId"}, "model check")
        provider = exact(check.get("provider"))
        node = exact(check.get("providerId", provider))
        model = exact(check.get("model"))
        identity = (provider, node)
        if (provider, node, model) in seen_checks:
            raise ValueError("Duplicate runtime model check")
        seen_checks.add((provider, node, model))
        mapping = bindings.get(identity)
        if mapping and "quotaGroup" in check and check["quotaGroup"] != mapping["quotaGroup"]:
            raise ValueError("Model quota group contradicts mapped account quota")
        grouped_checks.setdefault(identity, []).append(
            {key: value for key, value in check.items() if key != "providerId"}
        )
    groups = set(bindings) | set(grouped_accounts) | set(grouped_checks)
    return bindings, groups, grouped_accounts, grouped_checks


def prepare_snapshots(manifest, providers, fresh, groups, bindings):
    strict_object(manifest, {"version", "snapshots"}, "manifest")
    if type(manifest.get("version")) is not int or manifest["version"] != 1:
        raise ValueError("Manifest version must be 1")
    snapshot_rows = manifest.get("snapshots")
    if not isinstance(snapshot_rows, list) or len(snapshot_rows) > MAX_ROWS:
        raise ValueError("Snapshots must be a bounded array")
    snapshot_providers = set()
    snapshot_cache = {}
    provider_sizes = {}
    for row in snapshot_rows:
        strict_object(row, {"provider", "path", "observedAt", "expectedFolder"}, "snapshot")
        provider = exact(row.get("provider"))
        if provider in snapshot_providers:
            raise ValueError("Duplicate snapshot provider")
        if provider not in providers.PROVIDER_CATALOGS:
            raise ValueError("Unknown snapshot provider")
        fresh(row.get("observedAt"))
        _, parsed = snapshot_entry(
            provider, Path(exact(row.get("path"))), providers, snapshot_cache, expected_folder=row.get("expectedFolder")
        )
        provider_sizes[provider] = len(parsed)
        snapshot_providers.add(provider)
        if not any(group[0] == provider for group in groups):
            groups.add((provider, provider))
    for provider, node in groups:
        if provider not in providers.PROVIDER_CATALOGS or provider not in snapshot_providers:
            raise ValueError("Runtime evidence requires a saved canonical provider snapshot")
        if node != provider and (provider, node) not in bindings:
            raise ValueError("Alternate runtime ID requires an explicit evidenced mapping")
    if len(groups) > MAX_ROWS:
        raise ValueError("Combined runtime binding count exceeds bound")
    return snapshot_rows, snapshot_cache, provider_sizes


def build(manifest, evidence, repository, as_of):
    """Bind independently evidenced runtime nodes to canonical provider catalogs."""
    strict_object(
        evidence,
        {
            "version",
            "maxAgeHours",
            "accounts",
            "modelChecks",
            "comboEndpoints",
            "maxGlobalAttempts",
            "comboTimeoutMs",
            "runtimeMappings",
        },
        "evidence",
    )
    max_age = evidence.get("maxAgeHours", 24)
    if type(max_age) not in (int, float) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("maxAgeHours must be positive and finite")
    providers = load_module(repository, "provider_catalogs")
    routing = load_module(repository, "omniroute")

    def fresh(value):
        observed = moment(value)
        age = (as_of - observed).total_seconds() / 3600
        if not 0 <= age <= max_age:
            raise ValueError("Mapping evidence must independently be fresh and nonfuture")
        return observed

    if type(evidence.get("version")) is not int or evidence["version"] != 1:
        raise ValueError("Evidence version must be 1")
    mappings = evidence.get("runtimeMappings", [])
    accounts = evidence.get("accounts", [])
    checks = evidence.get("modelChecks", [])
    if any(not isinstance(rows, list) or len(rows) > MAX_ROWS for rows in (mappings, accounts, checks)):
        raise ValueError("Runtime inputs must be bounded arrays")
    bindings, groups, grouped_accounts, grouped_checks = runtime_indexes(mappings, accounts, checks, providers, fresh)
    # A canonical snapshot alone remains a candidate with blocked admission.
    snapshot_rows, snapshot_cache, provider_sizes = prepare_snapshots(manifest, providers, fresh, groups, bindings)
    rows_by_identity, targets, reports = {}, [], []
    expanded_rows = 0
    base = {key: value for key, value in evidence.items() if key not in ("runtimeMappings", "accounts", "modelChecks")}
    policy_mappings = []
    for provider, node in sorted(groups):
        expanded_rows += provider_sizes[provider]
        if expanded_rows > MAX_ROWS:
            raise ValueError("Snapshot rows expanded across runtime bindings exceed bound")
        local = dict(base)
        local["accounts"] = [grouped_accounts[provider, node]] if (provider, node) in grouped_accounts else []
        local["modelChecks"] = grouped_checks.get((provider, node), [])
        selected = {
            "version": manifest.get("version"),
            "snapshots": [row for row in snapshot_rows if row["provider"] == provider],
        }
        catalog, access, _, report = build_unmapped(selected, local, repository, as_of, snapshot_cache=snapshot_cache)
        mapping = bindings.get((provider, node))
        if mapping:
            policy_mappings.append({"catalogProvider": provider, "providerId": node, "evidence": mapping["evidence"]})
        if len(targets) + len(access["targets"]) > MAX_ROWS:
            raise ValueError("Combined runtime target count exceeds bound")
        for row in catalog:
            identity = (row["provider"], row["id"])
            if identity not in rows_by_identity and len(rows_by_identity) >= MAX_ROWS:
                raise ValueError("Combined catalog count exceeds bound")
            previous = rows_by_identity.setdefault(identity, row)
            if previous != row:
                raise ValueError("Conflicting canonical metadata across runtime nodes")
        for target in access["targets"]:
            target["providerId"] = node
            if mapping:
                target["quotaGroup"] = mapping["quotaGroup"]
                target["evidence"] += mapping["evidence"]
                target["verifiedAt"] = min(moment(target["verifiedAt"]), fresh(mapping["verifiedAt"])).isoformat()
            targets.append(target)
        reports.append(
            {"provider": provider, "providerId": node, "mappingEvidencePresent": mapping is not None, "import": report}
        )
    catalog = sorted(rows_by_identity.values(), key=lambda row: (-row["quality_score"], row["provider"], row["id"]))
    targets.sort(key=lambda target: (target["providerId"], target["model"]))
    if len(catalog) > MAX_ROWS or len(targets) > MAX_ROWS:
        raise ValueError("Combined runtime candidates exceed adapter bounds")
    policy = {key: value for key, value in base.items() if key not in ("version",)}
    policy.update({"version": 1, "targets": targets, "providerMappings": policy_mappings})
    proposal = routing.generate(
        catalog,
        policy,
        as_of,
        hashlib.sha256(encoded(catalog)).hexdigest(),
        hashlib.sha256(encoded(policy)).hexdigest(),
    )
    return (
        catalog,
        policy,
        proposal,
        {
            "asOf": as_of.isoformat(),
            "runtimeImports": reports,
            "sources": [source for report in reports for source in report["import"]["sources"]],
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    def deny_network(event, _args):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            raise RuntimeError("Offline snapshot pipeline denies network access")

    sys.addaudithook(deny_network)
    manifest, manifest_hash = read_json(args.manifest)
    evidence, evidence_hash = read_json(args.evidence)
    catalog, access, proposal, report = build(manifest, evidence, args.repository, moment(args.as_of))
    report["inputsSha256"] = {"manifest": manifest_hash, "evidence": evidence_hash}
    report["helpersSha256"] = {
        name: hashlib.sha256((args.repository / "src/llm_fallbacks" / f"{name}.py").read_bytes()).hexdigest()
        for name in ("provider_catalogs", "pricing", "quality", "omniroute")
    }
    artifacts = dict(
        zip(
            ("catalog.candidate.json", "access.draft.json", "proposal.json", "import-report.json"),
            (catalog, access, proposal, report),
            strict=True,
        )
    )
    serialized = {name: encoded(value) for name, value in artifacts.items()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in serialized.items():
        (args.output_dir / name).write_bytes(content)
    print(
        f"Providers {len({source['provider'] for source in report['sources']})}; "
        f"candidates {len(catalog)}; proposed combos {len(proposal['proposedCombos'])}"
    )


if __name__ == "__main__":
    main()
