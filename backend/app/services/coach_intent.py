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
from datetime import date, timedelta

logger = logging.getLogger(__name__)

WORKOUT_AUDIT = "WORKOUT_AUDIT"
SCHEDULE_UPDATE = "SCHEDULE_UPDATE"
WEEK_REVIEW = "WEEK_REVIEW"
MONTH_REVIEW = "MONTH_REVIEW"
YEAR_REVIEW = "YEAR_REVIEW"
WEEK_PLAN_REVIEW = "WEEK_PLAN_REVIEW"
DAY_ADJUST = "DAY_ADJUST"
SCIENCE_LOOKUP = "SCIENCE_LOOKUP"
CLINICAL_VETO = "CLINICAL_VETO"
OFF_TOPIC = "OFF_TOPIC"
GENERAL_CHAT = "GENERAL_CHAT"

PERIOD_REVIEW_INTENTS = frozenset({WEEK_REVIEW, MONTH_REVIEW, YEAR_REVIEW})

INTENTS = (
    WORKOUT_AUDIT,
    SCHEDULE_UPDATE,
    DAY_ADJUST,
    WEEK_REVIEW,
    MONTH_REVIEW,
    YEAR_REVIEW,
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
    "month_review": MONTH_REVIEW,
    "month_recap": MONTH_REVIEW,
    "year_review": YEAR_REVIEW,
    "year_recap": YEAR_REVIEW,
    "season_review": YEAR_REVIEW,
    "day_adjust": DAY_ADJUST,
    "today_adjust": DAY_ADJUST,
    "science": SCIENCE_LOOKUP,
    "science_rag_lookup": SCIENCE_LOOKUP,
    "clinical_safety_veto": CLINICAL_VETO,
    "clinical": CLINICAL_VETO,
    "off_topic": OFF_TOPIC,
    # Architecture lens names. Stored replies may use either vocabulary.
    "workout_single_autopsy": WORKOUT_AUDIT,
    "weekly_executive_summary": WEEK_REVIEW,
    "schedule_mutation": SCHEDULE_UPDATE,
}

# Blueprint lenses. Runtime labels above stay the values classify_chat_intent returns.
WORKOUT_SINGLE_AUTOPSY = "WORKOUT_SINGLE_AUTOPSY"
WEEKLY_EXECUTIVE_SUMMARY = "WEEKLY_EXECUTIVE_SUMMARY"
SCHEDULE_MUTATION = "SCHEDULE_MUTATION"

ARCHITECTURE_INTENTS = (
    WORKOUT_SINGLE_AUTOPSY,
    WEEKLY_EXECUTIVE_SUMMARY,
    SCHEDULE_MUTATION,
    SCIENCE_LOOKUP,
    CLINICAL_VETO,
)

# Several runtime labels share one lens. The reverse map is the canonical
# runtime label for that lens, so reading a lens back does not collapse
# DAY_ADJUST into a week rewrite or a month recap into a week recap.
RUNTIME_TO_ARCHITECTURE = {
    WORKOUT_AUDIT: WORKOUT_SINGLE_AUTOPSY,
    WEEK_REVIEW: WEEKLY_EXECUTIVE_SUMMARY,
    MONTH_REVIEW: WEEKLY_EXECUTIVE_SUMMARY,
    YEAR_REVIEW: WEEKLY_EXECUTIVE_SUMMARY,
    SCHEDULE_UPDATE: SCHEDULE_MUTATION,
    DAY_ADJUST: SCHEDULE_MUTATION,
    WEEK_PLAN_REVIEW: SCHEDULE_MUTATION,
    SCIENCE_LOOKUP: SCIENCE_LOOKUP,
    CLINICAL_VETO: CLINICAL_VETO,
}

ARCHITECTURE_TO_RUNTIME = {
    WORKOUT_SINGLE_AUTOPSY: WORKOUT_AUDIT,
    WEEKLY_EXECUTIVE_SUMMARY: WEEK_REVIEW,
    SCHEDULE_MUTATION: SCHEDULE_UPDATE,
    SCIENCE_LOOKUP: SCIENCE_LOOKUP,
    CLINICAL_VETO: CLINICAL_VETO,
}

