"""LLM factory for creating LLM instances."""

from typing import Optional
from .base import BaseLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM
from ..config import Settings


def create_llm(settings: Settings) -> BaseLLM:
    """Create an LLM instance based on settings.

    Args:
        settings: Application settings

    Returns:
        LLM instance

    Raises:
        ValueError: If provider is unknown
    """
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        return OllamaLLM(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            hide_reasoning=settings.llm_hide_reasoning,
        )
    elif provider in ("openai", "openrouter"):
        return OpenAILLM(
            model=settings.llm_model,
            base_url=settings.llm_base_url if provider != "openai" else None,
            api_key=settings.llm_api_key,
            hide_reasoning=settings.llm_hide_reasoning,
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. Supported: ollama, openai"
        )
