# OmniRoute catalog adapter

`llm_fallbacks.omniroute` reads the generated `configs/free_models.json` from `ai-llm-experiments/llm_fallbacks` and a credential-free access manifest. It writes sorted proposed OmniRoute combo payloads and dispositions for every submitted access target. It records input SHA-256 hashes and an explicit observation time so repeated runs with the same inputs produce identical output.

The catalog changes over time. Its generator can represent absent input and output token prices as zero, and includes subscription, trial, image, and other entries. Its `quality_score` is a capability heuristic. Current price verification and account entitlement therefore come from the access manifest. Ordering preserves the original catalog rank after the operator's explicit priority, including the repository's pinned preference and capability scoring.

Run the adapter with a freshly generated repository catalog and a verified access manifest.

```sh
python -m llm_fallbacks.omniroute \
  --catalog configs/free_models.json \
  --access configs/omniroute-access.example.json \
  --as-of 2026-11-15T23:00:00Z \
  --output omniroute-proposal.json
```

The example starts with empty access and runtime support lists. Populate `targets` from current, private operational evidence using the shape below. Evidence values should reference receipts or official documents without credentials or personal prompts.

```json
{
  "catalogProvider": "openrouter",
  "catalogId": "cohere/north-mini-code:free",
  "providerId": "openrouter",
  "model": "cohere/north-mini-code:free",
  "connected": true,
  "providerScopeApproved": true,
  "prices": {"prompt": 0, "completion": 0, "request": 0},
  "pricesComplete": true,
  "freeOnlyEnforced": true,
  "requestSucceeded": true,
  "verifiedAt": "2026-11-15T23:00:00Z",
  "evidence": ["private receipt path", "official price and privacy source"],
  "privacy": "public-demo",
  "purposes": ["coding"],
  "purposeEvidence": {"coding": "task suitability receipt"},
  "toolsVerified": true,
  "endpoints": ["chat/completions"],
  "quotaGroup": "openrouter-shared-free-account",
  "priority": 10
}
```

This shape illustrates required fields. The values need current operational evidence before inclusion in a real access manifest. `providerScopeApproved` establishes that every account selectable by this provider satisfies the route's cost and privacy policy. Per-account restrictions need additional runtime admission verification before a provider-wide target is suitable. `prices` must enumerate every applicable token, request, media, and processing price dimension and all must be numeric zero. `pricesComplete` records that completeness was checked. A zero token price alone does not establish free media generation. `freeOnlyEnforced` records verification that this provider path cannot escalate into a paid model or endpoint.

`privacy` selects `*-free` for explicitly approved private use and `*-free-demo` for public prompts. Unknown privacy is excluded. `comboEndpoints` lists endpoints where the deployed OmniRoute version has verified compatible combo dispatch. This permits source-supported modalities to be exposed as they become operational. Coding and persona targets need purpose-specific evidence. Agent and coding targets also require catalog function-call support and a successful tool-contract check.

The target's `model` must exactly equal its canonical `catalogId`. Prefix translations and aliases require reconciliation in the canonical catalog before admission. The target's `providerId` must equal its canonical provider, or appear in `providerMappings` as an explicit `{ "catalogProvider": "openrouter", "providerId": "custom-node-id", "evidence": ["verified node configuration receipt"] }` mapping. Every evidence reference and purpose proof must contain nonblank text. `maxAgeHours` must be a positive finite number. Invalid values fail generation.

Embedding targets additionally require an `embeddingSpace` object with a nonblank string `identity`, positive integer `dimensions`, and nonblank `evidence` references, plus a purpose-based `routeName` starting with `embed-` and ending in `-free` or `-free-demo`, such as `embed-semantic-free-demo`. Every admitted target in that route must have the identical space and dimensions. Cross-model embedding similarity requires explicit proof in that space identity. Excluded targets do not register embedding metadata. Reusing a route name across incompatible endpoints fails generation.

Proposals use priority routing and enabled account stickiness. Runtime model affinity, exact-account admission, failover, key permissions, and live request behavior remain deployment verification responsibilities. Every eligible target is retained in the sorted route. The attempt budget defaults to the eligible target count up to OmniRoute's hard limit of 200. `beyondAttemptBudget` explicitly lists targets beyond that execution limit. The default whole-combo deadline is ten minutes and is configurable through `comboTimeoutMs`. A request stops at its first success, attempt budget, or deadline. Hundreds of catalog rows sharing one gateway share its quotas.

The adapter writes proposed payloads only. The parent deployment workflow owns import, update/rename compatibility, activation, source review, and live verification. Keep credentials in the existing secret manager and omit them from the access manifest.

## Provider catalog evidence

`llm_fallbacks.provider_catalogs` provides offline snapshot parsers for OpenRouter, Kilo, Groq, Cerebras, Google AI Studio, and Hugging Face. It preserves supported capability and pricing metadata, rejects incomplete pagination, and does not enable accounts or automatically fetch newly registered providers. For example, inspect a trusted saved response with `python -m llm_fallbacks.provider_catalogs --provider kilo --snapshot /path/to/models.json --output /tmp/kilo-catalog.json`.

For several saved snapshots, the [multi-provider pipeline](provider-snapshot-pipeline.md) generates a candidate catalog, evidence draft, proposal, and audit report together. Its registry IDs are not necessarily OmniRoute runtime IDs; reconcile mappings before any import.

The [offline reconciliation planner](omniroute-reconciliation.md) compares an approved proposal with a complete sanitized export and an explicit ownership manifest. It produces reviewable plans only; live API compatibility, admission and executor concurrency still require verification. Model-list changes can clear session history, which configuration rollback cannot recover.

Free-only classification requires explicit, complete zero pricing for supported text or embedding contracts. Missing, partial, invalid, or positive pricing is not free. Media and other endpoint shapes are excluded from automatic free classification until their complete pricing contracts are represented. Account tier, quota, privacy, and runtime entitlement require separate current evidence regardless of catalog classification.

Known dynamic selectors, including OpenRouter's free and auto router families and Kilo's auto selector, are held from exact-model proposals because their downstream model can change. Wildcards and opaque or whitespace-decorated identifiers are also rejected. This check covers known selectors, not arbitrary database aliases; verify the deployed runtime's mapping before import.

## Import a saved OpenRouter snapshot

The optional offline importer refreshes candidate metadata from a saved public OpenRouter models response and combines it with a credential-free evidence file. It calls the scoring helpers from the repository path supplied by the operator; only point it at trusted code. It does not fetch the snapshot, contact providers, or change routes.

```sh
python scripts/import_openrouter_snapshot.py \
  --models /path/to/saved-openrouter-models.json \
  --observed-at 2026-11-15T23:00:00Z \
  --as-of 2026-11-15T23:30:00Z \
  --catalog configs/free_models.json \
  --evidence configs/omniroute-openrouter-evidence.example.json \
  --repository . --output-dir /tmp/omniroute-snapshot
```

`catalog.candidate.json`, `access.draft.json`, and `import-report.json` are review artifacts, not runtime changes. Record the real observation and evaluation times; future and stale evidence is rejected. The example has no account or model attestations and remains ineligible. Explicit zeroes in reported pricing fields are only candidate metadata: verify completeness, account scope, privacy, endpoint, and usage policy before adding attestations. This importer handles OpenRouter; the main catalog includes other providers and requires separate provider-specific evidence.