# Spoken after a calendar write. Discussion turns never use this line.
EXECUTION_CONFIRMATION = "Done. I've updated your calendar. Rest up."

_QUESTION_RE = re.compile(
    r"(\?\s*$)|^\s*(can|could|should|would|how|what|why|may|is it|do you think)\b",
    re.IGNORECASE,
)
_EXPLICIT_PATCH_RE = re.compile(
    r"\b("
    r"update my (week|calendar|schedule|plan)|"
    r"yes,?\s+update|"
    r"do it|"
    r"lock (it|that) in|"
    r"go ahead|"
    r"apply (it|that|those|the changes|the plan)|"
    r"put (it|that) on (my )?(calendar|schedule)"
    r")\b",
    re.IGNORECASE,
)
_IMPERATIVE_PATCH_RE = re.compile(
    r"^\s*(please\s+)?(move|swap|shift|reschedule|skip|downgrade|make|change|wipe)\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

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
    "analyse my last week",
    "analyze my last week",
    "analyse last week",
    "analyze last week",
    "summarize my week",
    "summarise my week",
    "summarize last week",
    "summarise last week",
    "weekly debrief",
    "week debrief",
)

MONTH_REVIEW_HINTS = (
    "how did i do this month",
    "how did i do last month",
    "how was my month",
    "how was this month",
    "how was last month",
    "monthly recap",
    "recap my month",
    "review my month",
    "grade my month",
    "analyse my month",
    "analyze my month",
    "analyse last month",
    "analyze last month",
    "summarize my month",
    "summarise my month",
    "last 30 days",
    "past 30 days",
    "last 4 weeks",
    "past 4 weeks",
)

YEAR_REVIEW_HINTS = (
    "how did i do this year",
    "how did i do last year",
    "how was my year",
    "how was this year",
    "how was last year",
    "yearly recap",
    "year in review",
    "recap my year",
    "review my year",
    "grade my year",
    "grade my season",
    "analyse my year",
    "analyze my year",
    "summarize my year",
    "summarise my year",
    "last 12 months",
    "past 12 months",
    "this season",
)

WEEK_SCOPE_RE = re.compile(
    r"\b(this week|last week|the week|my week|weekly recap|week recap|"
    r"past week|previous week|last 7 days|past 7 days|the last 7 days|"
    r"last seven days|past seven days)\b",
    re.IGNORECASE,
)
MONTH_SCOPE_RE = re.compile(
    r"\b(this month|last month|the month|my month|monthly recap|month recap|"
    r"past month|previous month|last 30 days|past 30 days|the last 30 days|"
    r"last 4 weeks|past 4 weeks|last four weeks|30 days ago)\b",
    re.IGNORECASE,
)
YEAR_SCOPE_RE = re.compile(
    r"\b(this year|last year|the year|my year|yearly recap|year recap|"
    r"past year|previous year|year in review|this season|last season|"
    r"last 12 months|past 12 months|the last 12 months|calendar year)\b",
    re.IGNORECASE,
)
FORWARD_PLAN_RE = re.compile(
    r"\b(adjust|change|modify|update|revise|rewrite|plan my|build my|"
    r"what should i do|schedule)\b",
    re.IGNORECASE,
)
RETROSPECT_RE = re.compile(
    r"\b(how did i do|how did i perform|how was|how's my|hows my|how did .{0,20} go|"
    r"recap|review|debrief|grade|look at|take a look|done with|"
    r"analyse|analyze|summarize|summarise|break down|"
    r"improved|improvement|progress|fitter|gains|compared)\b",
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
    r"\b("
    r"what is(?! a good| the best| a nice)|what's(?! a good| the best)|whats(?! a good)|"
    r"how does|why does|why is my|why has my|why's my|"
    r"explain|latest research|peer[- ]?reviewed|blood flow restriction|heat acclim|"
    r"what does .{0,20} (mean|do|measure)"
    r")\b",
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
    "stock price",
    "crypto",
    "bitcoin",
    "nft",
    "who should i vote",
    "election",
    "write me python",
    "write me a python",
    "do my homework",
    "recipe for lasagna",
    "best tv show",
    "fix my wifi",
    "help with my taxes",
    "book me a flight",
    "capital of france",
    "joke about cats",
    "restaurant nearby",
)

