"""Offline parsers and documentation-backed provider discovery descriptors."""

from __future__ import annotations

import json
import math
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

RETIRED_PROVIDER_IDS = frozenset({"github", "github_models"})
UNVERIFIED_INFERENCE_PROVIDER_IDS = frozenset({"completions", "completions_me", "completions-me", "completions.me"})
EXCLUDED_PROVIDER_IDS = RETIRED_PROVIDER_IDS | UNVERIFIED_INFERENCE_PROVIDER_IDS


def is_retired_provider(provider: Any, model_id: str = "") -> bool:
    """Recognize the retired GitHub Models service independently of Copilot."""
    name = str(provider or "").strip().casefold()
    if name:
        return name in RETIRED_PROVIDER_IDS
    return model_id.partition("/")[0].strip().casefold() in RETIRED_PROVIDER_IDS


def is_excluded_provider(provider: Any, model_id: str = "") -> bool:
    """Exclude retired services and providers lacking verified real inference."""
    name = str(provider or "").strip().casefold()
    if name:
        return name in EXCLUDED_PROVIDER_IDS
    return model_id.partition("/")[0].strip().casefold() in EXCLUDED_PROVIDER_IDS


PROVIDER_CATALOGS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models_url": "https://api.openai.com/v1/models",
        "schema": "openai",
        "auth_env": "OPENAI_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://developers.openai.com/api/reference/resources/models/methods/list",
    },
    "vertexai": {
        "base_url": "https://us-central1-aiplatform.googleapis.com/v1",
        "models_url": "https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models",
        "schema": "vertex_publisher",
        "auth_env": "GOOGLE_APPLICATION_CREDENTIALS",
        "auto_fetch_models": False,
        "catalog_scope": "publishers/google",
        "docs": "https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/publishers.models/list",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models_url": "https://openrouter.ai/api/v1/models",
        "schema": "openai",
        "auth_env": "OPENROUTER_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://openrouter.ai/docs/api-reference/list-available-models",
    },
    "kilo": {
        "base_url": "https://ai-gateway.kilo.ai/api/v1",
        "models_url": "https://ai-gateway.kilo.ai/api/v1/models",
        "schema": "openai",
        "auth_env": "KILO_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://kilo.ai/docs/gateway/api-reference",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models_url": "https://api.groq.com/openai/v1/models",
        "schema": "openai",
        "auth_env": "GROQ_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://console.groq.com/docs/models",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "models_url": "https://api.cerebras.ai/v1/models",
        "schema": "openai",
        "auth_env": "CEREBRAS_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://inference-docs.cerebras.ai/api-reference/models/list-models",
    },
    "google_ai_studio": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "schema": "gemini",
        "auth_env": "GOOGLE_AI_STUDIO_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://ai.google.dev/api/models",
    },
    "huggingface": {
        "base_url": "https://router.huggingface.co/v1",
        "models_url": "https://router.huggingface.co/v1/models",
        "schema": "openai",
        "auth_env": "HUGGINGFACE_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://huggingface.co/docs/inference-providers/hub-api",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "models_url": "https://api.mistral.ai/v1/models",
        "schema": "mistral",
        "auth_env": "MISTRAL_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.mistral.ai/api/endpoint/models",
    },
    "cohere": {
        "base_url": "https://api.cohere.com/v2",
        "models_url": "https://api.cohere.com/v1/models",
        "schema": "cohere",
        "auth_env": "COHERE_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.cohere.com/v2/reference/list-models",
    },
    "nvidia_nim": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models_url": "https://integrate.api.nvidia.com/v1/models",
        "schema": "openai",
        "auth_env": "NVIDIA_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.api.nvidia.com/nim/reference/llm-apis",
    },
    "together_ai": {
        "base_url": "https://api.together.xyz/v1",
        "models_url": "https://api.together.xyz/v1/models",
        "schema": "together",
        "auth_env": "TOGETHER_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.together.ai/docs/serverless/models",
    },
    'fireworks_ai': {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "models_url": "https://api.fireworks.ai/v1/accounts/fireworks/models",
        "schema": "fireworks",
        "auth_env": "FIREWORKS_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.fireworks.ai/api-reference/list-models",
    },
    'sambanova': {
        "base_url": "https://api.sambanova.ai/v1",
        "models_url": "https://api.sambanova.ai/v1/models",
        "schema": "sambanova",
        "auth_env": "SAMBANOVA_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.sambanova.ai/docs/api-reference/models/get-environments-available-model-list-metadata",
    },
    'nebius': {
        "base_url": "https://api.tokenfactory.nebius.com/v1",
        "models_url": "https://api.tokenfactory.nebius.com/v1/models?verbose=true",
        "schema": "nebius",
        "auth_env": "NEBIUS_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.tokenfactory.nebius.com/api-reference/models/list-models",
    },
    "novita": {
        "base_url": "https://api.novita.ai/v3/openai",
        "models_url": "https://api.novita.ai/v3/openai/models",
        "schema": "novita",
        "auth_env": "NOVITA_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://docs.novita.ai/api-reference/model-apis-llm-list-models",
    },
    "featherless": {
        "base_url": "https://api.featherless.ai/v1",
        "models_url": "https://api.featherless.ai/v1/models?all=true",
        "schema": "featherless",
        "auth_env": "FEATHERLESS_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://featherless.ai/docs/api-reference-models",
    },
    "chutes": {
        "base_url": "https://llm.chutes.ai/v1",
        "models_url": "https://llm.chutes.ai/v1/models",
        "schema": "chutes",
        "auth_env": "CHUTES_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://www.chutes.ai/docs/help/faq",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "models_url": "https://api.deepseek.com/models",
        "schema": "deepseek",
        "auth_env": "DEEPSEEK_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://api-docs.deepseek.com/api/list-models/",
    },
    "opencode_zen": {
        "base_url": "https://opencode.ai/inference",
        "models_url": "https://opencode.ai/inference/v1/models",
        "schema": "opencode",
        "auth_env": "OPENCODE_API_KEY",
        "auto_fetch_models": False,
        "docs": "https://opencode.ai/docs/console/api/inference",
    },
    "hyperbolic": {
        "base_url": "https://api.hyperbolic.ai/inference/v1",
        "models_url": "https://api.hyperbolic.ai/inference/v1/models",
        "schema": "hyperbolic",
        "auth_env": "HYPERBOLIC_API_KEY",
        "auth_scheme": "Bearer",
        "auto_fetch_models": False,
        "docs": "https://www.hyperbolic.ai/docs/inference/text-apis#list-models",
    },
    "yandex": {
        "base_url": "https://ai.api.cloud.yandex.net/v1",
        "models_url": "https://ai.api.cloud.yandex.net/v1/models",
        "schema": "yandex_scoped",
        "auth_env": "YANDEX_API_KEY",
        "auth_scheme": "Api-Key",
        "scope_env": "YANDEX_FOLDER_ID",
        "scope_header": "x-project",
        "required_api_key_scope": "yc.ai.models.viewer",
        "required_service_account_role": "ai.languageModels.user",
        "auto_fetch_models": False,
        "docs": "https://aistudio.yandex.ru/en/docs/ai-studio/operations/models/get",
    },
}
PRICE_FIELDS = {
    "prompt": "input_cost_per_token",
    "completion": "output_cost_per_token",
    "image": "input_cost_per_image",
    "request": "input_cost_per_query",
    "input_cache_read": "cache_read_input_token_cost",
    "input_cache_write": "cache_creation_input_token_cost",
}
MODES = {
    "chat",
    "responses",
    "completion",
    "embedding",
    "image_generation",
    "image_edit",
    "audio_transcription",
    "audio_speech",
    "video_generation",
    "moderation",
    "rerank",
    "search",
}
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_NUMBER_CHARS = 256
MAX_NUMBER_EXPONENT = 100_000


