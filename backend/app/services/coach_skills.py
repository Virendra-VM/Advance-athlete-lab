"""Phase A — skill-based routing for coach chat.

Every athlete message resolves to a *skill* (what the coach should do), not just
an intent label. Skills drive prompt selection, elite-coach persona, and polish.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.coach_advisory import (
    MISSED_OR_ROUGH_RE,
    is_go_deeper_followup,
    is_plan_advice_message,
)
from app.services.coach_intent import (
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    OFF_TOPIC,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEK_PLAN_REVIEW,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
)

# --- Skill identifiers (stable API for frontend / eval) ---

SKILL_REVIEW_SESSION = "review_session"
SKILL_REBUILD_WEEK = "rebuild_week"
SKILL_WEEK_DEBRIEF = "week_debrief"
SKILL_WEEK_PLAN_REVIEW = "week_plan_review"
SKILL_ADJUST_DAY = "adjust_day"
SKILL_EXPLAIN_METRIC = "explain_metric"
SKILL_VALIDATE_PLAN = "validate_plan"
SKILL_GO_DEEPER = "go_deeper"
SKILL_SUPPORT_CHAT = "support_chat"
SKILL_GENERAL_CHAT = "general_chat"
SKILL_CLINICAL = "clinical"
SKILL_OFF_TOPIC = "off_topic"

ALL_SKILLS = (
    SKILL_REVIEW_SESSION,
    SKILL_REBUILD_WEEK,
    SKILL_WEEK_DEBRIEF,
    SKILL_WEEK_PLAN_REVIEW,
    SKILL_ADJUST_DAY,
    SKILL_EXPLAIN_METRIC,
    SKILL_VALIDATE_PLAN,
    SKILL_GO_DEEPER,
    SKILL_SUPPORT_CHAT,
    SKILL_GENERAL_CHAT,
    SKILL_CLINICAL,
    SKILL_OFF_TOPIC,
)

INTENT_TO_SKILL: dict[str, str] = {
    WORKOUT_AUDIT: SKILL_REVIEW_SESSION,
    SCHEDULE_UPDATE: SKILL_REBUILD_WEEK,
    WEEK_REVIEW: SKILL_WEEK_DEBRIEF,
    WEEK_PLAN_REVIEW: SKILL_WEEK_PLAN_REVIEW,
    DAY_ADJUST: SKILL_ADJUST_DAY,
    SCIENCE_LOOKUP: SKILL_EXPLAIN_METRIC,
    CLINICAL_VETO: SKILL_CLINICAL,
    OFF_TOPIC: SKILL_OFF_TOPIC,
}

EMOTIONAL_RE = re.compile(
    r"\b("
    r"guilty|feel like i failed|i failed|cut it short|overwhelmed|burnt out|burned out|"
    r"stressed|anxious|discouraged|defeated|can't keep up|cannot keep up|"
    r"life got in the way|not motivated|lost motivation"
    r")\b",
    re.I,
)

TRAVEL_STRESS_RE = re.compile(
    r"\b(travel(?:ing)?|train ride|airport|jet lag|time zone|packing)\b",
    re.I,
)

ILLNESS_SOFT_RE = re.compile(
    r"\b(cold|flu|sick|under the weather|not feeling well|feeling off)\b",
    re.I,
)

PERSONAL_METRIC_RE = re.compile(
    r"\b("
    r"why is my|why has my|why's my|why are my|what(?:'s| is) wrong with my|"
    r"my hrv|my acwr|my ftp|my readiness|my sleep score|my resting heart"
    r")\b",
    re.I,
)


@dataclass(frozen=True)
class CoachSkillResolution:
    skill: str
    intent: str
    uses_elite_coach: bool = False
    uses_advisory_polish: bool = False


def is_support_chat_message(message: str) -> bool:
    """Emotional / missed-session / travel-stress chat — not plan validation."""
    text = (message or "").strip()
    if not text:
        return False
    if is_plan_advice_message(text) or is_go_deeper_followup(text):
        return False
    if MISSED_OR_ROUGH_RE.search(text):
        return True
    if EMOTIONAL_RE.search(text):
        return True
    if ILLNESS_SOFT_RE.search(text) and not re.search(
        r"\b(sharp|stabbing|tendon|ligament|fracture|diagnos)\b", text, re.I
    ):
        return True
    if TRAVEL_STRESS_RE.search(text) and re.search(
        r"\b(missed|busy|rough|stress|tired|recover)\b", text, re.I
    ):
        return True
    return False


def is_personal_metric_question(message: str) -> bool:
    return bool(PERSONAL_METRIC_RE.search(message or ""))


def resolve_coach_skill(
    intent: str,
    message: str,
    *,
    plan_advice_mode: bool = False,
    go_deeper_mode: bool = False,
) -> CoachSkillResolution:
    """Map intent + message shape to a coach skill."""
    if plan_advice_mode:
        return CoachSkillResolution(
            skill=SKILL_VALIDATE_PLAN,
            intent=GENERAL_CHAT,
            uses_elite_coach=True,
            uses_advisory_polish=True,
        )
    if go_deeper_mode:
        return CoachSkillResolution(
            skill=SKILL_GO_DEEPER,
            intent=GENERAL_CHAT,
            uses_elite_coach=True,
            uses_advisory_polish=True,
        )

    if intent == GENERAL_CHAT:
        if is_support_chat_message(message):
            return CoachSkillResolution(
                skill=SKILL_SUPPORT_CHAT,
                intent=intent,
                uses_elite_coach=True,
                uses_advisory_polish=True,
            )
        if is_personal_metric_question(message):
            return CoachSkillResolution(
                skill=SKILL_EXPLAIN_METRIC,
                intent=intent,
                uses_elite_coach=True,
                uses_advisory_polish=True,
            )
        return CoachSkillResolution(
            skill=SKILL_GENERAL_CHAT,
            intent=intent,
            uses_elite_coach=True,
            uses_advisory_polish=True,
        )

    skill = INTENT_TO_SKILL.get(intent, SKILL_GENERAL_CHAT)
    elite = skill in {
        SKILL_VALIDATE_PLAN,
        SKILL_GO_DEEPER,
        SKILL_SUPPORT_CHAT,
        SKILL_GENERAL_CHAT,
        SKILL_EXPLAIN_METRIC,
    }
    polish = elite
    return CoachSkillResolution(
        skill=skill,
        intent=intent,
        uses_elite_coach=elite,
        uses_advisory_polish=polish,
    )


def skill_prompt_block(skill: str) -> str:
    """Extra routing instructions injected into the user prompt."""
    blocks: dict[str, str] = {
        SKILL_REVIEW_SESSION: """SKILL: review_session