OFF_TOPIC_RE = re.compile(
    r"\b(stock|stocks|crypto|bitcoin|ethereum|nft|portfolio|who (won|should i vote)|"
    r"election|homework|lasagna|netflix|python script|wifi|taxes|flight to|"
    r"capital of|tv show)\b",
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
    "can i swap",
    "could i swap",
    "rest day",
    "what should i do this week",
    "plan my week",
    "plan the week",
    "build my week",
    "build a recovery week",
    "plan the rest",
    "change friday",
    "this week's calendar",
    "this weeks calendar",
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
- WEEK_REVIEW: recap of a completed or current training week ("how did I do this week", "last 7 days").
- MONTH_REVIEW: recap of a month or ~30 days of training ("how did I do this month", "last 4 weeks").
- YEAR_REVIEW: recap of a year/season ("how did I do this year", "last 12 months").
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

CLASSIFIER_SCHEMA = """{"intent": "WORKOUT_AUDIT|WEEK_REVIEW|MONTH_REVIEW|YEAR_REVIEW|DAY_ADJUST|SCHEDULE_UPDATE|SCIENCE_LOOKUP|CLINICAL_VETO|OFF_TOPIC|GENERAL_CHAT"}"""


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    source: str
    audit_score: int = 0
    schedule_score: int = 0
    review_score: int = 0
    month_score: int = 0
    year_score: int = 0


def normalize_intent(value: str | None) -> str:
    raw = (value or "").strip()
    if raw in INTENTS:
        return raw
    return LEGACY_INTENT.get(raw.lower(), GENERAL_CHAT)


def architecture_intent_for(runtime_intent: str | None) -> str | None:
    """Map a runtime or legacy label onto a blueprint lens.

    GENERAL_CHAT and OFF_TOPIC stay unmapped. They are not one of the five lenses.
    """
    if runtime_intent is None or not str(runtime_intent).strip():
        return None
    raw = str(runtime_intent).strip()
    if raw in RUNTIME_TO_ARCHITECTURE:
        return RUNTIME_TO_ARCHITECTURE[raw]
    normalized = normalize_intent(raw)
    return RUNTIME_TO_ARCHITECTURE.get(normalized)


def runtime_intent_for(architecture_intent: str) -> str:
    """Canonical runtime label for a blueprint lens."""
    try:
        return ARCHITECTURE_TO_RUNTIME[architecture_intent]
    except KeyError as exc:
        raise ValueError(f"Unknown architecture intent: {architecture_intent}") from exc


def schedule_patch_authorized(message: str) -> bool:
    """True only when the athlete told us to write the calendar.

    A question stays in discussion. An explicit confirm or an imperative
    change ("Move my long run to Sunday") is execution.
    """
    text = (message or "").strip()
    if not text:
        return False
    if _EXPLICIT_PATCH_RE.search(text):
        return True
    if _QUESTION_RE.search(text):
        return False
    return bool(_IMPERATIVE_PATCH_RE.search(text))


def extract_target_date(message: str, today: date | None = None) -> str | None:
    """First concrete day in the message, as YYYY-MM-DD."""
    text = message or ""
    iso = _ISO_DATE_RE.search(text)
    if iso:
        try:
            date.fromisoformat(iso.group(1))
        except ValueError:
            return None
        return iso.group(1)
    if today is None:
        return None
    lower = text.lower()
    if re.search(r"\btoday\b", lower):
        return today.isoformat()
    if re.search(r"\btomorrow\b", lower):
        return (today + timedelta(days=1)).isoformat()
    for index, name in enumerate(_WEEKDAY_NAMES):
        if re.search(rf"\b{name}\b", lower):
            delta = (index - today.weekday()) % 7
            return (today + timedelta(days=delta)).isoformat()
    return None


def route_athlete_query(
    message: str,
    *,
    runtime_intent: str,
    confidence: float = 0.9,
    today: date | None = None,
):
    """Phase gate. Discussion never sets requires_database_patch."""
    from app.ai_schemas import CoachIntent

    category = architecture_intent_for(runtime_intent)
    if category is None:
        return None
    patch = category == SCHEDULE_MUTATION and schedule_patch_authorized(message)
    score = min(1.0, max(0.0, float(confidence)))
    return CoachIntent(
        intent_category=category,
        confidence_score=score,
        requires_database_patch=patch,
        target_date=extract_target_date(message, today) if patch else None,
    )


def decision_to_coach_intent(
    decision: IntentDecision,
    *,
    requires_database_patch: bool = False,
    target_date: str | None = None,
):
    """Validate a routing decision as the blueprint CoachIntent, when it has a lens."""
    from app.ai_schemas import CoachIntent

    category = architecture_intent_for(decision.intent)
    if category is None:
        return None
    return CoachIntent(
        intent_category=category,
        confidence_score=decision.confidence,
        requires_database_patch=requires_database_patch,
        target_date=target_date,
    )


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
    if structural.source in {
        "empty",
        "structural_go_deeper",
        "structural_plan_advice",
        "structural_clinical",
        "structural_off_topic",
    }:
        return structural
    if structural.intent in {CLINICAL_VETO, OFF_TOPIC} and structural.confidence >= 0.8:
        return structural

    embed = None
    long_tail = bool(
        re.search(
            r"\b(last 7 days|past 7 days|last 30 days|last 4 weeks|last 12 months|"
            r"improved|improvement|progress|fitter|recap|debrief|"
            r"analyse|analyze|summarize|summarise|how did i do|how was my|how's my)\b",
            message or "",
            re.I,
        )
    )
    weak_or_default = (
        structural.confidence < 0.7
        or structural.source in {"structural_weak", "structural_week_scoped_default"}
        or (structural.source == "structural_default" and long_tail)
    )
    if weak_or_default:
        try:
            from app.services.coach_intent_embed import classify_with_embeddings

            embed = classify_with_embeddings(message)
        except Exception:  # noqa: BLE001 — embeddings must never break chat
            embed = None
        if embed and embed.intent in INTENTS:
            if (
                structural.intent in PERIOD_REVIEW_INTENTS
                and embed.intent not in PERIOD_REVIEW_INTENTS
                and embed.intent != SCHEDULE_UPDATE
            ):
                return structural
            return IntentDecision(
                intent=embed.intent,
                confidence=embed.confidence,
                source=embed.source,
                audit_score=structural.audit_score,
                schedule_score=structural.schedule_score,
                review_score=structural.review_score,
                month_score=structural.month_score,
                year_score=structural.year_score,
            )

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
                month_score=structural.month_score,
                year_score=structural.year_score,
            )
        if llm_intent == WORKOUT_AUDIT and structural.month_score >= 3:
            return IntentDecision(
                intent=MONTH_REVIEW,
                confidence=0.85,
                source="structural_blocks_llm_audit",
                audit_score=structural.audit_score,
                schedule_score=structural.schedule_score,
                review_score=structural.review_score,
                month_score=structural.month_score,
                year_score=structural.year_score,
            )
        if llm_intent == WORKOUT_AUDIT and structural.year_score >= 3:
            return IntentDecision(
                intent=YEAR_REVIEW,
                confidence=0.85,
                source="structural_blocks_llm_audit",
                audit_score=structural.audit_score,
                schedule_score=structural.schedule_score,
                review_score=structural.review_score,
                month_score=structural.month_score,
                year_score=structural.year_score,
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
            month_score=structural.month_score,
            year_score=structural.year_score,
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
    month_review = 0
    year_review = 0
    science = 0
    week_scoped = bool(WEEK_SCOPE_RE.search(text))
    month_scoped = bool(MONTH_SCOPE_RE.search(text))
    year_scoped = bool(YEAR_SCOPE_RE.search(text))
    looking_forward = bool(FORWARD_PLAN_RE.search(text))
    pasted_laps = bool(LAP_RE.search(text) and POWER_PASTE_RE.search(text))
    retrospect = bool(RETROSPECT_RE.search(text))

    if any(hint in text for hint in AUDIT_HINTS):
        audit += 3
    if ("how did i do" in text or "how did i perform" in text) and not (
        week_scoped or month_scoped or year_scoped
    ):
        if SESSION_SCOPE_RE.search(text):
            audit += 3
    if POWER_PASTE_RE.search(text) and ("ftp" in text or "lap" in text or len(message) >= 280):
        audit += 3
    if pasted_laps:
        audit += 3
    if re.search(r"\b(how was|analyse|analyze)\b", text) and SESSION_SCOPE_RE.search(text):
        if not (week_scoped or month_scoped or year_scoped):
            audit += 2

    if any(hint in text for hint in YEAR_REVIEW_HINTS):
        year_review += 4
    if year_scoped and retrospect and not looking_forward:
        year_review += 3

    if any(hint in text for hint in MONTH_REVIEW_HINTS):
        month_review += 4
    if month_scoped and retrospect and not looking_forward:
        month_review += 3

    if any(hint in text for hint in WEEK_REVIEW_HINTS):
        review += 4
    if week_scoped and retrospect and not looking_forward:
        review += 3
    elif week_scoped and re.search(
        r"\b(how did i|done with|look at my week|analyse|analyze|summarize|summarise)\b",
        text,
    ):
        review += 2
    if week_scoped and re.search(r"\b(that week|in that week)\b", text) and retrospect:
        review += 2

    # Longer windows beat a week recap when both are present.
    if year_review >= 3:
        review = min(review, 2)
        month_review = min(month_review, 2)
    elif month_review >= 3:
        review = min(review, 2)

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
    if SCIENCE_QUESTION_RE.search(text) and not week_scoped and not month_scoped and not year_scoped and audit < 3 and schedule < 3:
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
            WORKOUT_AUDIT, 0.9, "structural_audit_overrides_schedule", audit, schedule, review,
            month_review, year_review,
        )

    period_scores = (
        (YEAR_REVIEW, year_review),
        (MONTH_REVIEW, month_review),
        (WEEK_REVIEW, review),
    )
    best_period, best_period_score = max(period_scores, key=lambda item: item[1])
    if best_period_score >= 3 and best_period_score >= audit and not pasted_laps:
        if schedule >= 3 and looking_forward and schedule > best_period_score:
            confidence = 0.92 if schedule >= 5 else 0.8
            return IntentDecision(
                SCHEDULE_UPDATE, confidence, "structural", audit, schedule, review,
                month_review, year_review,
            )
        confidence = 0.92 if best_period_score >= 5 else 0.85
        return IntentDecision(
            best_period, confidence, "structural", audit, schedule, review,
            month_review, year_review,
        )

    if day_adjust >= 3 and not full_week_build and day_adjust >= audit and best_period_score < 3:
        confidence = 0.92 if day_adjust >= 5 else 0.8
        return IntentDecision(
            DAY_ADJUST, confidence, "structural_day_adjust", audit, schedule, review,
            month_review, year_review,
        )

    if schedule >= 3 and schedule > audit and schedule >= best_period_score:
        confidence = 0.92 if schedule >= 5 else 0.8
        return IntentDecision(
            SCHEDULE_UPDATE, confidence, "structural", audit, schedule, review,
            month_review, year_review,
        )
    if audit >= 3 and audit >= schedule and audit >= best_period_score:
        confidence = 0.92 if audit >= 5 else 0.8
        return IntentDecision(
            WORKOUT_AUDIT, confidence, "structural", audit, schedule, review,
            month_review, year_review,
        )
    if science >= 3 and science >= audit and science >= schedule and science >= best_period_score:
        confidence = 0.9 if science >= 5 else 0.8
        return IntentDecision(
            SCIENCE_LOOKUP, confidence, "structural_science", audit, schedule, review,
            month_review, year_review,
        )
    if best_period_score > 0 and best_period_score >= audit and best_period_score >= schedule:
        return IntentDecision(
            best_period, 0.6, "structural_weak", audit, schedule, review,
            month_review, year_review,
        )
    # DIY "should I use this plan?" with day names is advice, not a calendar rebuild.
    if schedule > 0 and schedule >= audit and not is_plan_advice_message(message):
        return IntentDecision(
            SCHEDULE_UPDATE, 0.55, "structural_weak", audit, schedule, review,
            month_review, year_review,
        )
    if audit > 0:
        return IntentDecision(
            WORKOUT_AUDIT, 0.55, "structural_weak", audit, schedule, review,
            month_review, year_review,
        )
    return IntentDecision(
        GENERAL_CHAT, 0.85, "structural_default", audit, schedule, review,
        month_review, year_review,
    )


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
