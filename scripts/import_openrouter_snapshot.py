#!/usr/bin/env python3
"""Import saved OpenRouter metadata and local operational evidence without network access."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SOURCE_URL = "https://openrouter.ai/api/v1/models"
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
ADMISSION_FLAGS = ("providerScopeApproved", "pricesComplete", "freeOnlyEnforced", "requestSucceeded", "toolsVerified")


def read_json(path):
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds the size limit")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Observation timestamps require nonblank ISO strings")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamps require a UTC offset")
    return parsed.astimezone(timezone.utc)


def evidence(value):
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
        return []
    return [x.strip() for x in value]


def capacity(value):
    return value if type(value) is int and value > 0 else 0


def zero_prices(prices):
    if not isinstance(prices, dict) or not {"prompt", "completion"} <= set(prices):
        return False
    for value in prices.values():
        if type(value) not in (str, int, float):
            return False
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            return False
        if not amount.is_finite() or amount != 0:
            return False
    return True


def load_repository_function(repository, relative_path, name):
    # Load only the inspected dependency-free scorer or ranking module. Package
    # __init__ and config discovery are bypassed for this offline entry point.
    path = repository / "src" / "llm_fallbacks" / relative_path
    spec = importlib.util.spec_from_file_location(f"offline_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def prepare_inputs(snapshot, catalog, local, observed_at, as_of):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("data"), list):
        raise ValueError("Snapshot must be an OpenRouter models response")
    rows = snapshot["data"]
    if len(rows) > MAX_ROWS or snapshot.get("links", {}).get("next"):
        raise ValueError("Snapshot is oversized or has an unconsumed next page")
    if "total_count" in snapshot and snapshot["total_count"] != len(rows):
        raise ValueError("Snapshot row count does not match total_count")
    if not isinstance(catalog, list) or len(catalog) > MAX_ROWS:
        raise ValueError("Canonical catalog must be a bounded array")
    if not isinstance(local, dict) or type(local.get("version")) is not int or local["version"] != 1:
        raise ValueError("Local evidence version must be 1")
    max_age = local.get("maxAgeHours", 24)
    if type(max_age) not in (int, float) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("maxAgeHours must be a positive finite number")

    def validate_time(value):
        age = (as_of - value).total_seconds() / 3600
        if age < 0 or age > max_age:
            raise ValueError("A source timestamp is outside the evaluation freshness window")

    validate_time(observed_at)
    account = local.get("account", {})
    if not isinstance(account, dict):
        raise ValueError("account must be an object")
    account_evidence = evidence(account.get("evidence"))
    account_time = timestamp(account["verifiedAt"]) if account.get("verifiedAt") else None
    if account_time:
        validate_time(account_time)
    account_verified = bool(account_evidence and account_time)
    if account.get("providerId", "openrouter") != "openrouter":
        raise ValueError("This importer accepts the exact OpenRouter provider ID")
    checks = local.get("modelChecks", [])
    if not isinstance(checks, list) or len(checks) > MAX_ROWS:
        raise ValueError("modelChecks must be a bounded array")
    check_index = {}
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("model"), str) or not check["model"].strip():
            raise ValueError("Model checks require exact nonblank model IDs")
        model_id = check["model"]
        if model_id in check_index:
            raise ValueError("Duplicate model check")
        if check.get("verifiedAt"):
            validate_time(timestamp(check["verifiedAt"]))
        check_index[model_id] = check
    return rows, account, account_evidence, account_time, account_verified, check_index


def build(snapshot, catalog, local, observed_at, snapshot_hash, repository, *, as_of):
    rows, account, account_evidence, account_time, account_verified, check_index = prepare_inputs(
        snapshot, catalog, local, observed_at, as_of
    )
    scorer = load_repository_function(repository, "quality.py", "compute_quality_score")
    ranker = load_repository_function(repository, "core.py", "get_model_priority_rank")
    fresh_rows = []
    targets = []
    dispositions = []
    seen = set()
    metadata_reference = f"{SOURCE_URL} snapshot sha256:{snapshot_hash} observed {observed_at.isoformat()}"
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError("Snapshot rows require exact model IDs")
        model_id = row["id"]
        if model_id in seen:
            raise ValueError("Duplicate snapshot model ID")
        seen.add(model_id)
        reasons = []
        prices = row.get("pricing")
        if not zero_prices(prices):
            reasons.append("not-explicit-zero-prices")
        architecture = row.get("architecture", {})
        if not isinstance(architecture, dict):
            architecture = {}
        inputs = architecture.get("input_modalities", [])
        outputs = architecture.get("output_modalities", [])
        if outputs != ["text"] or not isinstance(inputs, list) or "text" not in inputs:
            reasons.append("chat-endpoint-shape-unmapped")
        if model_id in ("openrouter/free", "openrouter/auto"):
            reasons.append("dynamic-router-policy-unbounded")
        dispositions.append({"model": model_id, "excluded": reasons})
        if reasons:
            continue
        params = row.get("supported_parameters", [])
        if not isinstance(params, list) or not all(isinstance(x, str) for x in params):
            raise ValueError("supported_parameters must be a string array")
        top = row.get("top_provider", {})
        if not isinstance(top, dict):
            top = {}
        context = capacity(top.get("context_length")) or capacity(row.get("context_length"))
        output = capacity(top.get("max_completion_tokens"))
        spec = {
            "max_input_tokens": context,
            "max_output_tokens": output,
            "supports_function_calling": "tools" in params,
            "supports_tool_choice": "tool_choice" in params,
            "supports_vision": "image" in inputs,
            "supports_audio_input": "audio" in inputs,
            "supports_response_schema": "structured_outputs" in params,
            "supports_prompt_caching": "cache_control" in params,
        }
        score, source = scorer(spec)
        canonical = {
            "id": model_id,
            "provider": "openrouter",
            "mode": "chat",
            "is_free": True,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "context_length": context,
            "max_output_tokens": output,
            "quality_score": score,
            "quality_source": source,
            "pricing_evidence": {"source": metadata_reference, "requires_live_verification": True},
        }
        for field in (
            "supports_function_calling",
            "supports_tool_choice",
            "supports_vision",
            "supports_audio_input",
            "supports_response_schema",
            "supports_prompt_caching",
            "supports_audio_output",
            "supports_pdf_input",
            "supports_system_messages",
        ):
            canonical[field] = spec.get(field, False)
        fresh_rows.append(canonical)
        check = check_index.get(model_id, {})
        check_evidence = evidence(check.get("evidence"))
        check_time = timestamp(check["verifiedAt"]) if check.get("verifiedAt") else None
        check_verified = bool(check_evidence and check_time)
        times = [observed_at] + ([account_time] if account_time else []) + ([check_time] if check_time else [])
        target = {
            "catalogProvider": "openrouter",
            "catalogId": model_id,
            "providerId": "openrouter",
            "model": model_id,
            "connected": account_verified and account.get("connected") is True,
            "prices": dict.fromkeys(prices, 0),
            "verifiedAt": min(times).isoformat(),
            "evidence": [metadata_reference, *account_evidence, *check_evidence],
            "privacy": check.get("privacy", "unknown") if check_verified else "unknown",
            "purposes": check.get("purposes", ["text"]) if check_verified else ["text"],
            "purposeEvidence": check.get("purposeEvidence", {}) if check_verified else {},
            "endpoints": check.get("endpoints", []) if check_verified else [],
            "quotaGroup": "openrouter-shared-free-account",
        }
        for flag in ADMISSION_FLAGS:
            target[flag] = check_verified and check.get(flag) is True
        target["providerScopeApproved"] = account_verified and account.get("providerScopeApproved") is True
        if type(check.get("priority")) in (int, float) and math.isfinite(check["priority"]):
            target["priority"] = check["priority"]
        targets.append(target)
    merged = [row for row in catalog if row.get("provider") != "openrouter"] + fresh_rows
    merged.sort(key=lambda row: (ranker(row["id"]), -row.get("quality_score", 0), row["id"], row["provider"]))
    access = {
        "version": 1,
        "maxAgeHours": local.get("maxAgeHours", 24),
        "maxGlobalAttempts": local.get("maxGlobalAttempts", 200),
        "comboTimeoutMs": local.get("comboTimeoutMs", 600_000),
        "comboEndpoints": local.get("comboEndpoints", []),
        "targets": targets,
    }
    report = {
        "source": SOURCE_URL,
        "observedAt": observed_at.isoformat(),
        "evaluatedAt": as_of.isoformat(),
        "snapshotSha256": snapshot_hash,
        "snapshotRows": len(rows),
        "importedChatCandidates": len(fresh_rows),
        "accountEvidencePresent": account_verified,
        "modelChecksProvided": len(check_index),
        "unmatchedModelChecks": sorted(set(check_index) - {r["id"] for r in fresh_rows}),
        "dispositions": dispositions,
    }
    return merged, access, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--as-of", required=True, help="Explicit evaluation time for every evidence source")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    # Enforce the offline CLI contract even if a repository helper changes.

    def deny_network(event, _args):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            raise RuntimeError("Network access is disabled for this importer")

    sys.addaudithook(deny_network)
    snapshot, snapshot_hash = read_json(args.models)
    catalog, catalog_hash = read_json(args.catalog)
    local, evidence_hash = read_json(args.evidence)
    merged, access, report = build(
        snapshot,
        catalog,
        local,
        timestamp(args.observed_at),
        snapshot_hash,
        args.repository,
        as_of=timestamp(args.as_of),
    )
    report["inputSha256"] = {"canonicalCatalog": catalog_hash, "localEvidence": evidence_hash}
    report["repositoryHelpersSha256"] = {
        name: hashlib.sha256((args.repository / "src" / "llm_fallbacks" / name).read_bytes()).hexdigest()
        for name in ("quality.py", "core.py")
    }
    encoded = [
        (name, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        for name, value in (
            ("catalog.candidate.json", merged),
            ("access.draft.json", access),
            ("import-report.json", report),
        )
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in encoded:
        (args.output_dir / name).write_text(content)
    print(f"Imported {len(access['targets'])} chat candidates from {report['snapshotRows']} snapshot rows")


if __name__ == "__main__":
    main()