def _snapshot_decimal_literal(value: str) -> str:
    """Keep provider decimal lexemes exact within a bounded numeric envelope."""
    if len(value) > MAX_NUMBER_CHARS:
        raise ValueError("Provider decimal literal exceeds the size limit")
    _, separator, exponent = value.lower().partition("e")
    if separator and (len(exponent.lstrip("+-")) > 6 or abs(int(exponent)) > MAX_NUMBER_EXPONENT):
        raise ValueError("Provider decimal exponent exceeds the limit")
    return value


def _reject_snapshot_constant(value: str):
    raise ValueError(f"Nonstandard provider numeric constant: {value}")


def _snapshot_integer_literal(value: str) -> int:
    _snapshot_decimal_literal(value)
    return int(value)


def decode_provider_snapshot(raw: bytes):
    """Decode saved provider JSON without rounding a positive price to zero."""
    if not isinstance(raw, bytes) or len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Provider snapshot must contain at most 16 MiB of bytes")
    return json.loads(
        raw,
        parse_float=_snapshot_decimal_literal,
        parse_int=_snapshot_integer_literal,
        parse_constant=_reject_snapshot_constant,
    )


def _positive_integer(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _openai_spec(provider: str, row: dict[str, Any]) -> dict[str, Any]:
    spec = {"litellm_provider": provider, "upstream_model": row["id"], "mode": "unknown"}
    prices = row.get("pricing")
    evidence = {
        "source": "provider-model-catalog",
        "availability": "listed",
        "reported_prices": prices if isinstance(prices, dict) else None,
    }
    spec["pricing_evidence"] = evidence
    if isinstance(prices, dict):
        for source, destination in PRICE_FIELDS.items():
            if source not in prices or type(prices[source]) not in (str, int, float):
                continue
            try:
                amount = Decimal(str(prices[source]))
            except InvalidOperation:
                continue
            if amount.is_finite() and amount >= 0:
                spec[destination] = float(amount)
    architecture = row.get("architecture", {})
    top = row.get("top_provider", {})
    if not isinstance(architecture, dict):
        architecture = {}
    if not isinstance(top, dict):
        top = {}
    inputs = architecture.get("input_modalities", [])
    outputs = architecture.get("output_modalities", [])
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise ValueError("Model modalities must be arrays")
    legacy_modes = {
        "text+image->text": "chat",
        "text->text": "chat",
        "text->image": "image_generation",
        "text->embedding": "embedding",
        "audio->text": "audio_transcription",
    }
    if row.get("mode") in MODES:
        spec["mode"] = row["mode"]
    elif architecture.get("modality") in legacy_modes:
        spec["mode"] = legacy_modes[architecture["modality"]]
    elif outputs == ["image"] and "text" in inputs:
        spec["mode"] = "image_generation"
    elif outputs == ["embedding"] and "text" in inputs:
        spec["mode"] = "embedding"
    elif outputs == ["text"] and inputs == ["audio"]:
        spec["mode"] = "audio_transcription"
    elif outputs == ["text"] and "text" in inputs:
        spec["mode"] = "chat"
    parameters = row.get("supported_parameters", [])
    if not isinstance(parameters, list) or not all(isinstance(value, str) for value in parameters):
        raise ValueError("Model supported_parameters must be a string array")
    for capability, parameter in (
        ("supports_function_calling", "tools"),
        ("supports_tool_choice", "tool_choice"),
        ("supports_response_schema", "structured_outputs"),
    ):
        if "supported_parameters" in row:
            spec[capability] = parameter in parameters
    if "image" in inputs or architecture.get("modality") == "text+image->text":
        spec["supports_vision"] = True
    if "audio" in inputs:
        spec["supports_audio_input"] = True
    context = (
        _positive_integer(top.get("context_length"))
        or _positive_integer(row.get("context_length"))
        or _positive_integer(row.get("context_window"))
    )
    output = _positive_integer(top.get("max_completion_tokens")) or _positive_integer(row.get("max_completion_tokens"))
    if context:
        spec["max_input_tokens"] = context
    if output:
        spec["max_output_tokens"] = output
    if type(row.get("mayTrainOnYourPrompts")) is bool:
        spec["may_train_on_prompts"] = row["mayTrainOnYourPrompts"]
    return spec


def parse_openai_models(
    provider: str, response: dict[str, Any], *, qualify_ids: bool = True
) -> dict[str, dict[str, Any]]:
    """Preserve structured metadata from an OpenAI-compatible models listing."""
    if not isinstance(response, dict) or response.get("links", {}).get("next"):
        raise ValueError("Complete model pagination before importing the snapshot")
    rows = response.get("data")
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Model response must contain a bounded array")
    if "total_count" in response:
        total = response["total_count"]
        if type(total) is not int or total != len(rows):
            raise ValueError("Model total_count must match the complete snapshot")
    result = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"].strip()
            or len(row["id"]) > 500
        ):
            raise ValueError("Model entries require exact string IDs")
        if row.get("active") is False:
            continue
        key = f"{provider}/{row['id']}" if qualify_ids else row["id"]
        if key in result:
            raise ValueError("Duplicate provider model ID")
        result[key] = _openai_spec(provider, row)
    return result


