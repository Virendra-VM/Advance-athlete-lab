"""Phase 7 — mechanical eval for coach conversation quality.

Scores replies without an LLM judge so results are reproducible across runs.
Used by ``scripts/ai_eval/run_coach_eval.py`` and unit tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.coach_plain_language import word_count_excluding_table
from app.services.coach_schedule_mode import ACTION_SUMMARY, FULL_REPORT
from app.services.coach_variety import trigram_overlap

PHASE7_WEIGHTS = {
    "diversity": 0.25,
    "intent_adherence": 0.30,
    "plain_language": 0.25,
    "athlete_panel": 0.20,
}

DIVERSITY_OVERLAP_FAIL = 0.70
PLAIN_LANGUAGE_MAX_FK_GRADE = 10.0
ATHLETE_PANEL_MAX_WORDS = 320

BANNED_FORMAL_HEADERS = (
    "WEEKLY TRANSLATIONS",
    "THE SCIENCE",
    "LOCKER ROOM LINGO",
    "REAL-WORLD EXAMPLE",
    "METRIC:",
    "THE BIOLOGY:",
)

ZONE_CHANGE_RE = re.compile(
    r"\b("
    r"ftp|lthr|max hr|resting hr|zone|bpm|\d+\s*W|watts|heart rate|"
    r"what changed|updated anchor|under \d|over \d"
    r")\b",
    re.I,
)

WHAT_CHANGED_RE = re.compile(r"WHAT CHANGED", re.I)
WEEKLY_TRANSLATIONS_RE = re.compile(r"WEEKLY TRANSLATIONS", re.I)

TRIPLET_LINE_RES = (
    re.compile(r"THE SCIENCE", re.I),
    re.compile(r"LOCKER ROOM LINGO", re.I),
    re.compile(r"REAL-WORLD EXAMPLE", re.I),
)

SECTION_HEADER_RE = re.compile(
    r"^(🟢|🟡|🔴|🗣️|🗓️|📊|🛡️|🔬|⚡|💡|📌)\s|"
    r"^(TODAY'S CALL|REVISED WEEK|SPINE LOCK|WHAT CHANGED|WEEKLY TRANSLATIONS)",
    re.I | re.M,
)

SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.I)
WORD_RE = re.compile(r"\b[\w']+\b")


@dataclass
class CoachEvalExpectation:
    schedule_mode: str = FULL_REPORT
    require_what_changed: bool = False
    require_zone_mentions: bool = False
    ban_weekly_translations: bool = True
    max_triplet_blocks: int = 0
    max_fk_grade: float = PLAIN_LANGUAGE_MAX_FK_GRADE
    max_words: int = ATHLETE_PANEL_MAX_WORDS


@dataclass
class CoachEvalCase:
    case_id: str
    message: str
    description: str
    expectation: CoachEvalExpectation = field(default_factory=CoachEvalExpectation)
    diversity_runs: int = 0


def count_section_headers(text: str) -> int:
    return len(SECTION_HEADER_RE.findall(text or ""))


def count_triplet_blocks(text: str) -> int:
    """Count science + lingo + example triplet sets."""
    if not text:
        return 0
    blocks = 0
    current = 0
    for line in text.splitlines():
        hit = sum(1 for pattern in TRIPLET_LINE_RES if pattern.search(line))
        if hit:
            current += 1
        elif current:
            if current >= 2:
                blocks += 1
            current = 0
    if current >= 2:
        blocks += 1
    # Also count explicit WEEKLY TRANSLATIONS sections as one triplet block
    if WEEKLY_TRANSLATIONS_RE.search(text):
        blocks = max(blocks, 1)
    return blocks


def count_banned_formal_headers(text: str) -> int:
    blob = text or ""
    return sum(1 for header in BANNED_FORMAL_HEADERS if header in blob)


def mentions_zone_changes(text: str) -> bool:
    return bool(ZONE_CHANGE_RE.search(text or ""))


def has_what_changed_block(text: str) -> bool:
    return bool(WHAT_CHANGED_RE.search(text or ""))


def syllable_count(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    groups = VOWEL_GROUP_RE.findall(cleaned)
    if not groups:
        return 1
    count = len(groups)
    if cleaned.endswith("e") and not cleaned.endswith("le") and count > 1:
        count -= 1
    return max(1, count)


def flesch_kincaid_grade(text: str) -> float:
    """Grade level on prose excluding markdown tables."""
    if not text:
        return 0.0
    prose_lines = [
        line
        for line in text.splitlines()
        if not re.match(r"^\s*\|.*\|\s*$", line)
    ]
    blob = " ".join(prose_lines)
    words = WORD_RE.findall(blob)
    if not words:
        return 0.0
    sentences = [part for part in SENTENCE_SPLIT_RE.split(blob) if part.strip()]
    sentence_count = max(1, len(sentences))
    word_count = len(words)
    syllables = sum(syllable_count(word) for word in words)
    return round(
        0.39 * (word_count / sentence_count) + 11.8 * (syllables / word_count) - 15.59,
        2,
    )


def score_diversity(replies: list[str], *, threshold: float = DIVERSITY_OVERLAP_FAIL) -> tuple[float, str]:
    """Higher score when same-prompt runs differ (low pairwise trigram overlap)."""
    cleaned = [reply for reply in replies if (reply or "").strip()]
    if len(cleaned) < 2:
        return 1.0, "single run — diversity not measured"
    overlaps: list[float] = []
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            overlaps.append(trigram_overlap(cleaned[i], cleaned[j]))
    max_overlap = max(overlaps)
    avg_overlap = sum(overlaps) / len(overlaps)
    if max_overlap >= threshold:
        score = max(0.0, 1.0 - (max_overlap - threshold) / (1.0 - threshold))
    else:
        score = 1.0 - avg_overlap * 0.5
    detail = f"max_overlap={max_overlap:.2f}, avg={avg_overlap:.2f}, pairs={len(overlaps)}"
    return round(min(1.0, score), 3), detail


def score_intent_adherence(text: str, expectation: CoachEvalExpectation) -> tuple[float, str]:
    checks: dict[str, bool] = {}
    if expectation.require_what_changed:
        checks["what_changed"] = has_what_changed_block(text)
    if expectation.require_zone_mentions:
        checks["zone_mentions"] = mentions_zone_changes(text)
    if expectation.ban_weekly_translations:
        checks["no_weekly_translations"] = not WEEKLY_TRANSLATIONS_RE.search(text or "")
    checks["triplet_cap"] = count_triplet_blocks(text) <= expectation.max_triplet_blocks
    if expectation.schedule_mode == ACTION_SUMMARY:
        checks["no_formal_triplet_labels"] = count_banned_formal_headers(text) == 0

    hits = sum(1 for value in checks.values() if value)
    detail = ", ".join(f"{key}={'y' if value else 'n'}" for key, value in checks.items())
    if not checks:
        return 1.0, "no intent checks configured"
    return round(hits / len(checks), 3), detail


def score_plain_language(
    text: str,
    *,
    expectation: CoachEvalExpectation | None = None,
) -> tuple[float, str]:
    max_grade = (expectation.max_fk_grade if expectation else PLAIN_LANGUAGE_MAX_FK_GRADE)
    fk = flesch_kincaid_grade(text)
    banned = count_banned_formal_headers(text)
    words = word_count_excluding_table(text)

    grade_score = 1.0 if fk <= max_grade else max(0.0, 1.0 - (fk - max_grade) / 8.0)
    header_score = 1.0 if banned == 0 else max(0.0, 1.0 - banned * 0.35)
    length_penalty = 0.0
    if words > 280 and expectation and expectation.schedule_mode == ACTION_SUMMARY:
        length_penalty = min(0.4, (words - 280) / 400)

    score = max(0.0, 0.55 * grade_score + 0.45 * header_score - length_penalty)
    detail = f"fk_grade={fk}, banned_headers={banned}, words={words}"
    return round(score, 3), detail


def would_read_whole_message(text: str, *, expectation: CoachEvalExpectation | None = None) -> bool:
    """Heuristic proxy for athlete panel 'Would you read this whole message?'"""
    words = word_count_excluding_table(text)
    max_words = expectation.max_words if expectation else ATHLETE_PANEL_MAX_WORDS
    if words > max_words:
        return False
    if count_triplet_blocks(text) >= 2:
        return False
    if WEEKLY_TRANSLATIONS_RE.search(text or ""):
        return False
    if count_section_headers(text) > 8:
        return False
    head = (text or "")[:400]
    has_hook = bool(
        WHAT_CHANGED_RE.search(head)
        or re.search(r"(PRIMED|CAUTION|REST)\s*/\s*(ACCUMULATE|ABSORB|RESTORE)", head, re.I)
        or re.search(r"\b(only hard hit|cleared for|rest or easy|hold the calendar)\b", head, re.I)
        or re.search(r"^\*\*Why this works\*\*", head, re.I | re.M)
    )
    return has_hook


def score_athlete_panel(
    text: str,
    *,
    expectation: CoachEvalExpectation | None = None,
) -> tuple[float, str]:
    readable = would_read_whole_message(text, expectation=expectation)
    words = word_count_excluding_table(text)
    headers = count_section_headers(text)
    detail = f"would_read={'yes' if readable else 'no'}, words={words}, headers={headers}"
    return (1.0 if readable else 0.0), detail


def score_coach_reply(
    text: str,
    *,
    expectation: CoachEvalExpectation,
    diversity_replies: list[str] | None = None,
) -> dict[str, Any]:
    dimensions: dict[str, dict[str, Any]] = {}
    if diversity_replies and len(diversity_replies) >= 2:
        diversity_score, diversity_detail = score_diversity(diversity_replies)
    else:
        diversity_score, diversity_detail = 1.0, "not measured"
    dimensions["diversity"] = {"score": diversity_score, "detail": diversity_detail}

    intent_score, intent_detail = score_intent_adherence(text, expectation)
    dimensions["intent_adherence"] = {"score": intent_score, "detail": intent_detail}

    plain_score, plain_detail = score_plain_language(text, expectation=expectation)
    dimensions["plain_language"] = {"score": plain_score, "detail": plain_detail}

    panel_score, panel_detail = score_athlete_panel(text, expectation=expectation)
    dimensions["athlete_panel"] = {"score": panel_score, "detail": panel_detail}

    total = sum(PHASE7_WEIGHTS[key] * dimensions[key]["score"] for key in PHASE7_WEIGHTS)
    return {
        "total": round(total, 3),
        "dimensions": dimensions,
        "would_read_whole_message": panel_score >= 1.0,
    }
