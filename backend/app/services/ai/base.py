"""Provider-agnostic coach interface.

Providers only have to turn (system prompt, user prompt) into parsed JSON. All
domain logic — prompt construction, schema validation, safety gating — lives in
``app/services/coach_ai.py`` so swapping providers costs nothing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b\d{9,}\b"), "[number]"),
]


class ProviderError(RuntimeError):
    """Raised when a provider is unusable (missing key, transport error, bad JSON)."""


@dataclass
class ProviderResponse:
    data: dict
    provider: str
    model: str
    raw_text: str = ""
    usage: dict = field(default_factory=dict)


class CoachProvider(Protocol):
    name: str
    model: str

    def is_configured(self) -> bool:
        ...

    def generate_json(self, system: str, user: str) -> ProviderResponse:
        ...


def redact(text: str) -> str:
    cleaned = text
    for pattern, replacement in PII_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def log_exchange(provider: str, system: str, user: str, output: str) -> None:
    """Debug logging with PII redacted; disabled unless AI_LOG_PROMPTS=true."""
    from app.config import AI_LOG_PROMPTS

    if not AI_LOG_PROMPTS:
        return
    logger.info(
        "[ai:%s] system=%s\nuser=%s\noutput=%s",
        provider,
        redact(system)[:2000],
        redact(user)[:6000],
        redact(output)[:6000],
    )


def parse_json_payload(text: str) -> dict:
    """Parse model output that may be wrapped in prose or a fenced code block."""
    if not text or not text.strip():
        raise ProviderError("Empty response from provider.")

    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise ProviderError("Provider response was not JSON.") from None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Provider response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ProviderError("Provider response JSON was not an object.")
    return parsed