def parse_provider_models(
    provider: str,
    response: dict[str, Any] | list[dict[str, Any]],
    *,
    qualify_ids: bool = True,
    expected_folder: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Parse a saved provider response without inferring free account access."""
    if provider not in PROVIDER_CATALOGS:
        raise ValueError("Unsupported provider or invalid response")
    schema = PROVIDER_CATALOGS[provider]["schema"]
    if schema == "yandex_scoped":
        return _parse_yandex_models(response, expected_folder=expected_folder, qualify_ids=qualify_ids)
    if expected_folder is not None:
        raise ValueError("Folder scope is supported only for the Yandex catalog")
    if schema == "together":
        return _parse_together_models(response, qualify_ids=qualify_ids)
    if not isinstance(response, dict):
        raise ValueError("Provider response must be an object")
    schema_parsers = {
        "hyperbolic": _parse_hyperbolic_models,
        "vertex_publisher": _parse_vertex_publisher_models,
        "mistral": _parse_mistral_models,
        "cohere": _parse_cohere_models,
        "fireworks": _parse_fireworks_models,
        "sambanova": _parse_sambanova_models,
        "nebius": _parse_nebius_models,
        "chutes": _parse_chutes_models,
        "deepseek": _parse_deepseek_models,
        "opencode": _parse_opencode_models,
        "novita": _parse_novita_models,
        "featherless": _parse_featherless_models,
    }
    if schema in schema_parsers:
        return schema_parsers[schema](response, qualify_ids=qualify_ids)
    google = schema == "gemini"
    if not google:
        return parse_openai_models(provider, response, qualify_ids=qualify_ids)
    if response.get("nextPageToken") or response.get("links", {}).get("next"):
        raise ValueError("Complete provider pagination before importing the snapshot")
    rows = response.get("models" if google else "data")
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Model response must contain a bounded array")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Model entries must be objects")
        raw = row.get("name" if google else "id")
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 500:
            raise ValueError("Model entries require exact string IDs")
        if google:
            if not raw.startswith("models/"):
                raise ValueError("Gemini model names must use the documented resource prefix")
            raw = raw.removeprefix("models/")
            spec = {
                "litellm_provider": provider,
                "upstream_model": raw,
                "pricing_evidence": {
                    "source": "provider-model-catalog",
                    "availability": "listed",
                    "reported_prices": None,
                },
            }
            for source, destination in (
                ("inputTokenLimit", "max_input_tokens"),
                ("outputTokenLimit", "max_output_tokens"),
            ):
                if _positive_integer(row.get(source)):
                    spec[destination] = row[source]
            methods = row.get("supportedGenerationMethods", [])
            if not isinstance(methods, list) or not all(isinstance(value, str) for value in methods):
                raise ValueError("Gemini generation methods must be a string array")
            spec["supported_generation_methods"] = methods
        else:
            spec = _openai_spec(provider, row)
        key = f"{provider}/{raw}" if qualify_ids else raw
        if key in result:
            raise ValueError("Duplicate provider model ID")
        result[key] = spec
    return result


def _together_text_prices(pricing: dict[str, Any]) -> dict[str, Any]:
    """Normalize documented text token units and preserve every other quote."""
    result = {}
    for name, value in pricing.items():
        if not isinstance(name, str):
            raise ValueError("Together price field names must be strings")
        if name not in ("input", "output"):
            # Unclassified charges remain visible to the explicit-zero gate.
            result["provider_" + name] = value
            continue
        if value is None:
            result["prompt" if name == "input" else "completion"] = None
            continue
        if type(value) not in (str, int, float):
            raise ValueError("Together token prices must be numeric or unknown")
        try:
            if isinstance(value, str):
                _snapshot_decimal_literal(value)
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Together token prices must be finite and nonnegative")
            # Tuple construction shifts the exponent without context rounding.
            # Arithmetic division can underflow a positive price to zero.
            sign, digits, exponent = amount.as_tuple()
            if not isinstance(exponent, int) or abs(exponent) > MAX_NUMBER_EXPONENT:
                raise ValueError("Together token price exponent exceeds the limit")
            normalized = Decimal((sign, digits, exponent - 6))
            numeric = float(normalized)
            if not math.isfinite(numeric) or (not normalized.is_zero() and numeric == 0):
                raise ValueError("Together token price exceeds finite nonzero numeric representation")
        except (DecimalException, OverflowError, ValueError) as error:
            raise ValueError("Together token price cannot be normalized") from error
        result["prompt" if name == "input" else "completion"] = str(normalized)
    return result


def _parse_together_models(response: Any, *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Parse the SDK's complete bare model list without asserting entitlement."""
    if not isinstance(response, list) or len(response) > 20_000:
        raise ValueError("Together response must be a complete bounded model array")
    normalized = []
    source_by_id = {}
    modes = {
        "chat": "chat",
        "language": "completion",
        "code": "completion",
        "image": "image_generation",
        "embedding": "embedding",
        "moderation": "moderation",
        "rerank": "rerank",
        "transcribe": "audio_transcription",
        "video": "video_generation",
    }
    for row in response:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Together entries require exact string IDs")
        model_id = row["id"]
        if model_id in source_by_id:
            raise ValueError("Duplicate Together model ID")
        pricing = row.get("pricing")
        if pricing is not None and not isinstance(pricing, dict):
            raise ValueError("Together pricing must be an object or unknown")
        model_type = row.get("type")
        if model_type is not None and not isinstance(model_type, str):
            raise ValueError("Together model type must be a string or unknown")
        source_by_id[model_id] = row
        normalized_pricing = pricing
        if model_type in ("chat", "language", "code") and pricing is not None:
            normalized_pricing = _together_text_prices(pricing)
        elif pricing is not None:
            normalized_pricing = {"provider_" + name: value for name, value in pricing.items()}
        normalized.append({**row, "pricing": normalized_pricing, "mode": modes.get(model_type, "unknown")})
    result = parse_openai_models("together_ai", {"data": normalized}, qualify_ids=qualify_ids)
    for spec in result.values():
        source = source_by_id[spec["upstream_model"]]
        spec["pricing_evidence"]["reported_provider_prices"] = source.get("pricing")
        if source.get("type") in ("chat", "language", "code"):
            spec["pricing_evidence"]["token_price_unit"] = "USD per million tokens"
        context = spec.pop("max_input_tokens", None)
        if context:
            spec["context_window"] = context
    return result


def _parse_mistral_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Retain documented model capabilities without assigning an account price."""
    result = parse_openai_models("mistral", response, qualify_ids=qualify_ids)
    seen = set()
    for row in response["data"]:
        if row["id"] in seen:
            raise ValueError("Duplicate Mistral model ID")
        seen.add(row["id"])
        key = f"mistral/{row['id']}" if qualify_ids else row["id"]
        if "archived" in row and type(row["archived"]) is not bool:
            raise ValueError("Mistral archived must be a boolean")
        if row.get("archived") is True:
            result.pop(key, None)
            continue
        if key not in result:
            continue
        capabilities = row.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError("Mistral capabilities must be an object")
        spec = result[key]
        if row["id"].startswith("labs-"):
            # The documented Labs contract does not offer data-collection opt-out.
            spec["may_train_on_prompts"] = True
            spec["privacy_evidence"] = {
                "source": "https://docs.mistral.ai/inference/model-lifecycle",
                "data_collection_opt_out": False,
                "lifecycle": "labs",
            }
        for source, destination in (("function_calling", "supports_function_calling"), ("vision", "supports_vision")):
            if source in capabilities:
                if type(capabilities[source]) is not bool:
                    raise ValueError("Mistral capabilities must contain booleans")
                spec[destination] = capabilities[source]
        if "completion_chat" in capabilities:
            if type(capabilities["completion_chat"]) is not bool:
                raise ValueError("Mistral completion_chat must be a boolean")
            if capabilities["completion_chat"]:
                spec["mode"] = "chat"
        context = _positive_integer(row.get("max_context_length")) or spec.pop("max_input_tokens", None)
        spec.pop("max_input_tokens", None)
        if context:
            # Mistral documents a combined input/output window, not an input allowance.
            spec["context_window"] = context
    return result


def _parse_cohere_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Parse complete Cohere model listings while leaving prices unverified."""
    if response.get("next_page_token"):
        raise ValueError("Complete Cohere pagination before importing the snapshot")
    rows = response.get("models")
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Cohere model response must contain a bounded array")
    normalized = []
    endpoints_by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Cohere model entries must be objects")
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 500:
            raise ValueError("Cohere model entries require exact string names")
        if name in endpoints_by_id:
            raise ValueError("Duplicate Cohere model name")
        if "is_deprecated" in row and type(row["is_deprecated"]) is not bool:
            raise ValueError("Cohere is_deprecated must be a boolean")
        endpoints = row.get("endpoints", [])
        if not isinstance(endpoints, list) or not all(isinstance(value, str) for value in endpoints):
            raise ValueError("Cohere endpoints must be a string array")
        normalized.append({**row, "id": name, "active": row.get("is_deprecated") is not True})
        endpoints_by_id[name] = endpoints
    result = parse_openai_models("cohere", {"data": normalized}, qualify_ids=qualify_ids)
    endpoint_modes = {"chat": "chat", "generate": "completion", "embed": "embedding", "rerank": "rerank"}
    for spec in result.values():
        endpoints = endpoints_by_id[spec["upstream_model"]]
        spec["supported_endpoints"] = endpoints
        context = spec.pop("max_input_tokens", None)
        if context:
            spec["context_window"] = context
        modes = {endpoint_modes[value] for value in endpoints if value in endpoint_modes}
        if len(modes) == 1 and all(value in endpoint_modes for value in endpoints):
            spec["mode"] = modes.pop()
    return result


def _complete_catalog_rows(
    response: dict[str, Any], field: str, total_field: str | None = None, *, max_rows: int = 20_000
) -> list[dict[str, Any]]:
    """Require one complete bounded snapshot, including any pagination markers."""
    links = response.get("links", {})
    if not isinstance(links, dict):
        raise ValueError("Catalog links must be an object")
    for key in ("nextPageToken", "next_page_token", "next"):
        if key in response and response[key] is not None and not isinstance(response[key], str):
            raise ValueError("Catalog pagination tokens must be strings")
    if "has_more" in response and type(response["has_more"]) is not bool:
        raise ValueError("Catalog pagination completion must be a boolean")
    if links.get("next") or any(response.get(key) for key in ("nextPageToken", "next_page_token", "next", "has_more")):
        raise ValueError("Complete provider pagination before importing the snapshot")
    rows = response.get(field)
    if not isinstance(rows, list) or len(rows) > max_rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Model response must contain a bounded object array")
    for total in (total_field, "total_count"):
        if total and total in response and (type(response[total]) is not int or response[total] != len(rows)):
            raise ValueError("Catalog total must match the complete snapshot")
    return rows


def _catalog_identity(row: dict[str, Any], field: str, seen: set[str]) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 500:
        raise ValueError("Model entries require exact string identities")
    if value in seen:
        raise ValueError("Duplicate provider model identity")
    seen.add(value)
    return value


def _parse_vertex_publisher_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Read the Google publisher catalog without inventing a serving identity."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "publisherModels"):
        name = _catalog_identity(row, "name", seen)
        parts = name.split("/")
        if (
            len(parts) != 4
            or parts[:3] != ["publishers", "google", "models"]
            or not parts[3]
            or parts[3] in (".", "..")
            or any(char.isspace() or char in "?#\\" for char in parts[3])
        ):
            raise ValueError("Vertex publisher snapshot must use exact Google publisher model resources")
        version = row.get("versionId")
        if version is not None and (
            not isinstance(version, str) or not version.isascii() or not version.isdecimal() or len(version) > 100
        ):
            raise ValueError("Vertex versionId must be a bounded decimal string")
        actions = row.get("supportedActions")
        if actions is not None and not isinstance(actions, dict):
            raise ValueError("Vertex supportedActions must be an object or unknown")
        spec = _openai_spec("vertexai", {"id": name})
        # Catalog resources describe model-garden entries. Serving endpoints,
        # project/region entitlement, prices and native capabilities are separate.
        spec["catalog_evidence"] = {
            "catalog_scope": "publishers/google",
            "version_id": version,
            "version_state": row.get("versionState"),
            "launch_stage": row.get("launchStage"),
            "supported_actions": actions,
        }
        quotes = {key: row[key] for key in ("pricing", "price", "cost") if key in row}
        spec["pricing_evidence"]["reported_prices"] = quotes or None
        spec["pricing_evidence"]["units_verified"] = False
        key = f"vertexai/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_fireworks_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Read the control-plane resource catalog without guessing SKU prices."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "models", "totalSize"):
        name = _catalog_identity(row, "name", seen)
        parts = name.split("/")
        if (
            len(parts) != 4
            or parts[0] != "accounts"
            or parts[2] != "models"
            or any(
                not part or part in (".", "..") or any(char.isspace() or char in "?#\\" for char in part)
                for part in (parts[1], parts[3])
            )
        ):
            raise ValueError("Fireworks model names must use account/model resource paths")
        spec = _openai_spec("fireworks_ai", {"id": name})
        # This API lists account resources. Serverless support is a separate fact
        # from a usable deployment or account entitlement.
        spec["catalog_evidence"] = {"state": row.get("state"), "serverless_supported": row.get("supportsServerless")}
        for source, destination in (
            ("supportsTools", "supports_function_calling"),
            ("supportsImageInput", "supports_vision"),
        ):
            if source in row:
                if type(row[source]) is not bool:
                    raise ValueError("Fireworks capability declarations must be booleans")
                spec[destination] = row[source]
        if "supportsServerless" in row and type(row["supportsServerless"]) is not bool:
            raise ValueError("Fireworks serverless support must be a boolean")
        context = _positive_integer(row.get("contextLength"))
        if context:
            spec["context_window"] = context
        key = f"fireworks_ai/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_sambanova_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Preserve documented token rates while leaving untyped modes unknown."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        prices = row.get("pricing")
        if prices is not None and not isinstance(prices, dict):
            raise ValueError("SambaNova pricing must be an object")
        normalized: dict[str, Any] = {"id": name}
        if isinstance(prices, dict):
            normalized["pricing"] = {key: prices[key] for key in ("prompt", "completion") if key in prices}
        spec = _openai_spec("sambanova", normalized)
        spec["catalog_evidence"] = {"pricing": prices}
        context = _positive_integer(row.get("context_length"))
        output = _positive_integer(row.get("max_completion_tokens"))
        if context:
            spec["context_window"] = context
        if output:
            spec["max_output_tokens"] = output
        key = f"sambanova/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_nebius_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Read Token Factory metadata without guessing its price units."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        status = row.get("status")
        if status not in (None, "active", "validating", "error", "deleted"):
            raise ValueError("Unknown Nebius model status")
        if status in ("validating", "error", "deleted"):
            continue
        # Only schema-defined fields reach the generic converter. In particular,
        # caller-added mode/privacy/parameter flags cannot fabricate capabilities.
        normalized = {key: row[key] for key in ("id", "pricing", "architecture", "context_length") if key in row}
        if "pricing" in normalized and not isinstance(normalized["pricing"], dict):
            raise ValueError("Nebius pricing must be an object")
        if "architecture" in normalized and not isinstance(normalized["architecture"], dict):
            raise ValueError("Nebius architecture must be an object")
        if "architecture" in normalized:
            normalized["architecture"] = {
                key: value
                for key, value in normalized["architecture"].items()
                if key in ("modality", "tokenizer", "instruct_type")
            }
        features = row.get("supported_features")
        if features is not None and (
            not isinstance(features, list) or not all(isinstance(feature, str) for feature in features)
        ):
            raise ValueError("Nebius supported features must be a string array")
        prices = normalized.pop("pricing", None)
        spec = _openai_spec("nebius", normalized)
        # The published catalog schema names rates without defining their units.
        # Retain those observations without converting them to per-token costs.
        spec["pricing_evidence"]["reported_prices"] = prices
        spec["pricing_evidence"]["units_verified"] = False
        context = spec.pop("max_input_tokens", None)
        if context:
            spec["context_window"] = context
        spec["catalog_evidence"] = {"status": status, "supported_features": features}
        key = f"nebius/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a string array")
    return value


