"""AI provider registry.

``AI_PROVIDER`` selects the primary; ``AI_FALLBACK_PROVIDER`` an optional second
choice. When nothing is configured the coach falls back to deterministic
templates, so the product always works.
"""

from __future__ import annotations

from app.config import AI_FALLBACK_PROVIDER, AI_PROVIDER
from app.services.ai.base import (
    CoachProvider,
    ProviderError,
    ProviderResponse,
    parse_json_payload,
    redact,
)
from app.services.ai.providers import AnthropicProvider, GeminiProvider, OpenAIProvider

PROVIDER_CLASSES = {
    "claude": AnthropicProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gpt": OpenAIProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
}

__all__ = [
    "CoachProvider",
    "ProviderError",
    "ProviderResponse",
    "build_provider",
    "configured_providers",
    "parse_json_payload",
    "provider_chain",
    "redact",
]


def build_provider(name: str, model: str | None = None, api_key: str | None = None):
    provider_class = PROVIDER_CLASSES.get((name or "").strip().lower())
    if provider_class is None:
        return None
    return provider_class(model=model, api_key=api_key)


def provider_chain() -> list:
    """Primary then fallback, filtered to providers that actually have credentials."""
    chain = []
    for name in (AI_PROVIDER, AI_FALLBACK_PROVIDER):
        if not name:
            continue
        provider = build_provider(name)
        if provider is not None and provider.is_configured():
            if all(existing.name != provider.name for existing in chain):
                chain.append(provider)
    return chain


def configured_providers() -> list[str]:
    seen = []
    for name, provider_class in PROVIDER_CLASSES.items():
        provider = provider_class()
        if provider.is_configured() and provider.name not in seen:
            seen.append(provider.name)
    return seen
