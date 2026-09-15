"""Phase 5 — plain-language guardrails for quick session debriefs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.coach_plain_language import (
    collapse_formal_labels,
    strip_journal_filler,
    word_count_excluding_table,
)
from app.services.coach_reply_eval import flesch_kincaid_grade
from app.services.coach_voice import ANALOGY_MARKERS, wants_teaching
from app.services.debrief_mode import is_quick_debrief_compliant, quick_debrief_word_count

QUICK_DEBRIEF_MAX_FK = 8.0
QUICK_DEBRIEF_FLAG_WORDS = 150
QUICK_DEBRIEF_TARGET_MAX_WORDS = 120
QUICK_DEBRIEF_MAX_BOLD_SPANS = 3

BOLD_SPAN_RE = re.compile(r"\*\*([^*]+)\*\*")
ANALOGY_SENTENCE_RE = re.compile(
    r"[^.!?\n]*\b(" + "|".join(re.escape(m) for m in ANALOGY_MARKERS) + r")\b[^.!?\n]*[.!?]",
    re.I,
)
PLAN_MATCH_BOLD_RE = re.compile(
    r"\b(longer than planned|shorter than planned|not easy|not the easy)\b",
    re.I,
)
WATCH_HRV_BOLD_RE = re.compile(r"\bHRV\b", re.I)
WATCH_ACWR_BOLD_RE = re.compile(r"\bACWR\b", re.I)

PHASE5_QUICK_DEBRIEF_RULES = """PHASE 5 QUICK DEBRIEF (hard fail if violated):
- Max reading grade ~8 (short sentences, everyday words).
- 80-120 words target; never pad past 150.
- **Bold** only plan match (longer/shorter/not easy) and ONE watch number (HRV or ACWR).
- No analogies unless the athlete asked WHY/HOW.
- No METRIC/BIOLOGY/EXAMPLE triplets or 🔬/🫀 autopsy sections."""


@dataclass(frozen=True)
class DebriefEvalCase:
    case_id: str
    message: str
    description: str
    forbidden_patterns: tuple[str, ...] = ()
    required_patterns: tuple[str, ...] = ()


def count_bold_spans(text: str) -> int:
    return len(BOLD_SPAN_RE.findall(text or ""))


def strip_analogies_unless_teaching(text: str, message: str) -> str:
    if wants_teaching(message):
        return text
    cleaned = ANALOGY_SENTENCE_RE.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _bold_span_priority(inner: str) -> tuple[int, int]:
    """Lower sorts first — plan match (0), HRV (1), ACWR (2), drop (9)."""
    if PLAN_MATCH_BOLD_RE.search(inner):
        return (0, 0)
    if WATCH_HRV_BOLD_RE.search(inner):
        return (1, 0)
    if WATCH_ACWR_BOLD_RE.search(inner):
        return (2, 0)
    return (9, 0)


def trim_excess_bold(text: str, *, max_spans: int = QUICK_DEBRIEF_MAX_BOLD_SPANS) -> str:
    spans = list(BOLD_SPAN_RE.finditer(text or ""))
    if len(spans) <= max_spans:
        return text

    keep: set[int] = set()
    plan_idxs = [i for i, m in enumerate(spans) if _bold_span_priority(m.group(1))[0] == 0]
    for idx in plan_idxs:
        keep.add(idx)

    hrv_idx = next((i for i, m in enumerate(spans) if _bold_span_priority(m.group(1))[0] == 1), None)
    acwr_idx = next((i for i, m in enumerate(spans) if _bold_span_priority(m.group(1))[0] == 2), None)
    if hrv_idx is not None:
        keep.add(hrv_idx)
    elif acwr_idx is not None:
        keep.add(acwr_idx)

    if len(keep) > max_spans:
        keep = set(sorted(keep)[:max_spans])

    parts: list[str] = []
    last = 0
    for idx, match in enumerate(spans):
        parts.append(text[last : match.start()])
        inner = match.group(1)
        parts.append(f"**{inner}**" if idx in keep else inner)
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


def apply_quick_debrief_plain_language(
    reply: dict[str, Any],
    *,
    message: str,
    session_packet: dict[str, Any] | None = None,
    safety: dict | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """Post-process quick debrief: plain voice, no analogies, controlled bolding."""
    _ = session_packet, safety, context
    text = reply.get("reply") or ""
    text = collapse_formal_labels(strip_journal_filler(text))
    text = strip_analogies_unless_teaching(text, message)
    text = trim_excess_bold(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    reply["reply"] = text
    reply["debrief_mode"] = "quick"
    quality = score_quick_debrief_quality(text, message)
    reply["_quick_debrief_quality"] = quality
    return reply


def score_quick_debrief_quality(text: str, message: str) -> dict[str, Any]:
    words = quick_debrief_word_count(text)
    fk = flesch_kincaid_grade(text)
    bold = count_bold_spans(text)
    compliant = is_quick_debrief_compliant(text)
    analogy_violation = bool(
        not wants_teaching(message) and any(marker in (text or "").lower() for marker in ANALOGY_MARKERS)
    )

    issues: list[str] = []
    if words > QUICK_DEBRIEF_FLAG_WORDS:
        issues.append(f"words>{QUICK_DEBRIEF_FLAG_WORDS}")
    if fk > QUICK_DEBRIEF_MAX_FK:
        issues.append(f"fk>{QUICK_DEBRIEF_MAX_FK}")
    if bold > QUICK_DEBRIEF_MAX_BOLD_SPANS:
        issues.append(f"bold>{QUICK_DEBRIEF_MAX_BOLD_SPANS}")
    if not compliant:
        issues.append("structure")
    if analogy_violation:
        issues.append("analogy_without_why")

    # Higher is better — 1.0 perfect, 0.0 auto-flag
    penalties = 0.0
    if words > QUICK_DEBRIEF_FLAG_WORDS:
        penalties += min(0.5, (words - QUICK_DEBRIEF_FLAG_WORDS) / 200)
    if fk > QUICK_DEBRIEF_MAX_FK:
        penalties += min(0.35, (fk - QUICK_DEBRIEF_MAX_FK) / 10)
    if bold > QUICK_DEBRIEF_MAX_BOLD_SPANS:
        penalties += 0.15
    if not compliant:
        penalties += 0.25
    if analogy_violation:
        penalties += 0.2

    score = max(0.0, 1.0 - penalties)
    auto_flag = bool(issues)

    return {
        "score": round(score, 3),
        "words": words,
        "fk_grade": round(fk, 2),
        "bold_spans": bold,
        "compliant": compliant,
        "issues": issues,
        "auto_flag": auto_flag,
        "reason": "; ".join(issues) if issues else "ok",
    }


def should_auto_flag_quick_debrief(quality: dict[str, Any]) -> bool:
    return bool(quality.get("auto_flag"))


def validate_debrief_eval_reply(text: str, case: DebriefEvalCase) -> tuple[float, str]:
    from app.services.coach_reply_eval import score_message_grounding

    base_score, detail = score_message_grounding(
        text,
        forbidden_patterns=case.forbidden_patterns,
        required_patterns=case.required_patterns,
    )
    quality = score_quick_debrief_quality(text, case.message)
    if quality["auto_flag"]:
        return 0.0, f"{detail}; quick_debrief={quality['reason']}"
    if base_score < 1.0:
        return base_score, detail
    return 1.0, f"grounded; {quality['reason']}"