def _declared_modalities(row: dict[str, Any]) -> dict[str, Any]:
    architecture = {}
    for source, destination in (("input_modalities", "input_modalities"), ("output_modalities", "output_modalities")):
        if source in row:
            architecture[destination] = _string_array(row[source], source)
    return architecture


def _parse_chutes_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Normalize the hosted catalog's documented per-million USD quote."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        price = row.get("price")
        if price is not None and not isinstance(price, dict):
            raise ValueError("Chutes price must be an object or unknown")
        alternate = row.get("pricing")
        if alternate is not None and not isinstance(alternate, dict):
            raise ValueError("Chutes alternate pricing must be an object or unknown")
        quoted = {}
        additional_quotes = {}
        if isinstance(price, dict):
            for field, value in price.items():
                if not isinstance(field, str) or not isinstance(value, dict):
                    raise ValueError("Chutes prices require currency quote objects")
                # USD quotes are documented per million tokens. Missing USD
                # and additional charges remain visible to the zero-cost gate.
                quoted[field] = value.get("usd")
                for currency, amount in value.items():
                    if not isinstance(currency, str):
                        raise ValueError("Chutes currency names must be strings")
                    if currency != "usd":
                        # Structured keys preserve arbitrary field/currency pairs
                        # without collisions between separators in either name.
                        identity = json.dumps(["currency", field, currency], ensure_ascii=False, separators=(",", ":"))
                        additional_quotes[identity] = amount
        normalized = {"id": name, "architecture": _declared_modalities(row)}
        spec = _openai_spec("chutes", normalized)
        if price is not None or alternate is not None:
            prices = _together_text_prices(quoted) if price is not None else {}
            if "provider_input_cache_read" in prices:
                cache = _together_text_prices({"input": prices.pop("provider_input_cache_read")})
                prices["input_cache_read"] = cache["prompt"]
            prices.update(additional_quotes)
            if alternate is not None:
                # An undocumented parallel quote cannot override the documented
                # price object or disappear when the primary quote is missing.
                identity = json.dumps(["quote", "pricing"], separators=(",", ":"))
                prices[identity] = alternate
            priced = _openai_spec("chutes", {"id": name, "pricing": prices})
            spec.update({key: value for key, value in priced.items() if key in PRICE_FIELDS.values()})
            spec["pricing_evidence"]["reported_prices"] = prices
        spec["pricing_evidence"]["reported_provider_prices"] = price
        spec["pricing_evidence"]["reported_alternate_prices"] = alternate
        spec["pricing_evidence"]["token_price_unit"] = "USD per million tokens"
        features = _string_array(row.get("supported_features", []), "Chutes supported_features")
        if "supported_features" in row:
            spec["supports_function_calling"] = "tools" in features
            spec["supports_response_schema"] = "structured_outputs" in features
        context = _positive_integer(row.get("context_length")) or _positive_integer(row.get("max_model_len"))
        output = _positive_integer(row.get("max_output_length"))
        if context:
            spec["context_window"] = context
        if output:
            spec["max_output_tokens"] = output
        confidential = row.get("confidential_compute")
        if confidential is not None and type(confidential) is not bool:
            raise ValueError("Chutes confidential_compute must be boolean or unknown")
        spec["catalog_evidence"] = {"confidential_compute": confidential, "supported_features": features}
        key = f"chutes/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_deepseek_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Preserve current DeepSeek metadata without supplying absent prices."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        spec = _openai_spec("deepseek", {"id": name, "architecture": _declared_modalities(row)})
        context = _positive_integer(row.get("context_window"))
        output = _positive_integer(row.get("max_output_tokens"))
        if context:
            spec["context_window"] = context
        if output:
            spec["max_output_tokens"] = output
        effort = row.get("effort")
        if effort is not None:
            if not isinstance(effort, dict):
                raise ValueError("DeepSeek effort must be an object")
            levels = _string_array(effort.get("supported_levels"), "DeepSeek effort levels")
            if effort.get("default_level") is not None and effort["default_level"] not in levels:
                raise ValueError("DeepSeek default effort must be a supported level")
        capabilities = row.get("api_capabilities")
        if capabilities is not None and not isinstance(capabilities, dict):
            raise ValueError("DeepSeek protocol capabilities must be an object")
        spec["catalog_evidence"] = {"effort": effort, "api_capabilities": capabilities}
        key = f"deepseek/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_opencode_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Read discovery metadata while withholding unsupported external free access."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        modalities = row.get("modalities", {})
        limits = row.get("limit", {})
        capabilities = row.get("capabilities", {})
        apis = row.get("api", {})
        if not all(isinstance(value, dict) for value in (modalities, limits, capabilities, apis)):
            raise ValueError("OpenCode model metadata must contain objects")
        normalized = {"id": name}
        modality_row = {key + "_modalities": value for key, value in modalities.items() if key in ("input", "output")}
        normalized["architecture"] = _declared_modalities(modality_row)
        spec = _openai_spec("opencode_zen", normalized)
        for source, destination in (
            ("context", "context_window"),
            ("input", "max_input_tokens"),
            ("output", "max_output_tokens"),
        ):
            if _positive_integer(limits.get(source)):
                spec[destination] = limits[source]
        for source, destination in (("tools", "supports_function_calling"), ("reasoning", "supports_reasoning")):
            if source in capabilities:
                declaration = capabilities[source]
                if not isinstance(declaration, dict) or type(declaration.get("supported")) is not bool:
                    raise ValueError("OpenCode capabilities require explicit supported booleans")
                spec[destination] = declaration["supported"]
        if "structured_output" in capabilities:
            if type(capabilities["structured_output"]) is not bool:
                raise ValueError("OpenCode structured_output must be boolean")
            spec["supports_response_schema"] = capabilities["structured_output"]
        # The model listing's nested prices include protocol and time/context
        # variations. Preserve them without guessing a complete pricing contract.
        cost = row.get("cost")
        if cost is not None and not isinstance(cost, dict):
            raise ValueError("OpenCode cost must be an object or unknown")
        spec["pricing_evidence"]["reported_prices"] = cost
        spec["pricing_evidence"]["units_verified"] = False
        spec["catalog_evidence"] = {
            "api": apis,
            "external_free_chat_access": False,
            "access_source": "https://opencode.ai/docs/console/api/inference",
        }
        key = f"opencode_zen/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_novita_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Preserve Novita discovery without guessing integer or tiered price units."""
    result = {}
    seen: set[str] = set()
    for row in _complete_catalog_rows(response, "data"):
        name = _catalog_identity(row, "id", seen)
        normalized = {"id": name, "architecture": _declared_modalities(row)}
        spec = _openai_spec("novita", normalized)
        # Current public rows have both integer quotes and decimal nested
        # quotes. The model-list reference does not define their currency scale.
        quotes = {
            key: row[key]
            for key in ("input_token_price_per_m", "output_token_price_per_m", "pricing", "is_tiered_billing")
            if key in row
        }
        if "pricing" in row and row["pricing"] is not None and not isinstance(row["pricing"], dict):
            raise ValueError("Novita pricing must be an object or unknown")
        spec["pricing_evidence"]["reported_prices"] = quotes or None
        spec["pricing_evidence"]["units_verified"] = False
        context = _positive_integer(row.get("context_size"))
        output = _positive_integer(row.get("max_output_tokens"))
        if context:
            spec["context_window"] = context
        if output:
            spec["max_output_tokens"] = output
        features = row.get("features")
        endpoints = row.get("endpoints")
        if features is not None:
            _string_array(features, "Novita features")
        if endpoints is not None:
            _string_array(endpoints, "Novita endpoints")
        # Preserve provider declarations without inferring native protocol or
        # account entitlement from a catalog's labels.
        spec["catalog_evidence"] = {
            "features": features,
            "endpoints": endpoints,
            "model_type": row.get("model_type"),
            "status": row.get("status"),
        }
        key = f"novita/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_featherless_models(response: dict[str, Any], *, qualify_ids: bool) -> dict[str, dict[str, Any]]:
    """Read the complete active Featherless catalog, preserving plan uncertainty."""
    result = {}
    seen: set[str] = set()
    # The documented all=true listing currently exceeds the generic 20k cap.
    # Its own bound remains under the shared 16 MiB input envelope.
    for row in _complete_catalog_rows(response, "data", max_rows=50_000):
        name = _catalog_identity(row, "id", seen)
        status = row.get("status")
        if status is not None and status not in ("active", "pending_deploy", "not_deployed"):
            raise ValueError("Unknown Featherless model lifecycle status")
        for flag in ("is_gated", "available_on_current_plan", "vision_supported"):
            if flag in row and type(row[flag]) is not bool:
                raise ValueError("Featherless model flags must be booleans")
        if status in ("pending_deploy", "not_deployed") or row.get("available_on_current_plan") is False:
            continue
        normalized = {"id": name, "architecture": _declared_modalities(row)}
        if "pricing" in row:
            prices = row["pricing"]
            if prices is not None and not isinstance(prices, dict):
                raise ValueError("Featherless pricing must be an object or unknown")
            normalized["pricing"] = prices
        spec = _openai_spec("featherless", normalized)
        if "vision_supported" in row:
            if spec.get("supports_vision") is True and row["vision_supported"] is False:
                raise ValueError("Conflicting Featherless vision declarations")
            spec["supports_vision"] = row["vision_supported"]
        features = row.get("features", {})
        if not isinstance(features, dict):
            raise ValueError("Featherless features must be an object")
        for source, destination in (("tool_use", "supports_function_calling"), ("image_input", "supports_vision")):
            if source in features:
                if type(features[source]) is not bool:
                    raise ValueError("Featherless feature declarations must be booleans")
                if destination in spec and spec[destination] != features[source]:
                    raise ValueError("Conflicting Featherless feature declarations")
                spec[destination] = features[source]
        context = _positive_integer(row.get("context_length"))
        output = _positive_integer(row.get("max_completion_tokens"))
        if context:
            spec["context_window"] = context
        if output:
            spec["max_output_tokens"] = output
        concurrency = row.get("concurrency_cost")
        if concurrency is not None and not _positive_integer(concurrency):
            raise ValueError("Featherless concurrency cost must be a positive integer")
        tasks = row.get("tasks")
        if tasks is not None:
            _string_array(tasks, "Featherless tasks")
        spec["catalog_evidence"] = {
            "status": status,
            "is_gated": row.get("is_gated"),
            "available_on_current_plan": row.get("available_on_current_plan"),
            "model_class": row.get("model_class"),
            "concurrency_cost": concurrency,
            "tasks": tasks,
        }
        key = f"featherless/{name}" if qualify_ids else name
        result[key] = spec
    return result


