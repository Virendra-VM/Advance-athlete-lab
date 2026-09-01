"""Concrete CoachProvider implementations.

Each provider forces JSON output natively where the API supports it, and the
shared parser in ``base.py`` handles the rest.
"""

from __future__ import annotations

import httpx

from app.config import (
    AI_REQUEST_TIMEOUT_S,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from app.services.ai.base import (
    ProviderError,
    ProviderResponse,
    log_exchange,
    parse_json_payload,
)


class AnthropicProvider:
    name = "claude"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or ANTHROPIC_MODEL
        self.api_key = api_key if api_key is not None else ANTHROPIC_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, system: str, user: str) -> ProviderResponse:
        if not self.is_configured():
            raise ProviderError("ANTHROPIC_API_KEY is not set.")
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "temperature": 0.4,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=AI_REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Claude request failed: {exc}") from exc

        payload = response.json()
        blocks = payload.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        log_exchange(self.name, system, user, text)
        return ProviderResponse(
            data=parse_json_payload(text),
            provider=self.name,
            model=self.model,
            raw_text=text,
            usage=payload.get("usage") or {},
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or OPENAI_MODEL
        self.api_key = api_key if api_key is not None else OPENAI_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, system: str, user: str) -> ProviderResponse:
        if not self.is_configured():
            raise ProviderError("OPENAI_API_KEY is not set.")
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=AI_REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        payload = response.json()
        choices = payload.get("choices") or []
        text = choices[0]["message"]["content"] if choices else ""
        log_exchange(self.name, system, user, text)
        return ProviderResponse(
            data=parse_json_payload(text),
            provider=self.name,
            model=self.model,
            raw_text=text,
            usage=payload.get("usage") or {},
        )


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or GEMINI_MODEL
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, system: str, user: str) -> ProviderResponse:
        if not self.is_configured():
            raise ProviderError("GEMINI_API_KEY is not set.")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "responseMimeType": "application/json",
                        "maxOutputTokens": 8192,
                    },
                },
                timeout=AI_REQUEST_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc
        if response.is_error:
            detail = (response.text or "").strip().replace("\n", " ")[:400]
            raise ProviderError(
                f"Gemini {response.status_code} for model '{self.model}': {detail or response.reason_phrase}"
            )

        payload = response.json()
        candidates = payload.get("candidates") or []
        parts = (candidates[0].get("content", {}).get("parts") or []) if candidates else []
        text = "".join(part.get("text", "") for part in parts)
        log_exchange(self.name, system, user, text)
        return ProviderResponse(
            data=parse_json_payload(text),
            provider=self.name,
            model=self.model,
            raw_text=text,
            usage=payload.get("usageMetadata") or {},
        )
