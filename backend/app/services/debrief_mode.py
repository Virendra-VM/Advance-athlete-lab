"""Phase 3 — quick debrief vs full session autopsy."""

from __future__ import annotations

import re
from typing import Any

from app.services.session_plan import collect_prescription_text, parse_prescribed_workout

DEBRIEF_QUICK = "quick"
DEBRIEF_FULL = "full"

_FULL_HINTS = (
    "deep dive",
    "full breakdown",
    "full autopsy",
    "full analysis",
    "detailed analysis",
    "analyze laps",
    "analyse laps",
    "lap by lap",
    "lap-by-lap",
    "every lap",
    "telemetry audit",
    "break down laps",
    "breakdown of laps",
    "mechanical precision",
)

_QUICK_HINTS = (
    "quick debrief",
    "short debrief",
    "brief debrief",
    "quick summary",
    "quick read",
)

_HOW_WAS_RE = re.compile(
    r"\bhow was\b|\bhow did i do\b|\bhow did today\b|\bgive me a (?:quick )?debrief\b",
    re.IGNORECASE,
)


def message_has_pasted_prescription(message: str, history: list[dict] | None = None) -> bool:
    text = collect_prescription_text(message, history)
    return parse_prescribed_workout(text) is not None


def session_needs_interval_audit(session_packet: dict[str, Any] | None) -> bool:
    if not session_packet:
        return False
    overlay = session_packet.get("prescribed_vs_executed") or {}
    if overlay.get("aligned") or overlay.get("vo2_caps"):
        return True
    if overlay.get("key_laps") and overlay.get("hit_rate") is not None:
        return True
    if session_packet.get("prescription"):
        return True
    return False


def resolve_debrief_mode(
    message: str,
    *,
    history: list[dict] | None = None,
    session_packet: dict[str, Any] | None = None,
) -> str:
    """Default quick debrief; full autopsy only when the athlete asks for depth."""
    text = (message or "").strip()
    lower = text.lower()

    if any(hint in lower for hint in _FULL_HINTS):
        return DEBRIEF_FULL
    if "autopsy" in lower and "quick" not in lower:
        return DEBRIEF_FULL
    if message_has_pasted_prescription(text, history):
        return DEBRIEF_FULL
    if session_needs_interval_audit(session_packet):
        return DEBRIEF_FULL

    if any(hint in lower for hint in _QUICK_HINTS):
        return DEBRIEF_QUICK
    if _HOW_WAS_RE.search(text):
        return DEBRIEF_QUICK

    return DEBRIEF_QUICK


def quick_debrief_word_count(text: str) -> int:
    cleaned = re.sub(r"\[S\d+\]", " ", text or "")
    cleaned = re.sub(r"\*\*", " ", cleaned)
    return len(re.findall(r"[A-Za-z0-9']+", cleaned))


def is_quick_debrief_compliant(text: str) -> bool:
    lower = (text or "").lower()
    if "metric:" in lower or "the biology:" in lower or "💡 example:" in lower:
        return False
    if "🔬 mechanical precision" in lower or "🫀 cardiovascular cost" in lower:
        return False
    words = quick_debrief_word_count(text)
    if words < 55 or words > 160:
        return False
    has_bottom = "bottom line" in lower or "⚡" in text
    has_plan = "vs plan" in lower or "📋" in text
    has_recovery = "recovery" in lower or "🧠" in text
    return has_bottom and has_plan and has_recovery