def _parse_hyperbolic_models(response: dict[str, Any], *, qualify_ids: bool = True) -> dict[str, dict[str, Any]]:
    """Retain documented model IDs while leaving prices and eligibility unknown.

    Callers must use the existing bounded snapshot decoder before this function.
    Unknown envelope fields require review to prevent silent partial imports.
    """
    if not isinstance(response, dict) or set(response) != {"object", "data"} or response.get("object") != "list":
        raise ValueError("A complete documented Hyperbolic list envelope is required")
    rows = response["data"]
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Hyperbolic catalog must contain a bounded model array")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Hyperbolic catalog entries must be objects")
        model_id = row.get("id")
        if (
            not isinstance(model_id, str)
            or not model_id
            or len(model_id) > 500
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in model_id)
        ):
            raise ValueError("Hyperbolic entries require exact model IDs")
        key = f"hyperbolic/{model_id}" if qualify_ids else model_id
        if key in result:
            raise ValueError("Duplicate Hyperbolic model ID")
        result[key] = {
            "litellm_provider": "hyperbolic",
            "upstream_model": model_id,
            "mode": "unknown",
            "pricing_evidence": {"source": "provider-model-catalog", "availability": "listed", "reported_prices": None},
        }
    return result


def _parse_yandex_models(
    response: dict[str, Any], *, expected_folder: str | None, qualify_ids: bool = True
) -> dict[str, dict[str, Any]]:
    """Parse the documented list envelope, retaining unknown access and pricing.

    Callers must use the existing bounded snapshot decoder before this function.
    Folder context is explicit because every documented ID contains that scope.
    Unknown envelope fields require review to prevent silent partial imports.
    """
    if (
        not isinstance(expected_folder, str)
        or not expected_folder
        or len(expected_folder) > 500
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char in "/?#@:%\\" for char in expected_folder)
    ):
        raise ValueError("An exact folder ID is required")
    if not isinstance(response, dict) or set(response) != {"object", "data"} or response.get("object") != "list":
        raise ValueError("A complete documented Yandex list envelope is required")
    rows = response["data"]
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError("Yandex catalog must contain a bounded model array")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("object") != "model":
            raise ValueError("Yandex catalog entries must be model objects")
        model_id = row.get("id")
        if (
            not isinstance(model_id, str)
            or not model_id
            or len(model_id) > 500
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\" for char in model_id)
        ):
            raise ValueError("Yandex model entries require exact URI IDs")
        uri = urlsplit(model_id)
        if (
            uri.scheme not in {"gpt", "emb"}
            or uri.netloc != expected_folder
            or not uri.path.startswith("/")
            or uri.path == "/"
            or uri.query
            or uri.fragment
            or "%" in model_id
        ):
            raise ValueError("Yandex model URI must match its expected folder")
        key = f"yandex/{model_id}" if qualify_ids else model_id
        if key in result:
            raise ValueError("Duplicate Yandex model ID")
        result[key] = {
            "litellm_provider": "yandex",
            "upstream_model": model_id,
            "mode": "unknown",
            "catalog_evidence": {
                "source": "https://aistudio.yandex.ru/en/docs/ai-studio/operations/models/get",
                "scope_type": "folder",
                "folder_id": expected_folder,
                "scope_basis": "caller-expected-folder-matches-model-uri",
            },
            "pricing_evidence": {"source": "provider-model-catalog", "availability": "listed", "reported_prices": None},
        }
    return result


def main():
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(PROVIDER_CATALOGS), required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-folder", help="Required folder scope for a Yandex snapshot")
    args = parser.parse_args()
    if args.provider == "yandex" and args.expected_folder is None:
        parser.error("--expected-folder is required for Yandex snapshots")
    if args.provider != "yandex" and args.expected_folder is not None:
        parser.error("--expected-folder applies only to Yandex snapshots")

    def deny_network(event, _args):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            raise RuntimeError("Provider snapshot parsing is offline")

    sys.addaudithook(deny_network)
    with args.snapshot.open("rb") as source:
        raw = source.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Snapshot exceeds the input size limit")
    result = parse_provider_models(args.provider, decode_provider_snapshot(raw), expected_folder=args.expected_folder)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"Parsed {len(result)} provider model records")


if __name__ == "__main__":
    main()
