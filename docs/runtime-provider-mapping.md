# Explicit runtime provider mapping

The offline multi-provider importer accepts explicit runtime mappings. It does not change live configuration. Use `scripts/import_provider_snapshots.py` with the arguments documented in [the pipeline guide](provider-snapshot-pipeline.md).

The evidence input additionally accepts `runtimeMappings`. Each mapping requires the exact canonical catalog provider, exact runtime provider ID, explicit quota group, observation time and nonblank receipt references. Provider spellings carry no implicit equivalence. A Kilo catalog can map to `kilo-gateway`, `kilocode` or a custom connected node only when that exact mapping has evidence. Google AI Studio can map to `gemini` under the same rule.

This synthetic example illustrates the required binding. Replace every value with verified live facts before relying on the proposal.

```json
{
  "version": 1,
  "comboEndpoints": ["chat/completions"],
  "runtimeMappings": [{
    "provider": "kilo",
    "providerId": "kilo-gateway",
    "quotaGroup": "verified-account-one",
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-exact-catalog-to-runtime-node"]
  }],
  "accounts": [{
    "provider": "kilo",
    "providerId": "kilo-gateway",
    "connected": true,
    "providerScopeApproved": true,
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-every-account-selected-by-this-node"]
  }],
  "modelChecks": [{
    "provider": "kilo",
    "providerId": "kilo-gateway",
    "model": "exact-upstream-model-id",
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-request-through-this-exact-runtime-node"],
    "privacy": "private-approved",
    "purposes": ["text"],
    "endpoints": ["chat/completions"],
    "pricesComplete": true,
    "freeOnlyEnforced": true,
    "requestSucceeded": true
  }]
}
```

`accounts` and `modelChecks` accept an optional `providerId`. Omitting it binds the record to the canonical provider ID itself. A record scoped to `kilo` cannot approve `kilo-gateway`. Every alternate runtime ID requires its own mapping, account-scope receipt and exact model request evidence. Model IDs retain their exact canonical identity. The same model may have independently checked targets on several runtime nodes.

All mappings, accounts, model checks, local price proofs and saved snapshots must independently pass the explicit evaluation freshness window. Mapping time joins the minimum timestamp on each generated target so an old mapping cannot inherit fresh request evidence. Unused supplied mappings still undergo validation. Provider IDs cannot collide with a different registered canonical provider or map to multiple canonical providers.

Quota groups come from the exact mapping. They must identify the actual shared account/quota boundary, including when several runtime nodes use the same account. A model check cannot override its mapped quota group. Distinct verified account boundaries can have distinct groups. These groups document shared capacity for review and runtime monitoring. The existing OmniRoute adapter does not enforce quota reservations from this metadata.

The wrapper runs the reviewed importer separately for each catalog/runtime binding, then merges exact canonical rows and preserves independently scoped runtime targets. Conflicting canonical metadata across nodes rejects the proposal. The generated access policy includes explicit provider mapping evidence for the existing OmniRoute adapter. Exact serialized catalog/access hashes remain bound to emitted bytes. Full target lists, existing attempt/deadline limits and session stickiness are preserved.

The candidate does not fetch catalogs, inspect credentials, connect accounts, prove the contents of evidence receipts, or deploy proposals. Pricing/privacy admission rules and conservative media/embedding limitations remain those of the reviewed base importer and repository adapter.

## Inline verification

Network-denied in-memory checks passed exact Kilo-to-kilo-gateway binding, custom node mapping, one canonical model with two independent runtime targets, separate quota groups, deterministic repeated output and exact policy hash. Missing mappings, future mapping times, blank receipts, mismatched account/model identities, unapproved account scope, quota overrides and credential-shaped fields reject or remain excluded. Verification created no test files.

## Resource-bound reconciliation

A run freezes each resolved snapshot path and its hash on its first read. It parses each provider/path pair once and reuses that frozen catalog across runtime nodes. A later change to the source file cannot change another node's view within the run.

The wrapper limits the total runtime bindings to 20,000 and limits expanded snapshot work to 20,000 parsed model rows across all bindings. For example, a 1,000-row catalog supports at most 20 bindings in one proposal run. This conservative work bound applies before starting the next binding, even when many rows would later be excluded. Combined target capacity is checked before retaining a binding's targets, and unique catalog capacity is checked before insertion. Oversized expansions reject with an explicit error.

A network-denied reduced-bound reproducer used two models and two runtime nodes. A three-row work bound rejected before constructing the second binding. A four-row bound completed with one file read, one provider parse, two canonical rows, four target drafts and one stable snapshot hash across both nodes. Candidate syntax passed again.
