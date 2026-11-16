#!/usr/bin/env python3
"""Diff reviewed OmniRoute proposals into offline, reversible reconciliation plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
CONFIG_KEYS = {"disableSessionStickiness", "maxGlobalAttempts", "comboTimeoutMs", "maxRetries", "maxSetRetries"}
COMBO_KEYS = {
    "id",
    "name",
    "description",
    "strategy",
    "config",
    "models",
    "allowedProviders",
    "allowedModelFamilies",
    "invariant",
    "version",
    "isActive",
    "isHidden",
    "dimensions",
}
PAYLOAD_KEYS = {"name", "description", "strategy", "config", "models", "dimensions"}
STEP_KEYS = {
    "id",
    "kind",
    "providerId",
    "model",
    "weight",
    "label",
    "connectionId",
    "allowedConnectionIds",
    "tags",
    "prompt",
    "fallbackOnlyOnQuotaExhaustion",
    "comboName",
    "modelPattern",
}
SECRET_KEY = re.compile(
    r"^(?:[a-z0-9]*(?:apikey|privatekey|secretkey|secretaccesskey|accesskeyid|password|secret|token)"
    r"|auth|authorization|proxyauthorization|credentials?|cookies?|setcookie|bearer|sessionkey)$",
    re.IGNORECASE,
)
CONFIG_BOUNDS = {
    "maxGlobalAttempts": (1, 200),
    "maxRetries": (0, 10),
    "maxSetRetries": (0, 10),
    "comboTimeoutMs": (0, 2147483647),
}


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def read_json(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds size bound")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def obj(value, keys, label):
    if not isinstance(value, dict) or set(value) - keys:
        raise ValueError(f"Unsupported {label} fields")


def text(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 2000:
        raise ValueError("Exact nonblank string required")
    return value


def refs(value):
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError("Nonblank evidence references required")


def strings(value):
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError("String array required")
    if len(value) != len(set(value)):
        raise ValueError("Duplicate string identity")
    return value


def sanitized(value, depth=0):
    if depth > 30:
        raise ValueError("Nested input exceeds depth bound")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or SECRET_KEY.search(re.sub(r"[^a-z0-9]", "", key.casefold())):
                raise ValueError("Credential-shaped field in sanitized input")
            sanitized(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            sanitized(item, depth + 1)
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")


def route_name(value):
    text(value)
    if len(value) > 100 or re.fullmatch(r"[a-zA-Z0-9_/.\-\[\] ]+", value) is None:
        raise ValueError("Route name exceeds native API format or length")
    return value


def dimensions(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value) is None or not value.strip("0"):
        raise ValueError("Dimensions must be a positive integer string")


def config_values(config):
    for field, value in config.items():
        if field == "disableSessionStickiness" and type(value) is not bool:
            raise ValueError("Stickiness setting must be boolean")
        if field in CONFIG_BOUNDS:
            lower, upper = CONFIG_BOUNDS[field]
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("Managed setting exceeds native API bounds")


def model_identity(step):
    if not isinstance(step, dict) or step.get("kind") != "model":
        return None
    provider, model = step.get("providerId"), step.get("model")
    if not isinstance(provider, str) or not provider or not isinstance(model, str) or not model:
        return None
    # Matches inspected OmniRoute toFullModelString. Vendor/model IDs already
    # containing a slash retain their exact spelling.
    return provider, model if "/" in model else f"{provider}/{model}"


def simple_models(models, desired=False):
    if not isinstance(models, list) or not models or len(models) > MAX_ROWS:
        raise ValueError("Models must be a nonempty bounded array")
    for step in models:
        if isinstance(step, str) and not desired:
            text(step)
            continue
        obj(step, {"kind", "providerId", "model"} if desired else STEP_KEYS, "model step")
        if desired:
            if model_identity(step) is None:
                raise ValueError("Proposals require exact model steps")
            text(step["providerId"])
            text(step["model"])
            if len(step["providerId"]) > 120 or len(step["model"]) > 300:
                raise ValueError("Model/provider identity exceeds native API bounds")
            if any(character in step["model"] for character in ("*", "?")) or "/" in step["providerId"]:
                raise ValueError("Exact targets cannot contain wildcard or provider-scoping syntax")


def guarded_models(models):
    for step in models:
        if model_identity(step) is None:
            return True
        for key, value in step.items():
            if key in ("id", "kind", "providerId", "model", "label"):
                continue
            if key == "weight" and type(value) in (int, float) and value == 0:
                continue
            if key in ("connectionId", "prompt") and value in (None, ""):
                continue
            if key in ("tags", "allowedConnectionIds") and value in (None, []):
                continue
            if key == "fallbackOnlyOnQuotaExhaustion" and value is False:
                continue
            return True
    return False


def index_current_combos(rows):
    by_id, by_name = {}, {}
    for row in rows:
        obj(row, COMBO_KEYS, "combo export")
        identity, name = text(row.get("id")), route_name(row.get("name"))
        if identity in by_id or name in by_name:
            raise ValueError("Duplicate current combo ID or name")
        text(row.get("strategy"))
        simple_models(row.get("models"))
        if not isinstance(row.get("config"), dict):
            raise ValueError("Export requires complete config object")
        config_values(row["config"])
        if row.get("dimensions") is not None:
            dimensions(row["dimensions"])
        if row.get("allowedProviders") is not None:
            strings(row["allowedProviders"])
        by_id[identity], by_name[name] = row, identity
    return by_id, by_name


def index_proposals(desired):
    proposals = {}
    for item in desired:
        if not isinstance(item, dict):
            raise ValueError("Proposal combo must be an object")
        payload = item.get("payload")
        obj(payload, PAYLOAD_KEYS, "proposal payload")
        name = route_name(payload.get("name"))
        if name in proposals:
            raise ValueError("Duplicate proposal route name")
        text(item.get("endpoint"))
        simple_models(payload.get("models"), desired=True)
        if "description" in payload and (
            not isinstance(payload["description"], str) or len(payload["description"]) > 2000
        ):
            raise ValueError("Invalid proposal description")
        if "strategy" in payload and payload["strategy"] != "priority":
            raise ValueError("Reviewed adapter proposals require priority strategy")
        if "dimensions" in payload:
            dimensions(payload["dimensions"])
        if "config" in payload:
            obj(payload["config"], CONFIG_KEYS, "managed config")
            config_values(payload["config"])
        proposals[name] = item
    return proposals


def index_ownership(owners, proposals):
    claims = {}
    used_ids = set()
    for claim in owners:
        obj(
            claim,
            {"proposalName", "comboId", "currentName", "endpoint", "evidence", "allowedProviders"},
            "ownership claim",
        )
        name = text(claim.get("proposalName"))
        text(claim.get("endpoint"))
        refs(claim.get("evidence"))
        if name in claims or name not in proposals:
            raise ValueError("Duplicate or missing owned proposal")
        identity = claim.get("comboId")
        if identity is not None:
            text(identity)
            text(claim.get("currentName"))
            if identity in used_ids:
                raise ValueError("One current combo cannot serve multiple proposals")
            used_ids.add(identity)
        elif claim.get("currentName") is not None:
            raise ValueError("Creation claims cannot bind a current name")
        if "allowedProviders" in claim:
            if len(claim["allowedProviders"]) > 100 or any(
                len(value) > 200 for value in strings(claim["allowedProviders"])
            ):
                raise ValueError("Provider allowlist exceeds native API bounds")
            if not strings(claim["allowedProviders"]):
                raise ValueError("Explicit allowlist approval must remain restrictive")
        claims[name] = claim
    return claims, used_ids


def route_patch(old, payload, claim, allowlist, reasons):
    patch, rollback = {}, {}
    if old:
        before_models = [model_identity(step) for step in old["models"]]
        after_models = [model_identity(step) for step in payload["models"]]
        if before_models != after_models:
            if guarded_models(old["models"]):
                reasons.append("legacy-or-scoped-steps-require-explicit-migration")
            else:
                patch["models"], rollback["models"] = payload["models"], old["models"]
        for field in ("name", "description", "strategy", "dimensions"):
            if field in payload and payload[field] != old.get(field):
                if field == "dimensions" and field not in old:
                    reasons.append("adding-dimensions-has-no-supported-clear-rollback")
                    continue
                patch[field] = payload[field]
                rollback[field] = old.get(field)
        config = {**old["config"], **payload.get("config", {})}
        if config != old["config"]:
            patch["config"], rollback["config"] = config, old["config"]
        if "allowedProviders" in claim and claim["allowedProviders"] != old.get("allowedProviders"):
            patch["allowedProviders"], rollback["allowedProviders"] = (
                claim["allowedProviders"],
                old.get("allowedProviders"),
            )
    else:
        patch = dict(payload)
        if allowlist:
            patch["allowedProviders"] = allowlist
    return patch, rollback


def plan(proposal, current, ownership, proposal_hash, export_hash):
    for value in (proposal, current, ownership):
        sanitized(value)
    obj(current, {"version", "total", "combos"}, "sanitized export")
    obj(ownership, {"version", "reviewedProposalSha256", "reviewedExportSha256", "routes"}, "ownership")
    if (
        type(current.get("version")) is not int
        or current["version"] != 1
        or type(ownership.get("version")) is not int
        or ownership["version"] != 1
    ):
        raise ValueError("Export and ownership version must be 1")
    if ownership.get("reviewedProposalSha256") != proposal_hash or ownership.get("reviewedExportSha256") != export_hash:
        raise ValueError("Ownership must bind exact reviewed input bytes")
    rows, desired, owners = current.get("combos"), proposal.get("proposedCombos"), ownership.get("routes")
    if any(not isinstance(x, list) or len(x) > MAX_ROWS for x in (rows, desired, owners)):
        raise ValueError("Inputs require bounded arrays")
    if type(current.get("total")) is not int or current["total"] != len(rows):
        raise ValueError("Sanitized export must be complete")
    by_id, by_name = index_current_combos(rows)
    proposals = index_proposals(desired)
    claims, used_ids = index_ownership(owners, proposals)
    operations, decisions = [], []
    for name, item in sorted(proposals.items()):
        claim, payload = claims.get(name), item["payload"]
        reasons = []
        if claim is None:
            decisions.append({"name": name, "status": "blocked", "reasons": ["exact-ownership-unverified"]})
            continue
        if claim["endpoint"] != item["endpoint"]:
            reasons.append("endpoint-ownership-mismatch")
        identity = claim.get("comboId")
        old = by_id.get(identity) if identity is not None else None
        if identity is not None and (old is None or old["name"] != claim["currentName"]):
            reasons.append("current-ID-name-binding-mismatch")
        if name in by_name and by_name[name] != identity:
            reasons.append("desired-name-already-owned-by-another-ID")
        allowlist = claim.get("allowedProviders", old.get("allowedProviders") if old else None)
        provider_set = {step["providerId"] for step in payload["models"]}
        if allowlist and not provider_set <= set(allowlist):
            reasons.append("desired-model-provider-outside-approved-allowlist")
        if old and name != old["name"]:
            reasons.append("rename-requires-separate-reference-migration")
        if old and (old.get("allowedModelFamilies") or old.get("invariant")):
            reasons.append("additional-runtime-invariants-require-explicit-review")
        patch, rollback = route_patch(old, payload, claim, allowlist, reasons)
        if reasons:
            decisions.append({"name": name, "comboId": identity, "status": "blocked", "reasons": reasons})
            continue
        if old and not patch:
            decisions.append({"name": name, "comboId": identity, "status": "noop", "reasons": []})
            continue
        operation = {
            "name": name,
            "comboId": identity,
            "endpoint": item["endpoint"],
            "evidence": claim["evidence"],
            "action": "update" if old else "create",
            "forward": {
                "method": "PUT" if old else "POST",
                "path": f"/api/combos/{quote(identity, safe='')}" if old else "/api/combos",
                "body": patch,
            },
            "preconditions": {
                "exportSha256": export_hash,
                "comboRecordSha256": digest(old) if old else None,
                "expectedName": old["name"] if old else None,
                "desiredNameMustBeUnique": name,
            },
            "rollback": (
                {"method": "PUT", "path": f"/api/combos/{quote(identity, safe='')}", "body": rollback}
                if old
                else {
                    "method": "DELETE",
                    "pathFromCreatedResponseId": "/api/combos/{created-id}",
                    "requiresCreatedRecordIdentityAndPostApplyHash": True,
                }
            ),
        }
        operations.append(operation)
        decisions.append({"name": name, "comboId": identity, "status": "planned", "reasons": []})
    return {
        "version": 1,
        "mode": "offline-review-only",
        "source": {"proposalSha256": proposal_hash, "exportSha256": export_hash, "ownershipSha256": digest(ownership)},
        "operations": operations,
        "decisions": decisions,
        "preservedUnownedRoutes": [
            {"id": row["id"], "name": row["name"]}
            for row in sorted(rows, key=lambda row: row["id"])
            if row["id"] not in used_ids
        ],
        "executionRequirements": [
            "Re-export and compare preconditions immediately before any mutation.",
            "Capture exact post-apply record hashes and created IDs before using rollback.",
            "Apply only through the matching inspected OmniRoute API version.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("proposal", "current", "ownership", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(
        lambda event, _: (
            (_ for _ in ()).throw(RuntimeError("Network disabled"))
            if event in ("socket.connect", "socket.getaddrinfo", "socket.bind")
            else None
        )
    )
    proposal, proposal_hash = read_json(args.proposal)
    current, export_hash = read_json(args.current)
    ownership, _ = read_json(args.ownership)
    result = plan(proposal, current, ownership, proposal_hash, export_hash)
    args.output.write_bytes(encode(result))
    print(f"Planned {len(result['operations'])} reversible operations; decisions {len(result['decisions'])}")


if __name__ == "__main__":
    main()
