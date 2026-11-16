# Offline multi-provider route pipeline

`scripts/import_provider_snapshots.py` consumes saved snapshots for any configured `provider_catalogs.PROVIDER_CATALOGS` parser in llm_fallbacks. The current registry includes Kilo, OpenRouter, Groq, Cerebras, Google AI Studio, Hugging Face, Mistral, Cohere, NVIDIA NIM, Together AI, Fireworks AI, SambaNova and Nebius Token Factory. The parser and pricing implementation come from the selected repository, with helper hashes recorded in the report. It loads pure files directly and skips package/config discovery. Its CLI denies networking.

Run from the repository root with explicit paths and evaluation time.

```bash
python scripts/import_provider_snapshots.py \
  --repository . \
  --manifest /path/to/snapshots.json \
  --evidence /path/to/evidence.json \
  --as-of 2026-11-16T01:00:00Z \
  --output-dir /path/to/proposal-review
```

Snapshot paths are resolved from the process working directory. One complete snapshot per provider is allowed. Pagination and count completeness follow the repository parser. Each input is limited to 16 MiB, individual arrays to 20,000 rows, and the combined candidate catalog to the route adapter's 20,000-row bound. Relative and absolute snapshot paths are accepted.

The manifest has this shape. Replace the paths with existing saved provider responses and record their actual observation times.

```json
{
  "version": 1,
  "snapshots": [
    {"provider": "kilo", "path": "/path/to/kilo-models.json", "observedAt": "2026-11-16T00:00:00Z"},
    {"provider": "groq", "path": "/path/to/groq-models.json", "observedAt": "2026-11-16T00:00:00Z"},
    {"provider": "google_ai_studio", "path": "/path/to/google-models.json", "observedAt": "2026-11-16T00:00:00Z"}
  ]
}
```

A minimal evidence input is `{"version":1}`. It creates candidate metadata from explicitly eligible catalog rows while leaving route admission blocked. Credentials have no supported input field. Strict object-field allowlists reject accidental `apiKey`, `token` and other unexpected fields. Evidence reference strings should point to receipts and must never contain credentials.

For an admitted text route, an operator-supplied evidence record has this shape. The example values describe a synthetic fixture and establish no live account, price or privacy facts.

```json
{
  "version": 1,
  "maxAgeHours": 24,
  "comboEndpoints": ["chat/completions"],
  "maxGlobalAttempts": 200,
  "comboTimeoutMs": 600000,
  "accounts": [{
    "provider": "groq",
    "connected": true,
    "providerScopeApproved": true,
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-account-scope"]
  }],
  "modelChecks": [{
    "provider": "groq",
    "model": "exact-upstream-model-id",
    "verifiedAt": "2026-11-16T00:00:00Z",
    "evidence": ["receipt-successful-request"],
    "mode": "chat",
    "modeEvidence": ["receipt-endpoint-contract"],
    "verifiedPricing": {
      "prices": {"prompt": "0", "completion": "0"},
      "verifiedAt": "2026-11-16T00:00:00Z",
      "evidence": ["receipt-complete-account-price-contract"]
    },
    "privacy": "private-approved",
    "purposes": ["text"],
    "endpoints": ["chat/completions"],
    "pricesComplete": true,
    "freeOnlyEnforced": true,
    "requestSucceeded": true,
    "quotaGroup": "groq-shared-account"
  }]
}
```

`verifiedPricing` can supply zero-price metadata only when a saved provider response has no reported pricing. It cannot override existing positive, invalid or partial provider pricing. The evidence must establish all applicable account charges and enforcement, including quota exhaustion behavior. The pipeline validates evidence structure and freshness. The operator remains responsible for the truth of the referenced receipts.

An unknown endpoint mode can be supplied through a fresh model check with nonblank `modeEvidence`. Known endpoint modes remain authoritative. Capability metadata remains the provider parser's responsibility. A local mode receipt does not assert tools or task suitability. Agent/coding routes still require catalog tools support and `toolsVerified`. Coding/persona routes additionally require the existing adapter's purpose evidence.

