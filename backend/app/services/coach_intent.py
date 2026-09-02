"""Route coach chat before any autopsy or schedule prompt is built.

Structural matching is the default: it is fast, deterministic, and the thing
that stopped weekly-plan questions from being treated as the last bike file.
A tiny LLM classifier runs only when the scores are close and a provider is
configured. Ambiguous messages fall through to GENERAL_CHAT — never to an autopsy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

WORKOUT_AUDIT = "WORKOUT_AUDIT"
SCHEDULE_UPDATE = "SCHEDULE_UPDATE"
GENERAL_CHAT = "GENERAL_CHAT"

INTENTS = (WORKOUT_AUDIT, SCHEDULE_UPDATE, GENERAL_CHAT)

# Stored on older replies / eval harnesses.
LEGACY_INTENT = {
    "session_analysis": WORKOUT_AUDIT,
    "chat": GENERAL_CHAT,
    "schedule": SCHEDULE_UPDATE,
}

POWER_PASTE_RE = re.compile(
    r"\b(\d{2,4})\s*(w|watts|bpm|rpm|%?\s*ftp)\b",
    re.IGNORECASE,
)
WEEKDAY_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
LAP_RE = re.compile(r"\blaps?\s+\d+", re.IGNORECASE)

AUDIT_HINTS = (
    "how was today",
    "how was this",
    "how did i do",
    "how did i perform",
    "today's ride",
    "todays ride",
    "today's session",
    "todays session",
    "today's workout",
    "today's run",
    "todays run",
    "today's swim",
    "how was the lift",
    "how was yoga",
    "lap by lap",
    "you got it wrong",
    "analyse the workout",
    "analyze the workout",
    "analyse this ride",
    "analyze this ride",
    "autopsy",
    "telemetry",
    "normalized power",
    "functional threshold",
    "over-under",
    "over under",
    "overunder",
    "main set",
    "repeat this set",
    "match my workout",
)

SCHEDULE_HINTS = (
    "adjust this week",
    "this week's plan",
    "this weeks plan",
    "weekly plan",
    "week plan",
    "training plan",
    "weekly schedule",
    "my schedule",
    "planned this week",
    "plan this week",
    "revise my week",
    "revise the week",
    "rewrite my week",
    "change my week",
    "modify my week",
    "update my week",
    "update my schedule",
    "change my plan",
    "modify my plan",
    "move the long",
    "swap my",
    "rest day",
    "what should i do this week",
    "plan my week",
    "build my week",
)

CLASSIFIER_SYSTEM = """You classify athlete coach-chat messages. Reply with JSON only.
Choose exactly one intent:
- WORKOUT_AUDIT: asking about a specific past session's performance, laps, watts, or "how was today".
- SCHEDULE_UPDATE: proposing, asking to see, or asking to change this week's training plan.
- GENERAL_CHAT: sports science, recovery questions, casual chat. Default here if unsure.
Never pick WORKOUT_AUDIT just because the athlete trains or mentions a bike."""

CLASSIFIER_SCHEMA = """{"intent": "WORKOUT_AUDIT|SCHEDULE_UPDATE|GENERAL_CHAT"}"""


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    source: str
    audit_score: int = 0
    schedule_score: int = 0


def normalize_intent(value: str | None) -> str:
    raw = (value or "").strip()
    if raw in INTENTS:
        return raw
    return LEGACY_INTENT.get(raw.lower(), GENERAL_CHAT)


def classify_chat_intent(
    message: str,
    *,
    activity_id: int | None = None,
    use_llm: bool = True,
) -> str:
    """Public router. Returns one of WORKOUT_AUDIT, SCHEDULE_UPDATE, GENERAL_CHAT."""
    return classify_chat_intent_detailed(
        message, activity_id=activity_id, use_llm=use_llm
    ).intent


def classify_chat_intent_detailed(
    message: str,
    *,
    activity_id: int | None = None,
    use_llm: bool = True,
) -> IntentDecision:
    if activity_id:
        return IntentDecision(
            intent=WORKOUT_AUDIT,
            confidence=1.0,
            source="activity_id",
            audit_score=10,
        )
    structural = _classify_structural(message)
    if structural.confidence >= 0.7 or not use_llm:
        return structural
    llm_intent = _classify_with_llm(message)
    if llm_intent:
        return IntentDecision(
            intent=llm_intent,
            confidence=0.8,
            source="llm",
            audit_score=structural.audit_score,
            schedule_score=structural.schedule_score,
        )
    # Fail open to the structural winner. Never invent an autopsy.
    if structural.intent == WORKOUT_AUDIT and structural.confidence < 0.7:
        return IntentDecision(
            intent=GENERAL_CHAT,
            confidence=0.4,
            source="ambiguous_default",
            audit_score=structural.audit_score,
            schedule_score=structural.schedule_score,
        )
    return structural


def _classify_structural(message: str) -> IntentDecision:
    text = (message or "").strip().lower()
    if not text:
        return IntentDecision(GENERAL_CHAT, 1.0, "empty")

    audit = 0
    schedule = 0

    if any(hint in text for hint in AUDIT_HINTS):
        audit += 3
    if POWER_PASTE_RE.search(text) and ("ftp" in text or "lap" in text or len(message) >= 280):
        audit += 3
    if LAP_RE.search(text) and POWER_PASTE_RE.search(text):
        audit += 3
    if re.search(r"\b(how was|analyse|analyze)\b", text) and re.search(
        r"\b(ride|run|swim|session|workout|trainer|whoosh|lift|gym|yoga|mobility)\b",
        text,
    ):
        audit += 2

    if any(hint in text for hint in SCHEDULE_HINTS):
        schedule += 3
    if "schedule" in text and "match my workout" not in text:
        schedule += 2
    weekdays = {match.group(1).lower() for match in WEEKDAY_RE.finditer(text)}
    if len(weekdays) >= 3:
        schedule += 3
    elif len(weekdays) == 2:
        schedule += 1
    if re.search(r"\b(this week|next week|weekly)\b", text) and re.search(
        r"\b(plan|schedule|adjust|change|modify|train|session)\b",
        text,
    ):
        schedule += 2

    # A past-session correction that also mentions the week plan is still an autopsy.
    if audit >= 3 and schedule >= 2 and (
        LAP_RE.search(text) or "analyse" in text or "analyze" in text or "you got it wrong" in text
    ):
        return IntentDecision(WORKOUT_AUDIT, 0.9, "structural_audit_overrides_schedule", audit, schedule)

    if schedule >= 3 and schedule > audit:
        confidence = 0.92 if schedule >= 5 else 0.8
        return IntentDecision(SCHEDULE_UPDATE, confidence, "structural", audit, schedule)
    if audit >= 3 and audit >= schedule:
        confidence = 0.92 if audit >= 5 else 0.8
        return IntentDecision(WORKOUT_AUDIT, confidence, "structural", audit, schedule)
    if schedule > 0 and schedule >= audit:
        return IntentDecision(SCHEDULE_UPDATE, 0.55, "structural_weak", audit, schedule)
    if audit > 0:
        return IntentDecision(WORKOUT_AUDIT, 0.55, "structural_weak", audit, schedule)
    return IntentDecision(GENERAL_CHAT, 0.85, "structural_default", audit, schedule)


def _classify_with_llm(message: str) -> str | None:
    try:
        from app.services.ai import ProviderError, provider_chain
    except Exception:  # noqa: BLE001 — classifier must never break chat
        return None
    chain = provider_chain()
    if not chain:
        return None
    user = (
        f"ATHLETE MESSAGE\n{(message or '').strip()[:2000]}\n\n"
        f"TASK\nClassify intent.\n\nRespond with JSON matching exactly this shape:\n{CLASSIFIER_SCHEMA}"
    )
    try:
        response = chain[0].generate_json(CLASSIFIER_SYSTEM, user)
    except ProviderError as exc:
        logger.info("Intent LLM classifier skipped: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("Intent LLM classifier failed: %s", exc)
        return None
    raw = (response.data or {}).get("intent")
    intent = normalize_intent(str(raw) if raw else "")
    if intent in INTENTS:
        return intent
    return None
