# LLM Fallbacks

[![Python Package](https://github.com/bodecloud/llm_fallbacks/actions/workflows/python-package.yml/badge.svg)](https://github.com/bodecloud/llm_fallbacks/actions/workflows/python-package.yml)
[![Daily Config Update](https://github.com/bodecloud/llm_fallbacks/actions/workflows/daily-config-update.yml/badge.svg)](https://github.com/bodecloud/llm_fallbacks/actions/workflows/daily-config-update.yml)
[![GitHub Pages](https://img.shields.io/badge/chat-GitHub%20Pages-blue)](https://bodencrouch.github.io/llm_fallbacks/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Pick a model. If it fails, try the next one. This library ranks free LLM models and builds fallback chains on top of [LiteLLM](https://github.com/BerriAI/litellm).

## What you get

- **Fallback chains** — When one model or provider fails, the next one is tried automatically.
- **Model lists** — Filter by cost, context length, vision, tools, and more.
- **Quality scores** — Free models ranked by what they support (not benchmark scores).
- **Daily updates** — JSON and YAML lists refresh every night via GitHub Actions.
- **Live chat demo** — Try it in your browser at [GitHub Pages](https://bodencrouch.github.io/llm_fallbacks/).
- **Desktop explorer** — Browse models with `python -m llm_fallbacks`.

## Install

```bash
pip install llm-fallbacks
```

## Quick start

```python
from llm_fallbacks import get_chat_models, filter_models, get_fallback_list

chat_models = get_chat_models()
print(f"Found {len(chat_models)} chat models")

vision_models = filter_models(
    model_type="chat",
    supports_vision=True,
    max_cost_per_token=0.001,
)
print(f"Found {len(vision_models)} vision models under $0.001/token")

fallbacks = get_fallback_list("chat")
print(f"Fallback order: {fallbacks}")
```

## Run your own gateway

Host an OpenAI-compatible proxy with a `free` model alias (ranked fallback chain):

```bash
cp deploy/.env.example deploy/.env
# Set LITELLM_MASTER_KEY and OPENROUTER_API_KEY in deploy/.env

docker compose -f deploy/docker-compose.yml --env-file deploy/.env up --build
```

See [`deploy/README.md`](deploy/README.md) for smoke tests, env vars, and the difference between `free` and `openrouter/free`.

## Model lists (`configs/`)

Files in `configs/` update daily at midnight UTC. Fetch them from GitHub or generate locally.

| File | What it is |
|------|------------|
| [`free_models.json`](configs/free_models.json) | Free models sorted by quality score, with capabilities |
| [`free_models_ids.txt`](configs/free_models_ids.txt) | One model ID per line, same order as JSON |
| [`all_models.json`](configs/all_models.json) | Full model-id → spec map |
| [`custom_providers.json`](configs/custom_providers.json) | Custom provider configs |
| [`provider_urls.json`](configs/provider_urls.json) | Provider → OpenAI-compatible base URL |
| [`litellm_config.yaml`](configs/litellm_config.yaml) | LiteLLM proxy config (all models) |
| [`litellm_config_free.yaml`](configs/litellm_config_free.yaml) | LiteLLM proxy config (free models only) |

### OmniRoute proposals

The `llm_fallbacks.omniroute` module turns this catalog into reviewable,
purpose-named OmniRoute combo proposals. It requires a separate access manifest
with recent evidence for each exact model and provider: connection, zero-price
dimensions, cost boundary, endpoint, privacy, and successful requests. Agent
routes also require verified tool support. The [OmniRoute guide](docs/omniroute.md)
describes the manifest and command. Keep credentials out of the manifest.

The output is a proposal, not a deployment or a billing guarantee. The catalog's
ranking measures advertised capabilities; it is not a benchmark or proof of
access. Start with the empty [access manifest](configs/omniroute-access.example.json);
it produces no routes until you add verified targets. Confirm runtime permissions,
current pricing, privacy, and failover before importing a proposal. Long chains are
bounded by the router's attempt and time limits, and the output reports eligible
targets beyond the attempt budget.

**Stable raw URLs:**

```
https://raw.githubusercontent.com/bodecloud/llm_fallbacks/main/configs/free_models.json
https://raw.githubusercontent.com/bodecloud/llm_fallbacks/main/configs/free_models_ids.txt
```

**Python:**

```python
import json
import urllib.request

url = "https://raw.githubusercontent.com/bodecloud/llm_fallbacks/main/configs/free_models.json"
with urllib.request.urlopen(url) as resp:
    free_models = json.loads(resp.read())

for model in free_models[:5]:
    print(f"{model['id']:50s}  quality={model['quality_score']:.1f}  mode={model['mode']}")
```

**curl:**

```bash
curl -s https://raw.githubusercontent.com/bodecloud/llm_fallbacks/main/configs/free_models_ids.txt
curl -s https://raw.githubusercontent.com/bodecloud/llm_fallbacks/main/configs/free_models.json | python3 -m json.tool | head -30
```

### Quality scoring

Each free model in `free_models.json` has a `quality_score` (0–100) from a deterministic heuristic (`heuristic_v1`). It measures **capabilities**, not answer quality.

| Factor | Max points | What it measures |
|--------|-----------|------------------|
| Context window | 30 | Larger context → more points |
| Max output tokens | 10 | Larger output window |
| Function calling | 10 | Tool use support |
| Vision | 8 | Image input |
| Response schema | 7 | Structured output |
| Tool choice | 5 | Tool choice parameter |
| System messages | 5 | System role support |
| Parallel function calling | 5 | Parallel tool calls |
| Prompt caching | 3 | Prompt caching |
| Audio input / output | 3 each | Audio support |
| PDF input | 3 | PDF support |
| Assistant prefill | 3 | Assistant prefill |

### Free providers we track

We track 20+ free-tier providers. **Check each provider's site for current limits** — quotas change often.

| Provider | Free tier (approx.) | Sign-up |
|----------|---------------------|---------|
| [OpenRouter](https://openrouter.ai) | 50 req/day, 24+ free models | No card |
| [Groq](https://console.groq.com) | 30–60 RPM, Llama 3.3 70B | No card |
| [Cerebras](https://cloud.cerebras.ai) | 30 RPM, 1M tokens/day | No card |
| [Google AI Studio](https://aistudio.google.com) | 250K TPM, Gemini | No card |
| [Mistral](https://console.mistral.ai) | 1B tokens/month | Phone verify |
| [DeepSeek](https://platform.deepseek.com) | V3, R1 | No card |
| [Together AI](https://api.together.xyz) | $5 credits | No card |
| [Fireworks AI](https://fireworks.ai) | 10 RPM free tier | No card |
| [SambaNova](https://cloud.sambanova.ai) | $5 credits | No card |
| [NVIDIA NIM](https://build.nvidia.com) | 40 RPM, 1K credits | No card |
| [Cohere](https://cohere.com) | 1K req/month | No card |
| [GitHub Models](https://github.com/marketplace/models) | 50–150 req/day | GitHub account |
| [HuggingFace](https://huggingface.co) | 300+ models | No card |
| + Novita, Hyperbolic, Nebius, GLHF, Featherless, Chutes, Completions.me | | |

Set provider API keys as repo secrets to enrich the daily model list. The generator works without keys using LiteLLM's public registry plus OpenRouter when configured.

## Generate configs locally

```bash
python -m llm_fallbacks.generate_configs --output-dir configs

OPENROUTER_API_KEY=your-key python -m llm_fallbacks.generate_configs --output-dir configs
```

## Desktop model explorer

```bash
python -m llm_fallbacks
```

## API reference

### Core functions

- `get_chat_models()` — All chat models
- `get_completion_models()` — Completion models
- `get_embedding_models()` — Embedding models
- `get_image_generation_models()` — Image generation models
- `get_audio_transcription_models()` — Audio transcription models
- `get_audio_speech_models()` — Text-to-speech models
- `get_moderation_models()` — Moderation models
- `get_rerank_models()` — Rerank models
- `get_vision_models()` — Vision-capable models
- `get_function_calling_models()` — Function-calling models
- `get_parallel_function_calling_models()` — Parallel tool-call models
- `get_image_input_models()` — Image input models
- `get_audio_input_models()` — Audio input models
- `get_audio_output_models()` — Audio output models
- `get_pdf_input_models()` — PDF input models
- `get_models()` — All models
- `get_fallback_list(model_type)` — Fallback order for a model type
- `filter_models(model_type, **kwargs)` — Filter by criteria
- `calculate_cost_per_token(model_spec)` — Approximate cost per token

### Filtering examples

```python
from llm_fallbacks import filter_models

free_vision = filter_models(
    model_type="chat",
    free_only=True,
    supports_vision=True,
)

long_context = filter_models(
    model_type="chat",
    min_context_length=16000,
)

openai_only = filter_models(
    model_type="chat",
    provider="openai",
)
```

## Contributing

Pull requests welcome.

## License

MIT — see [LICENSE](LICENSE).

### OmniRoute catalog and sorting

Set `OMNIROUTE_BASE_URL` and optionally `OMNIROUTE_API_KEY` to use the live OmniRoute catalog in existing model filters. Exact gateway IDs and metadata are preserved. A configured gateway error is surfaced so a different catalog cannot silently replace it.

For a Python-only catalog sort, run `python -m llm_fallbacks.omniroute` (or add `--live-catalog`) with those environment variables, or call `get_omniroute_models` and `sort_omniroute_models` directly. This path uses the standard library. It sorts only the listing. OmniRoute owns provider selection, combo targets and failover execution. Entries with unknown prices sort after entries with advertised prices.

The existing `--catalog`, `--access`, `--as-of` and `--output` arguments select the offline proposal mode described above. Importing either adapter remains lazy; the live catalog is fetched only when requested.
