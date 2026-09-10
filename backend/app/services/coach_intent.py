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
WEEK_REVIEW = "WEEK_REVIEW"
WEEK_PLAN_REVIEW = "WEEK_PLAN_REVIEW"
DAY_ADJUST = "DAY_ADJUST"
SCIENCE_LOOKUP = "SCIENCE_LOOKUP"
CLINICAL_VETO = "CLINICAL_VETO"
OFF_TOPIC = "OFF_TOPIC"
GENERAL_CHAT = "GENERAL_CHAT"

INTENTS = (
    WORKOUT_AUDIT,
    SCHEDULE_UPDATE,
    DAY_ADJUST,
    WEEK_REVIEW,
    WEEK_PLAN_REVIEW,
    SCIENCE_LOOKUP,
    CLINICAL_VETO,
    OFF_TOPIC,
    GENERAL_CHAT,
)

# Stored on older replies / eval harnesses.
LEGACY_INTENT = {
    "session_analysis": WORKOUT_AUDIT,
    "chat": GENERAL_CHAT,
    "schedule": SCHEDULE_UPDATE,
    "week_review": WEEK_REVIEW,
    "week_recap": WEEK_REVIEW,
    "day_adjust": DAY_ADJUST,
    "today_adjust": DAY_ADJUST,
    "science": SCIENCE_LOOKUP,
    "science_rag_lookup": SCIENCE_LOOKUP,
    "clinical_safety_veto": CLINICAL_VETO,
    "clinical": CLINICAL_VETO,
    "off_topic": OFF_TOPIC,
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
    "how was this ride",
    "how was this run",
    "how was this session",
    "how was this workout",
    "how was this swim",
    "how did i do today",
    "how did i perform today",
    "how did i do on",
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
    "analyse this",
    "analyze this",
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

WEEK_REVIEW_HINTS = (
    "how did i do this week",
    "how did i do last week",
    "how did i do the week",
    "how was my week",
    "how was this week",
    "how was last week",
    "how was the week",
    "how did the week go",
    "how did this week go",
    "how did last week go",
    "done with the week",
    "finished the week",
    "finish the week",
    "week recap",
    "recap my week",
    "recap the week",
    "review my week",
    "review the week",
    "look at my week",
    "take a look at my week",
    "look at the week",
    "grade my week",
    "score my week",
    "week in review",
    "debrief my week",
    "debrief the week",
    "how did we do this week",
    "analyse this week",
    "analyze this week",
    "analyse my week",
    "analyze my week",
)

WEEK_SCOPE_RE = re.compile(
    r"\b(this week|last week|the week|my week|weekly recap|week recap)\b",
    re.IGNORECASE,
)
FORWARD_PLAN_RE = re.compile(
    r"\b(adjust|change|modify|update|revise|rewrite|plan my|build my|"
    r"what should i do|schedule)\b",
    re.IGNORECASE,
)
RETROSPECT_RE = re.compile(
    r"\b(how did i do|how did i perform|how was|how did .{0,20} go|"
    r"recap|review|debrief|grade|look at|take a look|done with)\b",
    re.IGNORECASE,
)
SESSION_SCOPE_RE = re.compile(
    r"\b(today|yesterday|this morning|this afternoon|this ride|this run|"
    r"this swim|this session|this workout|ride|run|swim|session|workout|"
    r"trainer|whoosh|lift|gym|yoga|mobility)\b",
    re.IGNORECASE,
)

SCIENCE_HINTS = (
    "what is acwr",
    "what is ftp",
    "what is hrv",
    "what is lthr",
    "what is tss",
    "what is zone 2",
    "what is polarized",
    "blood flow restriction",
    "heat acclimation",
    "heat acclimat",
    "latest research",
    "peer review",
    "peer-reviewed",
    "how does acwr",
    "why does acwr",
    "explain acwr",
    "mitochondrial",
    "lactate threshold",
    "lactate clearance",
    "carbohydrate periodization",
    "zone 2 carbohydrate",
    "tapering strategies",
    "polarized training",
    "periodization",
)

SCIENCE_QUESTION_RE = re.compile(
    r"\b(what is|what's|whats|how does|why does|why is my|why has my|why's my|"
    r"explain|latest research|peer[- ]?reviewed|blood flow restriction|heat acclim)\b",
    re.IGNORECASE,
)

PERSONAL_METRIC_RE = re.compile(
    r"\b("
    r"why is my|why has my|why's my|why are my|what(?:'s| is) wrong with my|"
    r"my hrv|my acwr|my ftp|my readiness|my sleep score|my resting heart"
    r")\b",
    re.IGNORECASE,
)

OFF_TOPIC_HINTS = (
    "what stock",
    "which stock",
    "stock should i buy",
    "crypto",
    "bitcoin",
    "nft",
    "who should i vote",
    "election",
    "write me python",
    "do my homework",
    "recipe for lasagna",
    "best tv show",
)

OFF_TOPIC_RE = re.compile(
    r"\b(stock|stocks|crypto|bitcoin|ethereum|nft|portfolio|who (won|should i vote)|"
    r"election|homework|lasagna|netflix)\b",
    re.IGNORECASE,
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
    "adjust my plan",
    "modify my plan",
    "move the long",
    "swap my",
    "rest day",
    "what should i do this week",
    "plan my week",
    "build my week",
)

DAY_ADJUST_HINTS = (
    "adjust today",
    "today only",
    "skip today",
    "swap today",
    "downgrade today",
    "should i still do",
    "should i still train",
    "can i still do",
    "can i still train",
    "train today with",
)

HEALTH_FACTOR_RE = re.compile(
    r"\b(hrv|rmssd|readiness|acwr|sleep score|slept (bad|poor)|poor sleep|bad sleep|"
    r"high stress|stress(?:ed| score)?|overreached)\b",
    re.IGNORECASE,
)
TODAY_SCOPE_RE = re.compile(
    r"\b(today|tonight|this morning|this afternoon)\b",
    re.IGNORECASE,
)

CLASSIFIER_SYSTEM = """You classify athlete coach-chat messages. Reply with JSON only.
Choose exactly one intent:
- WORKOUT_AUDIT: one named or implied session (today's ride, this run, laps, watts, "how was yoga").
- WEEK_REVIEW: recap of a completed or current training week ("how did I do this week", "look at my week").
- DAY_ADJUST: today's session only because HRV, readiness, stress, ACWR, or sleep is poor. Do not pick this for a full-week rewrite.
- SCHEDULE_UPDATE: proposing, asking to see, or asking to change this week's training plan going forward (calendar, sports, rest days) — not a one-day health tweak.
- CLINICAL_VETO: sharp/tissue pain, injury diagnosis requests, or asking the coach to prescribe medication.
- OFF_TOPIC: stocks, politics, generic homework, anything outside athletic performance / recovery / sports science.
- SCIENCE_LOOKUP: asking what a training concept is, or how a method works (ACWR, heat acclimation, zones, HRV).
- GENERAL_CHAT: emotional support, missed sessions, validating a DIY plan ("should I use this plan?"), casual coach chat. Default here if unsure.
Never pick SCHEDULE_UPDATE when they only want your opinion on a plan they already proposed.
Never pick WORKOUT_AUDIT just because a ride exists or they said "how did I do".
If they said "this week" / "my week" / "the week" and want a recap, pick WEEK_REVIEW, not WORKOUT_AUDIT.
Never pick SCHEDULE_UPDATE for a retrospective week recap.
Never pick SCHEDULE_UPDATE when the only reason is today's HRV, readiness, stress, or ACWR — that is DAY_ADJUST.
Never invent a paper. CLINICAL_VETO always beats a science explanation if they report sharp pain."""

CLASSIFIER_SCHEMA = """{"intent": "WORKOUT_AUDIT|WEEK_REVIEW|DAY_ADJUST|SCHEDULE_UPDATE|SCIENCE_LOOKUP|CLINICAL_VETO|OFF_TOPIC|GENERAL_CHAT"}"""


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    source: str
    audit_score: int = 0
    schedule_score: int = 0
    review_score: int = 0


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
    """Public router. Returns one of the INTENTS labels."""
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
        if llm_intent == WORKOUT_AUDIT and structural.review_score >= 3:
            return IntentDecision(
                intent=WEEK_REVIEW,
                confidence=0.85,
                source="structural_blocks_llm_audit",
                audit_score=structural.audit_score,
                schedule_score=structural.schedule_score,
                review_score=structural.review_score,
            )
        if structural.intent in {CLINICAL_VETO, OFF_TOPIC} and structural.confidence >= 0.8:
            return structural
        return IntentDecision(
            intent=llm_intent,
            confidence=0.8,
            source="llm",
            audit_score=structural.audit_score,
            schedule_score=structural.schedule_score,
            review_score=structural.review_score,
        )
    # Fail open to the structural winner. Never invent an autopsy.
    if structural.intent == WORKOUT_AUDIT and structural.confidence < 0.7:
        return IntentDecision(
            intent=GENERAL_CHAT,
            confidence=0.4,
            source="ambiguous_default",
            audit_score=structural.audit_score,
            schedule_score=structural.schedule_score,
            review_score=structural.review_score,
        )
    return structural


def _classify_structural(message: str) -> IntentDecision:
    text = (message or "").strip().lower()
    if not text:
        return IntentDecision(GENERAL_CHAT, 1.0, "empty")

    from app.services.coach_advisory import is_go_deeper_followup, is_plan_advice_message
    from app.services.coach_safety import detect_clinical_boundary

    if is_go_deeper_followup(message):
        return IntentDecision(GENERAL_CHAT, 0.94, "structural_go_deeper")
    if is_plan_advice_message(message):
        return IntentDecision(GENERAL_CHAT, 0.94, "structural_plan_advice")

    clinical = detect_clinical_boundary(message)
    if clinical:
        return IntentDecision(CLINICAL_VETO, 0.96, "structural_clinical")

    if any(hint in text for hint in OFF_TOPIC_HINTS) or (
        OFF_TOPIC_RE.search(text)
        and not re.search(r"\b(train|ftp|hrv|sleep|ride|run|week|session)\b", text)
    ):
        return IntentDecision(OFF_TOPIC, 0.9, "structural_off_topic")

    audit = 0
    schedule = 0
    review = 0
    science = 0
    week_scoped = bool(WEEK_SCOPE_RE.search(text))
    looking_forward = bool(FORWARD_PLAN_RE.search(text))
    pasted_laps = bool(LAP_RE.search(text) and POWER_PASTE_RE.search(text))

    if any(hint in text for hint in AUDIT_HINTS):
        audit += 3
    if ("how did i do" in text or "how did i perform" in text) and not week_scoped:
        if SESSION_SCOPE_RE.search(text):
            audit += 3
    if POWER_PASTE_RE.search(text) and ("ftp" in text or "lap" in text or len(message) >= 280):
        audit += 3
    if pasted_laps:
        audit += 3
    if re.search(r"\b(how was|analyse|analyze)\b", text) and SESSION_SCOPE_RE.search(text):
        if not week_scoped:
            audit += 2

    if any(hint in text for hint in WEEK_REVIEW_HINTS):
        review += 4
    if week_scoped and RETROSPECT_RE.search(text) and not looking_forward:
        review += 3
    elif week_scoped and re.search(r"\b(how did i|done with|look at my week)\b", text):
        review += 2

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
    # Retrospective week language is not a request to rewrite the calendar.
    if review >= 3 and looking_forward is False:
        schedule = min(schedule, 2)

    if any(hint in text for hint in SCIENCE_HINTS):
        science += 4
    if PERSONAL_METRIC_RE.search(text):
        science += 4
    if SCIENCE_QUESTION_RE.search(text) and not week_scoped and audit < 3 and schedule < 3:
        science += 3

    day_adjust = 0
    health = bool(HEALTH_FACTOR_RE.search(text))
    today_scoped = bool(TODAY_SCOPE_RE.search(text))
    science_question = bool(SCIENCE_QUESTION_RE.search(text))
    full_week_build = (
        "plan my week" in text
        or "build my week" in text
        or "weekly plan" in text
        or len(weekdays) >= 3
    )
    if health and not science_question:
        day_adjust += 3
    if any(hint in text for hint in DAY_ADJUST_HINTS):
        day_adjust += 4
    if health and today_scoped and not science_question:
        day_adjust += 3
    if health and looking_forward and not full_week_build and not science_question:
        day_adjust += 3
    if health and re.search(
        r"\b(should i|can i|skip|swap|downgrade|still train|still do)\b",
        text,
    ):
        day_adjust += 2
        audit = min(audit, 2)

    # A past-session correction that also mentions the week plan is still an autopsy.
    if audit >= 3 and schedule >= 2 and (
        pasted_laps or "analyse" in text or "analyze" in text or "you got it wrong" in text
    ):
        return IntentDecision(
            WORKOUT_AUDIT, 0.9, "structural_audit_overrides_schedule", audit, schedule, review
        )

    # Week recap beats a generic "how did I do" autopsy unless they pasted laps.
    if review >= 3 and review >= audit and not pasted_laps:
        if schedule >= 3 and looking_forward and schedule > review:
            confidence = 0.92 if schedule >= 5 else 0.8
            return IntentDecision(SCHEDULE_UPDATE, confidence, "structural", audit, schedule, review)
        confidence = 0.92 if review >= 5 else 0.85
        return IntentDecision(WEEK_REVIEW, confidence, "structural", audit, schedule, review)

    if day_adjust >= 3 and not full_week_build and day_adjust >= audit and review < 3:
        confidence = 0.92 if day_adjust >= 5 else 0.8
        return IntentDecision(DAY_ADJUST, confidence, "structural_day_adjust", audit, schedule, review)

    if schedule >= 3 and schedule > audit and schedule >= review:
        confidence = 0.92 if schedule >= 5 else 0.8
        return IntentDecision(SCHEDULE_UPDATE, confidence, "structural", audit, schedule, review)
    if audit >= 3 and audit >= schedule and audit >= review:
        confidence = 0.92 if audit >= 5 else 0.8
        return IntentDecision(WORKOUT_AUDIT, confidence, "structural", audit, schedule, review)
    if science >= 3 and science >= audit and science >= schedule and science >= review:
        confidence = 0.9 if science >= 5 else 0.8
        return IntentDecision(SCIENCE_LOOKUP, confidence, "structural_science", audit, schedule, review)
    if review > 0 and review >= audit and review >= schedule:
        return IntentDecision(WEEK_REVIEW, 0.6, "structural_weak", audit, schedule, review)
    # DIY "should I use this plan?" with day names is advice, not a calendar rebuild.
    if schedule > 0 and schedule >= audit and not is_plan_advice_message(message):
        return IntentDecision(SCHEDULE_UPDATE, 0.55, "structural_weak", audit, schedule, review)
    if audit > 0:
        return IntentDecision(WORKOUT_AUDIT, 0.55, "structural_weak", audit, schedule, review)
    return IntentDecision(GENERAL_CHAT, 0.85, "structural_default", audit, schedule, review)


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
