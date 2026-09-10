"""Phase 2 — conditional teaching, plain language, and analogy variety."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

WHY_HOW_RE = re.compile(
    r"\b("
    r"why|how does|how do|explain|help me understand|what(?:'s| is) the (?:science|reason)|"
    r"what makes|how come|tell me why|break down|walk me through"
    r")\b",
    re.I,
)

ANALOGY_MARKERS = (
    "engine",
    "radiator",
    "battery",
    "scaffolding",
    "scaffold",
    "mast",
    "sail",
    "credit card",
    "radio",
    "bricks",
    "overtime",
    "invoice",
    "project",
    "dashboard",
)

CONDITIONAL_TEACHING_RULES = """CONDITIONAL TEACHING (hard fail if violated):
- Do NOT add 🔬 WEEKLY TRANSLATIONS or science/lingo/analogy triplets unless one of these is true:
  • The athlete explicitly asked WHY or HOW something works.
  • Readiness is 🔴 REST / RESTORE (score < 65) — add one short **Why recovery** block (max 3 plain bullets).
  • A severe load or injury constraint must be explained to justify a change.
- When teaching IS warranted, use ONE block labeled **Why this works** (max 3 bullets) in everyday words with THEIR numbers.
- {analogy_ban}
- Prefer concrete profile numbers: "Your LTHR is 168 — Thursday unders sit at 142–151 bpm."
- Simple schedule updates: 80–180 words besides the table. No word-count padding."""

def _plain_language_rules() -> str:
    from app.services.coach_plain_language import PLAIN_LANGUAGE_PHASE4_RULES

    return PLAIN_LANGUAGE_PHASE4_RULES


@dataclass
class VoiceContext:
    wants_teaching: bool
    readiness_red: bool
    include_weekly_translations: bool
    recent_analogies: list[str]
    analogy_ban_prompt: str
    conditional_teaching_block: str
    plain_language_block: str


def wants_teaching(message: str) -> bool:
    return bool(WHY_HOW_RE.search(message or ""))


def readiness_is_red(safety: dict, context: dict | None = None) -> bool:
    from app.services.ai_coach import readiness_score, today_call_status

    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    score, _ = readiness_score(health, safety)
    band, _ = today_call_status(score)
    return band == "red" or (isinstance(score, int) and score < 65)


def should_include_weekly_translations(
    message: str,
    safety: dict,
    context: dict | None = None,
) -> bool:
    return wants_teaching(message) or readiness_is_red(safety, context)


def extract_recent_analogies(
    history: list[dict],
    *,
    max_assistant_turns: int = 3,
) -> list[str]:
    found: list[str] = []
    assistant_count = 0
    for row in reversed(history or []):
        if row.get("role") != "assistant":
            continue
        assistant_count += 1
        if assistant_count > max_assistant_turns:
            break
        text = (row.get("content") or "").lower()
        for marker in ANALOGY_MARKERS:
            if marker in text and marker not in found:
                found.append(marker)
    return found


def build_analogy_ban_prompt(recent_analogies: list[str]) -> str:
    if not recent_analogies:
        return (
            "Do not default to engine, radiator, battery, or scaffolding metaphors. "
            "Use the athlete's FTP/LTHR/pace numbers instead."
        )
    banned = ", ".join(recent_analogies)
    return (
        f"Do not reuse these metaphors (they appeared in recent replies): {banned}. "
        "Prefer the athlete's own FTP/LTHR/pace numbers instead."
    )


def build_voice_context(
    message: str,
    safety: dict,
    context: dict | None,
    history: list[dict] | None,
) -> VoiceContext:
    teaching = wants_teaching(message)
    red = readiness_is_red(safety, context)
    analogies = extract_recent_analogies(history or [])
    ban = build_analogy_ban_prompt(analogies)
    conditional = CONDITIONAL_TEACHING_RULES.format(analogy_ban=ban)
    return VoiceContext(
        wants_teaching=teaching,
        readiness_red=red,
        include_weekly_translations=teaching or red,
        recent_analogies=analogies,
        analogy_ban_prompt=ban,
        conditional_teaching_block=conditional,
        plain_language_block=_plain_language_rules(),
    )


def strip_triplet_blocks(text: str) -> str:
    from app.services.coach_schedule_mode import strip_weekly_translations

    return strip_weekly_translations(text)


def ensure_recovery_rationale(
    reply: str,
    safety: dict,
    context: dict | None,
) -> str:
    if not readiness_is_red(safety, context):
        return reply
    if re.search(r"why recovery", reply, re.I):
        return reply
    from app.services.ai_coach import readiness_score, today_call_status

    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    score, source = readiness_score(health, safety)
    _, status = today_call_status(score)
    block = (
        "**Why recovery**\n"
        f"• **{status}** — readiness is {score if score is not None else 'Missing'} ({source}).\n"
        "• Stack easy or rest today so hard days later in the week still land clean."
    )
    if "🟢 TODAY'S CALL" in reply:
        parts = reply.split("🟢 TODAY'S CALL", 1)
        return f"{parts[0].rstrip()}\n\n{block}\n\n🟢 TODAY'S CALL{parts[1]}"
    return f"{block}\n\n{reply}"


def finalize_schedule_full_reply(
    reply: dict,
    voice: VoiceContext,
    safety: dict,
    context: dict | None,
) -> dict:
    text = reply.get("reply") or ""
    if not voice.include_weekly_translations:
        text = strip_triplet_blocks(text)
    if voice.readiness_red and not voice.wants_teaching:
        text = ensure_recovery_rationale(text, safety, context)
    reply["reply"] = text
    return reply


def finalize_general_chat_reply(
    reply: dict,
    voice: VoiceContext,
    *,
    context: dict | None = None,
    safety: dict | None = None,
) -> dict:
    from app.services.coach_plain_language import apply_plain_language_reply

    text = reply.get("reply") or ""
    if not voice.wants_teaching:
        text = strip_triplet_blocks(text)
    reply["reply"] = text
    return apply_plain_language_reply(reply, context=context, safety=safety)
