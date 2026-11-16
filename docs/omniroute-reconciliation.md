# Offline OmniRoute reconciliation planning

`scripts/plan_omniroute_reconciliation.py` compares a reviewed llm_fallbacks `proposal.json` with a complete sanitized combo export and an explicit exact-ID ownership manifest. It writes a review artifact containing forward operations, rollback operations, preconditions, no-op decisions, blocked changes and preserved unowned routes. It performs local file operations only. The CLI installs a network-denial audit hook.

```bash
python scripts/plan_omniroute_reconciliation.py \
  --proposal /path/to/reviewed-proposal.json \
  --current /path/to/sanitized-combos.json \
  --ownership /path/to/ownership.json \
  --output /path/to/reconciliation-plan.json
```

Inputs are limited to 16 MiB and arrays to 20,000 rows. The current export must have `{"version":1,"total":N,"combos":[...]}` and contain every combo. `total` must match its row count. Retain each combo's exact ID, name, strategy, full config, model steps and routing restrictions. Supported optional fields are description, allowedProviders, allowedModelFamilies, invariant, version, isActive, isHidden and dimensions. Omit timestamps and unrelated API metadata. Sanitization must preserve the complete behavior of supported fields. Do not remove connection restrictions, prompts, tags or weights to make an input pass. The planner blocks changes to opaque or scoped model chains.

The ownership manifest binds exact SHA-256 hashes of the proposal and sanitized export file bytes. Each owned route requires a reviewed proposal name, existing combo ID and existing name, endpoint and evidence references.

```json
{
  "version": 1,
  "reviewedProposalSha256": "sha256-of-exact-proposal-file",
  "reviewedExportSha256": "sha256-of-exact-sanitized-export-file",
  "routes": [{
    "proposalName": "text-free",
    "comboId": "exact-existing-combo-id",
    "currentName": "text-free",
    "endpoint": "chat/completions",
    "evidence": ["receipt-reviewing-this-exact-ID-and-update"]
  }]
}
```

For an explicitly reviewed creation, set `comboId` and `currentName` to null. A name already belonging to any current ID blocks creation. Existing names, description prefixes and model overlap cannot establish ownership. One existing ID can serve one proposed route. No deletion operations are generated for existing routes absent from the proposal. Legacy routes remain listed as preserved when unowned. All renames remain blocked pending a separate reference-migration workflow. External keys, defaults and clients are outside these input hashes, and rename handlers may commit before a later response error. This initial planner supports same-name updates and creations.

Existing nonempty `allowedProviders` restrictions are enforced against every desired model. New providers outside that restriction block the plan. An ownership row may explicitly approve a nonempty final `allowedProviders` list, with its evidence covering that change. The planner never generates `overrideAllowedProviders`. Existing additional family or invariant restrictions block automatic updates pending separate review.

For simple structured model steps, comparison uses exact provider IDs and the inspected source's `toFullModelString` normalization. A bare model with an explicit provider matches its stored provider-prefixed representation. Vendor/model names containing a slash retain their spelling. Step IDs and display labels do not cause a model-list rewrite. When ordered target identities are unchanged, the entire existing model list remains untouched, preserving scopes and metadata. Changed lists containing scoped, weighted, prompted, tagged, wildcard, nested or legacy steps are blocked for explicit migration. This candidate does not resolve legacy aliases by guessing.

Managed config changes merge the reviewed adapter keys into the full current config. Unrelated settings remain present. Rollback includes the prior complete config. Existing descriptions can be restored or null-cleared through the inspected update schema. Adding dimensions is blocked when the export has no prior dimension field because this candidate has no verified null-clear rollback contract for that field.

Every update carries the exact existing ID, expected current name and sanitized record hash. Every plan carries the input export hash. Any future executor must re-export and verify these preconditions immediately before changing state, including matching the live API version. Rollback must be guarded by captured post-apply hashes so it cannot overwrite intervening edits. Creation rollback needs the ID from the successful create response and that exact created record's post-apply hash. This artifact itself contains no executor or transaction guarantee.

The planner rejects unsupported fields and credential-shaped keys recursively, including token, camelCase access/refresh tokens, client secrets, private keys and punctuation variants of API keys. Anchored normalized credential patterns preserve native noncredential token controls such as reasoningTokenBufferEnabled, maxCostPer1MTokens and slaMaxCostPer1MTokens. Sanitized export production remains a separate authorized operation. Evidence strings should be receipt references without credentials or private prompt content.

## Inspected local source

The implementation follows the retained OmniRoute update/create handlers, combo step normalizer and invariant checks under `/home/brunner56/omniroute-ops/upstream/src`.

- `app/api/combos/route.ts` returns paginated combos and total, and normalizes new steps.
- `app/api/combos/[id]/route.ts` handles existing allowlists, optional widening and schema validation.
- `lib/combos/steps.ts` defines exact structured steps and provider-prefix normalization.
- `lib/combos/invariants.ts` enforces provider/family restrictions.
- `shared/validation/schemas/combo.ts` defines update fields and nullable description/allowlist behavior.

These local source observations do not establish source parity with any deployed image.

## Inline verification receipt

Network-denied in-memory checks passed normalized model no-ops, preservation of unrelated config, reversible config/allowlist patches, explicit provider expansion approval, scoped and legacy model protection, name collision, preserved unowned routes, exact input hash binding and deterministic repeated plans. Verification created no test files and made no live calls.


## Review reconciliation

Exact desired targets reject wildcard/opaque target syntax. Provider IDs are limited to 120 characters and model IDs to 300 characters. Route names follow the native 100-character format. Managed settings enforce attempts 1–200, retries/set retries 0–10, timeout 0–2147483647 milliseconds, and a boolean stickiness setting. Dimensions require a positive decimal integer string. Explicit allowlists retain native array/string bounds.

Additional network-denied inline checks passed credential key variants at nested levels, wildcard rejection, native config ranges/types, dimension validation, held renames and model-list no-op preservation. These checks supersede the initial rename fixture. No live state changed.
