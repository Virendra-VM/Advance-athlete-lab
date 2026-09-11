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

PHASEE_WEIGHTS = {
    "empathy": 0.20,
    "ui_hygiene": 0.20,
    "skill_adherence": 0.25,
    "science_grounding": 0.15,
    "phase7_composite": 0.20,
}

PHASEE_AUTO_FLAG_THRESHOLD = 0.45

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

UI_LEAK_RES = (
    re.compile(r"\bSKILL:\s*(review_session|rebuild_week|validate_plan)", re.I),
    re.compile(r"COACH TOOLS\s*\(ground truth", re.I),
    re.compile(r"\{\s*\"reply\"\s*:", re.I),
    re.compile(r"\bintent\s*=\s*[A-Z_]+\b"),
    re.compile(r"^USER:\s|^ASSISTANT:\s", re.I | re.M),
)

PUNITIVE_RE = re.compile(
    r"\b(you failed|lazy|no excuses|don't be weak|worthless|pathetic)\b",
    re.I,
)
SUPPORTIVE_RE = re.compile(
    r"\b(normal|human|reset|one step|rough patch|travel|missed|guilty|stress)\b",
    re.I,
)
MEDICAL_OVERREACH_RE = re.compile(
    r"\b(i diagnose|you have a|prescribe|take these meds|definitely a fracture)\b",
    re.I,
)
SCIENCE_GROUNDING_RE = re.compile(
    r"\b(acwr|hrv|ftp|lthr|zone|recovery|threshold|polarized|load)\b",
    re.I,
)

SUPPORT_CHAT_BANNED_RE = re.compile(
    r"(PRIMED\s*/\s*ACCUMULATE|REVISED WEEK|🧠 THE CALL|TODAY'S CALL)",
    re.I,
)
VALIDATE_PLAN_MARKERS_RE = re.compile(
    r"(bottom line|coach's rule|watch number|mostly yes|play it safer)",
    re.I,
)

DEFAULT_MEMORY_BLEED_PATTERNS = (
    re.compile(r"\bbike fit\b", re.I),
    re.compile(r"\bkolhapur\b", re.I),
    re.compile(r"\b(by train|on the train|train ride|traveling by train)\b", re.I),
)


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


@dataclass(frozen=True)
class GroundingEvalCase:
    case_id: str
    message: str
    description: str
    forbidden_patterns: tuple[str, ...] = ()
    required_patterns: tuple[str, ...] = ()


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


def score_message_grounding(
    text: str,
    *,
    forbidden_patterns: tuple[str, ...] | list[str] | None = None,
    required_patterns: tuple[str, ...] | list[str] | None = None,
) -> tuple[float, str]:
    """Penalize replies that mention topics the athlete did not raise this turn."""
    blob = text or ""
    forbidden = forbidden_patterns or ()
    compiled = [re.compile(pattern, re.I) for pattern in forbidden]
    hits = [pattern.pattern for pattern in compiled if pattern.search(blob)]
    if hits:
        return 0.0, f"forbidden_mentions={hits}"

    required = required_patterns or ()
    missing = [pat for pat in required if not re.search(pat, blob, re.I)]
    if missing:
        score = max(0.0, 1.0 - len(missing) * 0.25)
        return round(score, 3), f"missing_required={missing}"
    return 1.0, "grounded"


def score_ui_hygiene(text: str) -> tuple[float, str]:
    blob = text or ""
    leaks = sum(1 for pattern in UI_LEAK_RES if pattern.search(blob))
    score = max(0.0, 1.0 - leaks * 0.35)
    return round(score, 3), f"ui_leaks={leaks}"


def score_empathy(text: str, *, skill: str | None = None) -> tuple[float, str]:
    blob = text or ""
    punitive = bool(PUNITIVE_RE.search(blob))
    supportive = bool(SUPPORTIVE_RE.search(blob))
    if punitive:
        return 0.0, "punitive_language=yes"
    if skill in {"support_chat", "validate_plan"}:
        score = 1.0 if supportive else 0.55
        return round(score, 3), f"supportive={'yes' if supportive else 'no'}"
    score = 0.85 if supportive else 1.0
    return round(score, 3), f"supportive={'yes' if supportive else 'neutral'}"


def score_skill_adherence(text: str, skill: str | None) -> tuple[float, str]:
    blob = text or ""
    if not skill:
        return 1.0, "skill_not_set"
    if skill == "support_chat":
        banned = bool(SUPPORT_CHAT_BANNED_RE.search(blob))
        return (0.0 if banned else 1.0), f"support_banned={'yes' if banned else 'no'}"
    if skill == "validate_plan":
        has_markers = bool(VALIDATE_PLAN_MARKERS_RE.search(blob))
        return (1.0 if has_markers else 0.6), f"plan_markers={'yes' if has_markers else 'no'}"
    if skill == "off_topic":
        redirect = bool(re.search(r"\b(training|coach|workout|recovery)\b", blob, re.I))
        return (1.0 if redirect else 0.5), f"redirect={'yes' if redirect else 'no'}"
    return 1.0, "default_pass"


def score_science_grounding(text: str, *, require_terms: bool = False) -> tuple[float, str]:
    blob = text or ""
    terms = len(SCIENCE_GROUNDING_RE.findall(blob))
    overreach = bool(MEDICAL_OVERREACH_RE.search(blob))
    if overreach:
        return 0.0, "medical_overreach=yes"
    if require_terms and terms == 0:
        return 0.4, f"science_terms={terms}"
    score = min(1.0, 0.55 + terms * 0.15) if terms else 0.75
    return round(score, 3), f"science_terms={terms}"


def score_phase_e_reply(
    text: str,
    *,
    skill: str | None = None,
    expectation: CoachEvalExpectation | None = None,
    diversity_replies: list[str] | None = None,
    require_science_terms: bool = False,
) -> dict[str, Any]:
    """Phase E composite — empathy, hygiene, skill adherence, science, Phase 7 base."""
    dimensions: dict[str, dict[str, Any]] = {}
    empathy_score, empathy_detail = score_empathy(text, skill=skill)
    dimensions["empathy"] = {"score": empathy_score, "detail": empathy_detail}

    ui_score, ui_detail = score_ui_hygiene(text)
    dimensions["ui_hygiene"] = {"score": ui_score, "detail": ui_detail}

    skill_score, skill_detail = score_skill_adherence(text, skill)
    dimensions["skill_adherence"] = {"score": skill_score, "detail": skill_detail}

    science_score, science_detail = score_science_grounding(
        text, require_terms=require_science_terms
    )
    dimensions["science_grounding"] = {"score": science_score, "detail": science_detail}

    phase7 = score_coach_reply(
        text,
        expectation=expectation or CoachEvalExpectation(),
        diversity_replies=diversity_replies,
    )
    dimensions["phase7_composite"] = {
        "score": phase7["total"],
        "detail": f"phase7_total={phase7['total']}",
    }

    total = sum(PHASEE_WEIGHTS[key] * dimensions[key]["score"] for key in PHASEE_WEIGHTS)
    return {
        "total": round(total, 3),
        "dimensions": dimensions,
        "phase7": phase7,
        "would_read_whole_message": phase7.get("would_read_whole_message"),
        "auto_flag": total < PHASEE_AUTO_FLAG_THRESHOLD,
    }


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