Every supplied timestamp is validated independently before aggregation. Future or stale account, model, pricing and snapshot observations reject the run. Missing checks keep privacy unknown and admission disabled. Privacy can be `private-approved` or `public-demo` only with verified model-check evidence. Demo targets retain the adapter's `free-demo` naming. Account approval covers every account that the runtime provider ID might select. Exact registry provider IDs are the default; alternate node IDs require independently verified [runtime mappings](runtime-provider-mapping.md).

The four outputs are `catalog.candidate.json`, `access.draft.json`, `proposal.json` and `import-report.json`. They contain exact upstream IDs, full source hashes, dispositions and unmatched checks. Candidate rank uses the repository's quality heuristic descending, then provider and exact model ID. Target priority and session stickiness follow the existing OmniRoute adapter. All eligible targets remain listed. Per-request attempts retain the adapter's explicit maximum of 200 and whole-combo deadline, with beyond-budget targets reported.

Media and other unsupported pricing contracts remain excluded by the repository's explicit-zero policy. Input-only embeddings can appear as catalog candidates, but the current route adapter requires both numeric token-price fields, so incomplete embedding route evidence remains excluded. This pipeline does not create either price dimension or an embedding-space identity. Preserve those compatibility boundaries when reviewing generated outputs.

## Inline verification receipt

An in-memory three-provider snapshot matrix covered Kilo, Groq and Google AI Studio. Kilo supplied complete catalog zero prices. Groq supplied unknown prices and mode, then required explicit fresh local receipts for both. Google remained excluded with unknown price metadata. Explicit account/model evidence produced a deterministic two-provider text proposal. Missing evidence, unknown privacy, mismatched exact IDs, future account/pricing times and credential-shaped fields stayed blocked or rejected. Python socket audit hooks denied network use throughout. The verification created no test files and made no provider requests.

## Review reconciliation

Malformed provider `pricing` values, including strings, lists and booleans, reject the entire input. Local price evidence is eligible only when provider pricing is absent or explicitly null. An empty or partial provider pricing object remains authoritative and cannot be replaced.

Nested purpose evidence accepts known route-purpose keys with nonblank string references. Embedding-space objects accept only identity, positive integer dimensions and string receipt references. Priority is finite numeric data, route names and quota groups are strings, endpoint/purpose arrays contain strings, and flags are booleans. These rules apply to every supplied check, including unused fields and checks that routing would exclude.

Catalog and access hashes in `proposal.json` use the exact UTF-8 bytes emitted to their respective files, including indentation and final newline. The same serialization function produces both artifacts and their hashes.

Additional inline adversarial checks reject malformed provider price metadata and nested credential-shaped objects in purpose evidence, embedding space, priority, route name, endpoint/purpose arrays and flags. Absent/null pricing with explicit fresh proof retains the valid baseline, while partial pricing remains excluded. Exact-byte catalog/access hash comparisons pass with networking denied.


## Mistral and Cohere discovery

The Mistral parser consumes a complete `data` model list, preserves explicit chat, function-calling and vision declarations, and excludes archived models. Combined context windows remain `context_window` metadata. They are not converted to an available input-token allowance. Prices absent from the catalog remain unknown. Mistral's free evaluation mode still requires account-specific entitlement and enforcement evidence. Its `labs-` model identifiers receive a conservative prompt-use flag because the documented lifecycle contract does not support data-collection opt-out. Labs models can change silently and are unsuitable for the stable default lane. The parser does not manufacture zero prices from their names. [Model catalog](https://docs.mistral.ai/api/endpoint/models), [API limits](https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them), [Lifecycle contract](https://docs.mistral.ai/inference/model-lifecycle)

The Cohere parser consumes a complete `models` list and rejects a remaining `next_page_token`. It preserves exact names and compatible endpoints and excludes deprecated models. A single unambiguous supported endpoint mode can populate `mode`. Mixed or unrecognized endpoint modes remain unknown. Trial keys provide limited free access, while production keys have different billing. The model list does not identify the connected key's tier or provide complete prices, so account and pricing evidence remain required. Combined context windows are retained separately from input-token limits. [Model catalog](https://docs.cohere.com/v2/reference/list-models), [Key types and limits](https://docs.cohere.com/docs/rate-limits)

