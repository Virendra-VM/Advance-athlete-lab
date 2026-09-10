"""Phase 5 — variety engine: detect repetitive replies and steer regeneration."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.coach_voice import ANALOGY_MARKERS

DEGENERATE_OVERLAP_THRESHOLD = 0.70
MAX_RECENT_ASSISTANT_TURNS = 3

SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"TODAY'S CALL", re.I), "today_call"),
    (re.compile(r"LOCKER ROOM DIRECTIVE|🗣️\s+DIRECTIVE", re.I), "directive"),
    (re.compile(r"WHAT CHANGED", re.I), "what_changed"),
    (re.compile(r"REVISED WEEK|🗓️", re.I), "revised_week"),
    (re.compile(r"SPINE LOCK|🛡️", re.I), "spine_lock"),
    (re.compile(r"Why this works", re.I), "why_works"),
    (re.compile(r"Why recovery", re.I), "why_recovery"),
    (re.compile(r"WEEKLY TRANSLATIONS", re.I), "weekly_translations"),
    (re.compile(r"THE CALL|📌 ANSWER", re.I), "general_chat"),
    (re.compile(r"REFRAME", re.I), "reframe"),
)

TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
WORD_RE = re.compile(r"[a-z0-9']+")


def normalize_for_overlap(text: str) -> str:
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        if TABLE_LINE_RE.match(line):
            continue
        cleaned = re.sub(r"[🟢🟡🔴🗣️🗓️📊🛡️⚡🔬🫀💬📌🧠]", " ", line)
        cleaned = re.sub(r"\*+", " ", cleaned)
        lines.append(cleaned)
    blob = " ".join(lines).lower()
    blob = re.sub(r"\s+", " ", blob).strip()
    return blob


def trigram_set(text: str) -> set[str]:
    words = WORD_RE.findall(normalize_for_overlap(text))
    if len(words) < 3:
        return set()
    return {f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)}


def trigram_overlap(a: str, b: str) -> float:
    left, right = trigram_set(a), trigram_set(b)
    if not left or not right:
        return 0.0
    shared = len(left & right)
    return shared / min(len(left), len(right))


def recent_assistant_replies(history: list[dict], *, max_turns: int = MAX_RECENT_ASSISTANT_TURNS) -> list[str]:
    found: list[str] = []
    for row in reversed(history or []):
        if row.get("role") != "assistant":
            continue
        content = row.get("content") or ""
        if content.strip():
            found.append(content)
        if len(found) >= max_turns:
            break
    return found


def max_overlap_with_recent(text: str, history: list[dict]) -> tuple[float, int]:
    best = 0.0
    index = -1
    for i, prior in enumerate(recent_assistant_replies(history)):
        score = trigram_overlap(text, prior)
        if score > best:
            best = score
            index = i
    return best, index


def is_degenerate_reply(text: str, history: list[dict], *, threshold: float = DEGENERATE_OVERLAP_THRESHOLD) -> bool:
    if not text or not history:
        return False
    overlap, _ = max_overlap_with_recent(text, history)
    return overlap >= threshold


def extract_section_signature(text: str) -> list[str]:
    found: list[str] = []
    for pattern, label in SECTION_PATTERNS:
        if pattern.search(text or "") and label not in found:
            found.append(label)
    return found


def extract_analogies_used(text: str) -> list[str]:
    blob = (text or "").lower()
    return [marker for marker in ANALOGY_MARKERS if marker in blob]


def section_signature_hash(signature: list[str]) -> str:
    joined = "|".join(sorted(signature))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def last_assistant_variety_meta(history: list[dict]) -> dict[str, Any]:
    for row in reversed(history or []):
        if row.get("role") != "assistant":
            continue
        variety = row.get("variety")
        if isinstance(variety, dict):
            return variety
    return {}


def build_variety_retry_block(
    *,
    overlap_score: float,
    last_reply: str,
    section_signature: list[str],
    analogies_used: list[str],
) -> str:
    snippet = normalize_for_overlap(last_reply)[:220]
    banned_sections = ", ".join(section_signature) or "none"
    banned_analogies = ", ".join(analogies_used) or "engine, radiator, battery, scaffolding"
    return f"""VARIETY RETRY (hard — Phase 5)
Your draft overlapped {overlap_score:.0%} with a recent assistant reply — too similar.
Say it differently. Change sentence openings. Do not copy phrasing from the prior turn.
Prior turn snippet (do NOT reuse): {snippet}
Recent section order to vary: {banned_sections}
Do not reuse these metaphors: {banned_analogies}
Keep the same facts, week plan, and numbers — new words only."""


def analyze_reply_variety(text: str, history: list[dict]) -> dict[str, Any]:
    overlap, overlap_index = max_overlap_with_recent(text, history)
    signature = extract_section_signature(text)
    analogies = extract_analogies_used(text)
    return {
        "overlap_score": round(overlap, 3),
        "overlap_with_turn_ago": overlap_index,
        "section_signature": signature,
        "section_signature_hash": section_signature_hash(signature),
        "analogies_used": analogies,
        "word_count": len(WORD_RE.findall(normalize_for_overlap(text))),
    }


def variety_prompt_block(history: list[dict]) -> str:
    """Steer the narrator away from recent phrasing before the first attempt."""
    priors = recent_assistant_replies(history, max_turns=2)
    if not priors:
        return ""
    last_sig = extract_section_signature(priors[0])
    last_analogies = extract_analogies_used(priors[0])
    lines = [
        "VARIETY (Phase 5): Do not repeat phrasing from your last assistant replies.",
    ]
    if last_sig:
        lines.append(f"Last reply sections: {', '.join(last_sig)} — vary sentence openings.")
    if last_analogies:
        lines.append(f"Banned metaphors from recent turns: {', '.join(last_analogies)}.")
    return "\n".join(lines)