Autopsy the named session with telemetry. Planned-vs-executed only.""",
        SKILL_REBUILD_WEEK: """SKILL: rebuild_week
Two-pass schedule. Action summary or full report per mode.""",
        SKILL_WEEK_DEBRIEF: """SKILL: week_debrief
Recap the week window from the packet. No single-ride autopsy.""",
        SKILL_WEEK_PLAN_REVIEW: """SKILL: week_plan_review
Review-only — no calendar save, no autopsy.""",
        SKILL_ADJUST_DAY: """SKILL: adjust_day
Change TODAY only. Easy swap or mobility if readiness is poor.""",
        SKILL_EXPLAIN_METRIC: """SKILL: explain_metric
Teach the concept in plain English. Tie one answer to THEIR numbers in ATHLETE STATE
(HRV, ACWR, sleep, FTP) when available. No session autopsy. No week table.
Warm coach tone — not a textbook.""",
        SKILL_VALIDATE_PLAN: """SKILL: validate_plan
Elite Coach plan advice — empathy, day blocks with Coach's Rule, The Bottom Line.""",
        SKILL_GO_DEEPER: """SKILL: go_deeper
Brief warm follow-up. One watch number. No week table.""",
        SKILL_SUPPORT_CHAT: """SKILL: support_chat
Empathy-first elite coach message. Validate missed sessions, travel, or stress.
Reframe without punishment language. One actionable next step + one watch number.
BAN: PRIMED/ACCUMULATE, TODAY'S CALL, REVISED WEEK, tables, THE CALL headers.""",
        SKILL_GENERAL_CHAT: """SKILL: general_chat
Elite Coach conversational reply. Warm, direct, 80–200 words.
Use COACH TOOLS snapshot numbers when present. No autopsy. No week table.
BAN: PRIMED/ACCUMULATE, TODAY'S CALL, emoji section headers.""",
        SKILL_CLINICAL: """SKILL: clinical
Safety veto — refer to clinician. No training prescription.""",
        SKILL_OFF_TOPIC: """SKILL: off_topic
Politely redirect to training / recovery topics.""",
    }
    return blocks.get(skill, blocks[SKILL_GENERAL_CHAT])