The route adapter rejects a `private-approved` operator label when a canonical catalog explicitly says prompts may be used for training. A `public-demo` route still requires all existing account, cost, capability, privacy and live-request evidence. Missing privacy remains unadmitted, and malformed catalog training flags are rejected by admission.

GitHub Models was retired on July 30, 2026; its catalog, inference and BYOK are unavailable. Active inventories and generated routes exclude its aliases, while saved user keys are retained. GitHub Copilot is a different service. [GitHub retirement notice](https://docs.github.com/en/github-models)


## Stable catalog privacy provenance

The standard `generate_configs` export keeps the existing 19-field `free_models.json` rows and writes a companion `free_models.provenance.json`. The sidecar records the exact catalog byte SHA-256, generation timestamp, and every exact provider/model identity with its original boolean prompt-training metadata or `null` for unknown. It does not infer a false flag from a missing field.

When proposing routes from that standard catalog, pass both files to the adapter.

```bash
python -m llm_fallbacks.omniroute \
  --catalog /path/to/free_models.json \
  --privacy-provenance /path/to/free_models.provenance.json \
  --access /path/to/access.json \
  --as-of 2026-11-16T00:00:00Z \
  --output /path/to/proposal.json
```

The sidecar must match the catalog hash, cover the complete exact identity set without duplicates, and fall inside the same freshness window as admission evidence. Unsupported fields, malformed flags, and conflicting rich-catalog metadata reject the run. The proposal records both the canonical sidecar digest and its exact file digest. Generation time records when metadata was exported. It does not establish that the provider's contract was independently reverified then. Current account/model verification and their receipt references are still required. Provenance input must come from the trusted catalog build, since these hashes detect mismatched artifacts rather than authenticate the source.

A `private-approved` target requires explicit `may_train_on_prompts=false` in a rich canonical row or matching sidecar. A label without that source metadata stays excluded. A true flag cannot be relabeled private by access evidence, and unknown metadata remains excluded from private routing. An explicitly approved public-demo target can retain unknown training metadata because it already requires public prompts and the existing admission evidence. Unknown privacy classification remains excluded from every route.

The offline snapshot pipeline preserves rich parser metadata in its candidate catalog and can therefore retain explicit training flags directly. A provider whose catalog offers no prompt-use information needs a separately verified source contract before a private route can be admitted. Existing saved catalog files require regeneration of the companion sidecar from their source specifications. Manually reconstructing a false flag from an omitted field would defeat this boundary.


## NVIDIA NIM and Together AI snapshots

The NVIDIA NIM descriptor uses the existing OpenAI-compatible parser for `https://integrate.api.nvidia.com/v1/models`. A public observation returned 39 exact model IDs with creation/owner metadata and no prices or endpoint capabilities. These entries therefore retain unknown mode and pricing. The cloud catalog does not establish access to every model-specific NIM service, a connected account's quota, or the cost of self-hosting. Inference credentials use `NVIDIA_API_KEY`. [NVIDIA hosted API](https://docs.api.nvidia.com/nim/reference/llm-apis), [NIM model endpoint](https://docs.nvidia.com/nim/large-language-models/latest/get-started/quickstart.html)

Together's official SDK defines `GET /v1/models` as a complete bare JSON array, unlike an OpenAI `data` wrapper. Its model `type` maps documented unambiguous categories to the repository's endpoint modes. Generic audio and future model types remain unknown. Combined context windows are retained separately from input-token allowances. The parser preserves exact IDs and rejects duplicates and malformed schema/pricing. Inference credentials use `TOGETHER_API_KEY`. [Official SDK model listing](https://github.com/togethercomputer/together-python/blob/807b79024fdcc4c3d37f49cc65b8d885322ae6b4/src/together/resources/models.py), [Official SDK schema](https://github.com/togethercomputer/together-python/blob/807b79024fdcc4c3d37f49cc65b8d885322ae6b4/src/together/types/models.py)

For Together chat, language and code types, numeric `pricing.input` and `pricing.output` are converted from USD per million tokens to the repository's per-token fields. The original quote is retained in pricing evidence. Every additional quoted field remains visible under a provider-prefixed name, so a positive, malformed or unknown extra charge prevents automatic zero-cost classification. Missing input/output values remain unknown. Other endpoint types preserve their pricing without token-unit conversion and remain excluded until their complete pricing contracts are supported. [Together serverless pricing units](https://docs.together.ai/docs/serverless/models)

Together currently requires a minimum credit purchase for account/API-key access and a positive balance, even though its model catalog contains a zero-priced text model. The parser can represent an explicit zero usage quote, while routing still requires evidence of account entitlement, complete applicable costs, free-only enforcement, privacy, capability and a successful request. A zero-usage-price model does not waive that paid access prerequisite. This candidate performed no purchase, credential lookup or inference. [Together access and credits](https://docs.together.ai/docs/billing-credits)

The `custom_providers.json` inventory marks NVIDIA NIM and Together AI inference as requiring API keys. Built-in configuration loading defers eager credential validation with `validate_api_key_on_init=False` while keeping `auto_fetch_models=False`, so offline imports can still load without either key. `CustomProviderConfig` retains eager validation by default for existing callers that set `api_key_required=True`. An offline caller constructing a provider from serialized metadata can explicitly pass `validate_api_key_on_init=False`. The serialized provider object keeps its six existing fields. Public model-list access alone does not establish anonymous inference access. [NVIDIA bearer-authenticated inference](https://docs.api.nvidia.com/nim/reference/meta-llama-3_2-3b-instruct-infer), [Together authentication](https://docs.together.ai/docs/api-keys-authentication)


## Exact provider price decoding

Provider snapshot JSON decimals are retained as their original numeric strings by both the parser CLI and the snapshot importer. Account, policy and other evidence JSON retains its existing numeric decoder. Snapshot integers stay integers. Nonstandard NaN/Infinity constants are rejected, numeric literals are bounded to 256 characters, and scientific exponents are bounded to an absolute value of 100,000. The importer requires the selected repository's exact snapshot decoder instead of falling back to lossy float parsing.

Together's per-million conversion constructs the exact decimal coefficient and shifted exponent without applying the process Decimal context. A converted positive price that cannot retain a finite positive numeric cost field is rejected. The parser therefore rejects numeric underflow before a positive source price can be classified as zero. The raw source quote and exact normalized price string remain available in evidence. Unrepresentable prices require explicit handling rather than a zero-price substitution.

## Fireworks AI, SambaNova and Nebius discovery

The Fireworks parser consumes the control-plane `models` resource list and requires completed `nextPageToken` pagination and a matching `totalSize` when present. Resource names retain their full account/model path. Explicit tool and image-input declarations are preserved. Combined context remains `context_window`. The parser leaves modes and prices unknown because this resource list includes multiple deployment types and tier-specific SKU amounts. The descriptor names the public `fireworks` account catalog, while separately obtained account catalogs can use the same response parser. Account rate limits and a prepaid balance do not establish zero-priced inference. [Model list](https://docs.fireworks.ai/api-reference/list-models), [Account quotas](https://docs.fireworks.ai/guides/quotas_usage/account-quotas), [Pricing](https://fireworks.ai/pricing)

The SambaNova parser reads complete `data` lists from the official inference API. The published schema defines prompt and completion rates in USD per token, so explicit valid rates retain those units. Duration pricing remains reported evidence. Model mode, tools, vision and privacy remain unknown because the schema leaves the corresponding metadata untyped. Free-tier access depends on the connected account's payment-method state and current limits. Preview models carry separate operational restrictions. Catalog listing does not prove that an account can perform a request. [Official OpenAPI](https://github.com/sambanova/sambanova-inference-api-spec/blob/main/openapi.documented.json), [Rate-limit tiers](https://docs.sambanova.ai/docs/en/models/rate-limits)

The Nebius Token Factory parser accepts basic or verbose `data` model records, excludes non-active lifecycle states and preserves documented modality and context metadata. The verbose catalog schema names price fields without specifying their units, so those values remain reported evidence with `units_verified=false` and cannot classify a model as free. Missing default-valued fields are never supplied by the parser. Billing setup requires a payment method, and promotional credits can expire. Current independent account and pricing evidence is required before any routing admission. [Model list](https://docs.tokenfactory.nebius.com/api-reference/models/list-models), [Billing](https://docs.tokenfactory.nebius.com/other-capabilities/billing-new)

All three parsers leave prompt-training policy unknown. Private admission still requires explicit verified no-training evidence through the established provenance contract. These offline parsers do not fetch catalogs, create credentials, infer account entitlements or perform inference.


## Retired GitHub Models aliases

GitHub's service notice says GitHub Models retired July 30, 2026, including inference and catalog access. The active built-in provider and URL inventories no longer advertise its endpoint. Cached model metadata, custom provider objects, generated free lists, deployment YAML and OmniRoute admission exclude the exact `github_models` and LiteLLM `github` service aliases. Existing cached browser catalogs also cannot select those retired aliases for fallback. [GitHub service notice](https://docs.github.com/en/github-models), [LiteLLM GitHub Models alias](https://docs.litellm.ai/docs/providers/github)

GitHub Copilot uses the distinct `github_copilot` identity and retains its existing handling. The retirement correction does not establish Copilot account access, prices, permissions or privacy. It creates no mapping from retired Models identifiers to Copilot. Saved browser keys are not rewritten automatically. The existing GitHub Models field is retained with a retirement label, allowing users to clear their saved value explicitly.

The exported provider URL map remains an object of strings, custom provider rows retain six fields, and the standard free-model catalog retains 19 fields. The deliberate inventory changes are the two corrected authentication booleans and retirement exclusions. Other providers' older `api_key_required` flags have not been verified by this correction and should not be interpreted as proof of anonymous inference.

## Chutes, DeepSeek and OpenCode Console discovery

The Chutes parser reads the hosted OpenAI-compatible catalog at `https://llm.chutes.ai/v1/models`. It preserves declared modalities, tools and structured-output flags, combined context windows, output limits and confidential-compute metadata. The documented `price` currency object expresses input and output rates per million tokens. USD token rates use exact decimal scaling, while additional currency or charge observations remain visible to complete-zero checking. An undocumented parallel `pricing` object is retained as an unclassified quote and cannot replace the documented currency quote. Confidential compute alone does not establish an account's prompt-training policy. Hosted inference requires a Chutes API key and is pay per token. [Chutes API and pricing](https://www.chutes.ai/docs/help/faq), [Chutes model discovery](https://chutes.ai/agents)

DeepSeek's current `/models` schema includes optional combined context/output limits, input/output modalities, reasoning-effort levels and protocol-specific system-message behavior. The parser preserves this metadata and leaves prices and tool capabilities unknown when absent. It does not substitute current models for legacy aliases or treat a listed model as permission to run inference. API credentials use `DEEPSEEK_API_KEY`. [Model schema](https://api-docs.deepseek.com/api/list-models/), [Authentication and aliases](https://api-docs.deepseek.com/en/)

The OpenCode descriptor points to the current Console discovery endpoint, `https://opencode.ai/inference/v1/models`. The current public catalog contains nested modalities, capability declarations, token limits, protocol metadata and tiered price objects. The parser retains the price object as unclassified evidence and does not assign canonical zero-cost fields. Its catalog evidence records the documented external free-chat restriction. OpenCode states that free-tier chat is available only within OpenCode and that external clients receive HTTP 403 even with an API key. Paid model or Go access requires separate account evidence. The parser creates no external-client bypass or protocol translation. `OPENCODE_API_KEY` is the documented bearer credential. [Console inference](https://opencode.ai/docs/console/api/inference), [Models](https://opencode.ai/docs/models)

All three adapters require complete bounded snapshots, reject duplicate exact model IDs and incomplete pagination, and leave account entitlement and prompt privacy unknown. They perform no automatic network access or inference. Two public catalog GETs were used to inspect current Chutes and OpenCode shapes, with response hashes retained in the isolated candidate evidence. A catalog GET establishes listing metadata only.

Chutes quote observations use separate structured identities for arbitrary field/currency pairs, so separators inside provider-controlled names cannot collide. The parallel `pricing` quote is retained even when `price` is absent or null. Any observed parallel quote remains authoritative incomplete evidence, preventing a local zero-price attestation from replacing it. Missing or null primary and parallel quotes retain the existing fresh local-pricing-attestation contract. Unknown, malformed and positive observed charges remain excluded by the classifier.

## Novita and Featherless discovery

The Novita parser reads its complete OpenAI-compatible model list and retains declared modalities, context and output limits. Current public records contain integer token amounts alongside nested decimal and tiered quotes. The official list reference does not establish the integer currency scale or the full nested contract, so all observations remain reported evidence and canonical costs stay unknown. [Novita model list](https://docs.novita.ai/api-reference/model-apis-llm-list-models)

The Featherless descriptor requests `all=true`. Its parser has a provider-specific 50,000-row limit within the existing 16 MiB snapshot bound. Other parsers and route output retain their existing 20,000-row limits. Explicit remaining pagination and count mismatches are rejected. A saved response without pagination metadata cannot prove which filters or query produced it, so acquisition evidence remains necessary. Per-token catalog prices and parallel charges are preserved. Explicit inactive or plan-unavailable rows are excluded, while missing plan information and prompt privacy remain unknown. Context metadata describes the model window, which can exceed the account plan's effective ceiling. [Model catalog](https://featherless.ai/docs/api-reference-models), [Plan limits](https://featherless.ai/docs/api-reference-plan)

Read-only public discovery observed 100 Novita records and 22,553 Featherless records. The actual offline importer processed both snapshots and admitted zero targets without current pricing, account and privacy evidence. Catalog size alone does not establish usable inference. The provider-specific discovery limit does not enlarge the combined routing output bound.

Current Hyperbolic documentation uses `https://api.hyperbolic.ai/inference/v1` for chat completions and describes credit-balance billing. A current model-list response schema was not established, so this change adds no Hyperbolic adapter or inferred endpoint. The older `hyperbolic.xyz/v1` inventory requires separate compatibility review. [Current inference documentation](https://hyperbolic.ai/docs/inference/overview), [Chat API](https://hyperbolic.ai/docs/inference/text-apis)


## Remaining provider discovery

OpenAI uses the existing bounded OpenAI model-list parser and the documented `GET /v1/models` endpoint. Its standard list contains exact IDs and owner/creation metadata. Prices, endpoint capabilities, prompt use, and connected-account entitlements remain unknown unless independently evidenced. A model appearing in the list does not establish zero-price inference. [OpenAI model list](https://developers.openai.com/api/reference/resources/models/methods/list)

Completions.me is excluded from built-in active discovery, cached-model selection, generated routes, standalone route admission, and browser dispatch. The OmniRoute maintainer reported that authenticated requests across advertised models returned canned lyrics with zero token usage and removed the provider. A later request to re-add it was closed with the same conclusion. This exclusion follows those specific recorded observations and does not assert motives or broader facts about the service. Saved browser credentials remain available for removal by their owner. A custom configuration using an excluded alias yields no discovered models or routes. [Maintainer investigation](https://github.com/diegosouzapw/OmniRoute/discussions/3293), [Later upstream decision](https://github.com/cheaper-inference/OmniRoute/issues/10646)

A Vertex AI descriptor parses the documented Google publisher catalog at `publishers/google/models` and preserves full model-garden resource names. It rejects other publisher scopes, mixed pages and duplicate resource names. Prices, native protocols, capabilities and project/region serving rights remain unknown. The parser retains version metadata without manufacturing an inference ID or appending an inferred version. Complete snapshots must have no remaining page token. `GOOGLE_APPLICATION_CREDENTIALS` identifies the standard ADC configuration source, and this offline descriptor does not read or authenticate it. [Publisher list contract](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/publishers.models/list), [Publisher resource](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/publishers.models)

No new descriptors are added for the dedicated Codestral endpoint, GLHF, Hyperbolic, or Yandex in this change. Mistral's documented model list is already supported, but a dedicated Codestral-key list contract was not established. The GLHF schema located in this review was an explicitly third-party profile. Current Hyperbolic documentation did not establish a model-list contract. The inspected Yandex first-party text-generation API documentation did not establish a general model-list response contract. These discovery gaps retain their existing account and price uncertainty.

## Yandex and Hyperbolic discovery

Yandex snapshots require an independently supplied `expectedFolder`; every model URI must match that folder. Import cache identities include the folder. This is scope evidence, not account authorization or pricing evidence. Hyperbolic discovery uses its documented current authenticated model-list endpoint. Both providers retain unknown pricing, privacy and entitlement and are not admitted as free from catalog data alone.
