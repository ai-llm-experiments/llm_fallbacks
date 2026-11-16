"""LLM fallback utilities with lazy public exports.

Importing the package or its offline catalog adapter does not initialize
provider discovery. Public library functions load their implementation on use.
"""

from importlib import import_module as _import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_fallbacks.core import (
        calculate_cost_per_token,
        get_audio_input_models,
        get_audio_output_models,
        get_audio_speech_models,
        get_audio_transcription_models,
        get_chat_models,
        get_completion_models,
        get_embedding_models,
        get_fallback_list,
        get_function_calling_models,
        get_image_generation_models,
        get_image_input_models,
        get_litellm_model_specs,
        get_litellm_models,
        get_models,
        get_moderation_models,
        get_parallel_function_calling_models,
        get_pdf_input_models,
        get_rerank_models,
        get_vision_models,
        sort_models_by_cost_and_limits,
    )
    from llm_fallbacks.filter_litellm import filter_models

__version__ = "0.1.0"
__all__ = [
    "calculate_cost_per_token",
    "filter_models",
    "get_audio_input_models",
    "get_audio_output_models",
    "get_audio_speech_models",
    "get_audio_transcription_models",
    "get_chat_models",
    "get_completion_models",
    "get_embedding_models",
    "get_fallback_list",
    "get_function_calling_models",
    "get_image_generation_models",
    "get_image_input_models",
    "get_litellm_model_specs",
    "get_litellm_models",
    "get_models",
    "get_moderation_models",
    "get_parallel_function_calling_models",
    "get_pdf_input_models",
    "get_rerank_models",
    "get_vision_models",
    "sort_models_by_cost_and_limits",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name = "llm_fallbacks.filter_litellm" if name == "filter_models" else "llm_fallbacks.core"
    value = getattr(_import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
