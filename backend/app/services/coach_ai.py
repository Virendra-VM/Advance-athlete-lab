"""Coach generation pipeline.

    athlete context + science retrieval + safety rules
        -> provider (JSON) -> pydantic validation -> safety validator -> persist

Every surface degrades gracefully: provider missing or failing falls back to the
deterministic templates, and a plan that fails the safety validator is replaced
rather than shown.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import AI_DEBUG
from app.ai_schemas import ChatReplyJSON, DailyAdviceJSON, WeekPlanJSON
from app.models import Activity, ActivityNote, AthleteProfile, CoachMessage, DailyAdviceSnapshot, PlannedWorkout, TrainingPlan, WeeklyAdviceSnapshot
from app.services.ai import ProviderError, provider_chain
from app.services.athlete_coach_context import build_athlete_coach_context
from app.services.coach_safety import (
    apply_joint_safe_recovery_mode,
    detect_clinical_boundary,
    detect_red_flags,
    flag_clinical_injury,
    safety_prompt_rules,
    sports_for_retrieval,
    strip_intensity,
    validate_plan,
)
from app.services.coach_templates import (
    build_template_advice,
    build_template_daily_brief,
    build_template_hrv_brief,
    build_template_load_brief,
    build_template_rhr_brief,
    build_template_season_brief,
    build_template_sleep_brief,
    build_template_stress_brief,
    build_template_week,
    build_template_week_brief,
)
from app.services.science_kb import (
    citation_slugs,
    format_science_for_prompt,
    grounded_hits,
    retrieve_science,
)
from app.services.ai_coach import (
    AUTOPSY_SCHEMA,
    BASE_SYSTEM_PROMPT as SYSTEM_PROMPT,
    athlete_state_block,
    autopsy_task_for_packet,
    chat_system_prompt,
    chat_task,
    coach_modality,
    retrieval_query_for_modality,
    science_sports_for_modality,
    schedule_system_prompt,
    schedule_task,
    day_adjust_task,
    week_plan_review_task,
    science_system_prompt,
    science_task,
    system_prompt_for_modality,
    template_autopsy,
    template_clinical_veto,
    template_general_chat,
    template_off_topic,
    template_schedule,
    template_day_adjust,
    template_week_plan_review,
    template_science_lookup,
    template_week_review,
    today_call_prompt_block,
    week_review_system_prompt,
    week_review_task,
    review_week_window,
)
from app.services.coach_intent import (
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    OFF_TOPIC,
    SCHEDULE_UPDATE,
    WEEK_PLAN_REVIEW,
    SCIENCE_LOOKUP,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
    classify_chat_intent_detailed,
    normalize_intent,
)
from app.services.session_plan import build_session_plan_overlay
from app.services.periodization import season_prompt_block
from app.services.session_telemetry import (
    analyze_activity,
    laps_are_uninformative,
    match_activity_for_message,
)
from app.services.session_blueprints import downgrade_today_workout, enrich_plan, enrich_workout
from app.services.week_from_chat import coerce_week_plan, parse_week_plan_from_text

logger = logging.getLogger(__name__)

WEEK_PLAN_SCHEMA = """{
  "title": "string",
  "summary": "string, 1-3 sentences",
  "focus": "string, short phrase",
  "week_start": "YYYY-MM-DD",
  "workouts": [
    {
      "date": "YYYY-MM-DD",
      "sport": "string",
      "title": "string",
      "session_type": "rest|easy|long|tempo|threshold|intervals|hills|speed|strength|mobility|cross-training|race",
      "duration_min": number,
      "distance_m": number or null,
      "intensity": "string",
      "description": "string with warm-up, named main set, cool-down stretches/foam roll",
      "structure": [{"segment": "Warm-up|Main set|Cool-down", "duration_min": number, "intensity": "string", "detail": "named work: exercises, intervals, poses, stretches"}]
    }
  ],
  "coach_notes": "string",
  "citations": ["S1"]
}"""

ADVICE_SCHEMA = """{
  "headline": "string, max 10 words, no markdown",
  "recommendation": "string with REAL newlines. Lead sentence, then numbered sessions. Each session is '1. Name — duration' followed by '- Label: value' bullets. Bold labels with **Label:** only. Never one packed paragraph.",
  "session_adjustment": "string or null, one or two short sentences, **Label:** allowed, no essays",
  "rationale": "string referencing the athlete's own numbers, max two sentences",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null
}"""

HEALTH_METRIC_ADVICE_SCHEMA = """{
  "headline": "string, max 10 words, no markdown",
  "recommendation": "string with REAL newlines. Lead sentence about THIS metric only, then numbered actions that only interpret or record this metric. Each action is '1. Name — constraint' followed by '- Label: value' bullets. Never one packed paragraph.",
  "session_adjustment": "string or null, one or two short sentences about THIS metric only",
  "rationale": "string referencing this metric's own numbers, max two sentences",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null
}"""

HEALTH_METRIC_SYSTEM_PROMPT = """You write a short week brief about ONE health metric inside Advance Athlete Lab.
You only interpret that metric versus the athlete's own recent usual.
You never mention workouts, sessions, intervals, races, strength, kilometres, training load, ACWR, or any other health metric.
You never prescribe training. Do not say train as planned, keep easy days, skip quality, or convert sessions.
Habits are allowed only when they change THIS metric (for example bedtime on the Sleep page, wearing the watch so this metric records).
Respond with JSON matching the requested schema."""

HEALTH_METRIC_BAN = """HARD RULES
This brief is the named metric only.
Do not mention workouts, sessions, intervals, races, strength, kilometres, training load, ACWR, or any other health metric (no HRV, sleep, stress, resting HR, or steps unless that IS this page).
Do not prescribe training. Numbered actions may only cover how to read this metric, how it is recorded, and habits that change THIS metric.
Never more than two consecutive sentences per block. Do not pack into one paragraph."""

_TRAINING_LEAK_RE = re.compile(
    r"\b("
    r"workout|workouts|interval|intervals|kilometre|kilometres|kilometer|kilometers|"
    r"acwr|tempo|long run|easy day|easy days|quality session|train as planned|"
    r"training load|skip quality|race pace"
    r")\b",
    re.I,
)
_CROSS_METRIC_RE = {
    "sleep": re.compile(
        r"\b(hrv|rmssd|stress|steps?|calories|acwr)\b|resting\s*h(?:eart)?\s*r",
        re.I,
    ),
    "hrv": re.compile(
        r"\b(sleep|stress|steps?|calories|acwr)\b|resting\s*h(?:eart)?\s*r",
        re.I,
    ),
    "stress": re.compile(
        r"\b(hrv|rmssd|sleep|steps?|calories|acwr)\b|resting\s*h(?:eart)?\s*r",
        re.I,
    ),
    "rhr": re.compile(r"\b(hrv|rmssd|sleep|stress|steps?|calories|acwr)\b", re.I),
    "daily": re.compile(r"\b(hrv|rmssd|sleep|stress|acwr)\b|resting\s*h(?:eart)?\s*r", re.I),
}


def health_brief_off_topic(topic: str, advice: dict | None) -> bool:
    """True when a health brief wandered into training or another metric."""
    if not advice or topic not in _CROSS_METRIC_RE:
        return False
    blob = " ".join(
        str(advice.get(key) or "")
        for key in ("headline", "recommendation", "session_adjustment", "rationale")
    )
    if _TRAINING_LEAK_RE.search(blob):
        return True
    return bool(_CROSS_METRIC_RE[topic].search(blob))


_SESSION_PRESCRIPTION_RE = re.compile(
    r"\b\d+\s*[x×]\s*\d|\b\d+\s*x\s*\d+\s*(m|km|min)\b|\bper\s*km\b|\b\d+:\d{2}\s*/\s*km\b",
    re.I,
)
_REPLAN_WORD_RE = re.compile(r"\breplan(?:ning|ned)?\b", re.I)


def season_brief_off_topic(season: dict | None, advice: dict | None) -> bool:
    """True when a season brief prescribes sessions or pushes a replan with no trigger."""
    if not advice:
        return False
    blob = " ".join(
        str(advice.get(key) or "")
        for key in ("headline", "recommendation", "session_adjustment", "rationale")
    )
    if _SESSION_PRESCRIPTION_RE.search(blob):
        return True
    has_trigger = bool((season or {}).get("replan_trigger_codes"))
    return bool(not has_trigger and _REPLAN_WORD_RE.search(blob))


SEASON_ADVICE_SCHEMA = """{
  "headline": "string, max 10 words, names the current phase, no markdown",
  "recommendation": "string with REAL newlines. Lead sentence about where they are in the season, then numbered points that explain this block or name the next planner action. Each point is '1. Name — short constraint' followed by '- Label: value' bullets. Never one packed paragraph.",
  "session_adjustment": "string or null, one or two short sentences naming Replan, Rebuild, or 'no change needed'",
  "rationale": "string referencing their own phase, week number, or race countdown, max two sentences",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null
}"""

SEASON_SYSTEM_PROMPT = """You explain an athlete's SEASON PLAN inside Advance Athlete Lab.
The season skeleton is drawn by a deterministic periodization engine working backward from the A-race. You do not author it.
Your job: say where they are in the season, what the current phase is for, and which planner action to take next (Replan, Rebuild, or nothing).
You never invent or restate phase dates other than the ones given to you, and you never write individual workouts — the Coach page does that.
Respond with JSON matching the requested schema."""

SEASON_BAN = """HARD RULES
Explain the season, do not rewrite it. Never propose different phase dates, phase lengths, or a different phase order.
Do not prescribe specific sessions, paces, distances, or interval sets. Point at the Coach page for sessions.
Only recommend Replan when a trigger is listed below. Only recommend Rebuild when the A-race itself changed or there is no plan.
If no trigger is listed, say plainly that no plan change is needed this week.
Do not lecture about sleep, HRV, stress, or resting HR — those have their own pages.
Never more than two consecutive sentences per block. Do not pack into one paragraph."""

CHAT_SCHEMA = """{
  "reply": "string, bullet-only GENERAL_CHAT answer: skip autopsy sections, max two sentences per bullet, optional bold REFRAME",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "GENERAL_CHAT"
}"""

WEEK_PLAN_REVIEW_SCHEMA = """{
  "reply": "string, review-only: phase fit, conflicts, schedule notes, safety, science triplets. No week table.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "WEEK_PLAN_REVIEW"
}"""

SCHEDULE_SCHEMA = """{
  "reply": "string, Pro Olympic Coach call: TODAY'S CALL status, one locker-room directive, 5-col week table, spine DO NOTs, science/lingo/analogy bullets. No essays.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "SCHEDULE_UPDATE",
  "week_plan": {
    "title": "string",
    "summary": "string",
    "focus": "string",
    "week_start": "YYYY-MM-DD",
    "workouts": [
      {
        "date": "YYYY-MM-DD",
        "sport": "string",
        "title": "string",
        "session_type": "rest|easy|long|tempo|threshold|intervals|hills|speed|strength|mobility|cross-training|race",
        "duration_min": number,
        "intensity": "string",
        "description": "string with warm-up, named main set, cool-down",
        "structure": [{"segment": "Warm-up|Main set|Cool-down", "duration_min": number, "intensity": "string", "detail": "named exercises, intervals, poses, stretches, foam roll"}]
      }
    ]
  }
}"""

DAY_ADJUST_SCHEMA = """{
  "reply": "string, today-only call: TODAY'S CALL, one locker-room sentence, today's session change, warmup/main/cooldown detail. Do not rewrite other days.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "DAY_ADJUST",
  "week_plan": {
    "title": "string",
    "summary": "string",
    "focus": "string",
    "week_start": "YYYY-MM-DD",
    "workouts": [
      {
        "date": "YYYY-MM-DD (TODAY only)",
        "sport": "string",
        "title": "string",
        "session_type": "rest|easy|long|tempo|threshold|intervals|hills|speed|strength|mobility|cross-training|race",
        "duration_min": number,
        "intensity": "string",
        "description": "string with warm-up, named main set, cool-down",
        "structure": [{"segment": "Warm-up|Main set|Cool-down", "duration_min": number, "intensity": "string", "detail": "named work"}]
      }
    ]
  }
}"""

WEEK_REVIEW_SCHEMA = """{
  "reply": "string, week debrief: WEEK GRADE, WHAT LANDED table, RECOVERY COST, NEXT WEEK'S CALL, science triplets. No ride autopsy, no NP/IF/TSS/laps.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "WEEK_REVIEW"
}"""

SCIENCE_SCHEMA = """{
  "reply": "string, science teaching: THE CALL, THE SCIENCE with [S#] or Evidence: Not in playbook, locker-room lingo, analogy, FOR YOU bullets. No invented papers.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "SCIENCE_LOOKUP"
}"""

ESCALATION_REPLY = (
    "What you're describing needs a professional, not a training plan. Please stop training and "
    "get assessed by a doctor or physiotherapist — I can't safely coach around symptoms like "
    "these. Once you're cleared, tell me what they advised and we'll rebuild carefully."
)


class PlanWeekNotCurrentError(ValueError):
    """Raised when a caller asks to generate a week other than the current one."""


WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _monday_of(value: date) -> date:
    return value - timedelta(days=value.weekday())


def current_week_monday(today: date | None = None) -> date:
    return _monday_of(today or date.today())


def resolve_clock(tz_name: str | None = None) -> dict:
    """Athlete-local 'now'. Browser IANA zone when provided; otherwise UTC."""
    label = (tz_name or "").strip() or "UTC"
    try:
        tz = ZoneInfo(label)
    except Exception:  # noqa: BLE001 - unknown zone names must not break coaching
        tz = ZoneInfo("UTC")
        label = "UTC"
    now = datetime.now(tz)
    today = now.date()
    week_start = _monday_of(today)
    weekday_index = today.weekday()
    return {
        "timezone": label,
        "tz": tz,
        "now": now,
        "today": today,
        "now_iso": now.isoformat(timespec="minutes"),
        "local_date": today.isoformat(),
        "local_time": now.strftime("%H:%M"),
        "weekday": WEEKDAYS[weekday_index],
        "weekday_index": weekday_index,
        "week_start": week_start,
        "week_start_iso": week_start.isoformat(),
        "week_end_iso": (week_start + timedelta(days=6)).isoformat(),
        "days_left_including_today": 7 - weekday_index,
        "remaining_days_after_today": 6 - weekday_index,
    }


def format_clock_block(clock: dict) -> str:
    if clock["remaining_days_after_today"] == 0:
        remaining = "none — today is the last day of this training week"
    else:
        remaining = (
            f"{clock['remaining_days_after_today']} day(s) after today, through Sunday "
            f"{clock['week_end_iso']}"
        )
    if clock["weekday_index"] >= 5:
        orientation = (
            "Late week. Do not say 'start this week' or 'begin the week easy'. "
            "Talk about what already happened and what remains (today and/or Sunday)."
        )
    elif clock["weekday_index"] >= 3:
        orientation = (
            "Mid/late week. Adjust remaining sessions. Do not restart the week from Monday."
        )
    else:
        orientation = "Early week. Planning language about the whole week is appropriate."
    return f"""NOW (athlete local time — this is ground truth)
- Current datetime: {clock['now_iso']}
- Today: {clock['weekday']} {clock['local_date']} at {clock['local_time']} ({clock['timezone']})
- This training week: Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}
- Days left including today: {clock['days_left_including_today']} ({remaining})
- Orientation: {orientation}
- An activity dated {clock['local_date']} happened TODAY. Never narrate it as a past day.
- Dates before today already happened. Dates after today are upcoming."""


def _parse_local_date(value, tz: ZoneInfo) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date) and not isinstance(value, datetime):
        return value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(tz).date()


_SESSION_FILE_KEYS = ("laps", "exercises", "streams", "work_laps", "points")
_SESSION_AUDIT_METRICS = ("np", "pct_ftp", "avg_power", "max_power", "avg_cadence", "lap_count")


def _activity_digest_row(
    activity: dict, clock: dict, *, include_session_audit: bool = False
) -> dict:
    local = _parse_local_date(activity.get("activity_date") or activity.get("date"), clock["tz"])
    skip = {
        "provider",
        "external_activity_id",
        "distance_m",
        "moving_time_s",
        "average_heartrate",
        "max_heartrate",
        "sport_type",
    }
    row = {key: value for key, value in activity.items() if key not in skip and value is not None}
    row["date"] = local.isoformat() if local else str(activity.get("activity_date") or activity.get("date") or "")[:10]
    row["when"] = _when_label(local, clock["today"]) if local else activity.get("when")
    row["sport"] = activity.get("sport") or activity.get("sport_type")
    row["name"] = activity.get("name")
    if "km" not in row:
        row["km"] = round((activity.get("distance_m") or 0) / 1000.0, 2)
    if "minutes" not in row:
        row["minutes"] = round((activity.get("moving_time_s") or 0) / 60.0)
    if "avg_hr" not in row:
        row["avg_hr"] = activity.get("average_heartrate")
    if "max_hr" not in row:
        row["max_hr"] = activity.get("max_heartrate")
    for key in _SESSION_FILE_KEYS:
        row.pop(key, None)
    if not include_session_audit:
        for key in _SESSION_AUDIT_METRICS:
            row.pop(key, None)
    return row


def _when_label(activity_day: date, today: date) -> str:
    delta = (today - activity_day).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta == -1:
        return "tomorrow"
    if delta > 1:
        return f"{delta} days ago"
    return f"in {-delta} days"


def format_data_sources_block(context: dict) -> str:
    """Tell the model which athlete data was loaded before answering."""
    sources = context.get("data_sources") or {}
    if not sources:
        return "DATA SOURCES: profile only — no integration summary available."
    lines = [
        "DATA SOURCES (ground truth — base every answer on what is loaded below)",
        f"- Profile + constraints: {'yes' if sources.get('profile_loaded') else 'no'}",
    ]
    if sources.get("planning_notes"):
        flags = ", ".join(sources.get("planning_note_flags") or []) or "free text"
        lines.append(f"- Athlete planning notes: yes ({flags})")
        for hint in sources.get("planning_note_hints") or []:
            lines.append(f"  · {hint}")
    else:
        lines.append("- Athlete planning notes: none on file")
    lines.append(
        f"- Strava connected: {'yes' if sources.get('strava_connected') else 'no'}"
    )
    lines.append(
        f"- COROS connected: {'yes' if sources.get('coros_connected') else 'no'}"
        + (
            f" (last sync {sources['coros_last_synced_at']})"
            if sources.get("coros_last_synced_at")
            else ""
        )
    )
    activity_count = sources.get("recent_activities_count") or 0
    by_provider = sources.get("recent_activities_by_provider") or {}
    provider_bits = ", ".join(f"{name}={count}" for name, count in sorted(by_provider.items()))
    lines.append(
        f"- Recent activities (28d): {activity_count}"
        + (f" ({provider_bits})" if provider_bits else "")
    )
    lines.append(f"- COROS health nights in context: {sources.get('coros_health_days') or 0}")
    lines.append(
        f"- COROS fitness snapshot: {'yes' if sources.get('coros_fitness_loaded') else 'no'}"
    )
    lines.append(
        f"- COROS training load: {'yes' if sources.get('coros_training_load_loaded') else 'no'}"
    )
    lines.append(
        f"- Active season plan in context: {'yes' if sources.get('season_plan_loaded') else 'no'}"
    )
    lines.append(
        "- If a source is missing, say so explicitly — never invent Strava/COROS numbers."
    )
    return "\n".join(lines)


def _context_digest(
    context: dict, clock: dict | None = None, *, include_session_audit: bool = False
) -> str:
    """Compact, prompt-friendly view of the athlete. Excludes sensitive extras.

    Laps, streams, and autopsy metrics of the last synced file stay out of this
    digest unless ``include_session_audit`` is True (WORKOUT_AUDIT only).
    Week recaps use WEEK REVIEW PACKET instead of last-file laps.
    """
    clock = clock or resolve_clock()
    profile = dict(context.get("profile") or {})
    profile.pop("name", None)
    coros = context.get("coros") or {}
    physiology = context.get("physiology") or {}
    # Zones are useful but keep the prompt lean — names + watt/bpm bounds only.
    zones = {
        "power": [
            {"name": zone.get("name"), "low_w": zone.get("low_w"), "high_w": zone.get("high_w")}
            for zone in (physiology.get("power_zones") or [])
        ],
        "hr": [
            {
                "name": zone.get("name"),
                "low_bpm": zone.get("low_bpm"),
                "high_bpm": zone.get("high_bpm"),
            }
            for zone in (physiology.get("hr_zones") or [])
        ],
    }
    digest = {
        "data_sources": context.get("data_sources") or {},
        "profile": profile,
        "physiology": {
            "ftp_watts": physiology.get("ftp_watts"),
            "ftp_source": physiology.get("ftp_source"),
            "ftp_estimated_watts": physiology.get("ftp_estimated_watts"),
            "lthr_bpm": physiology.get("lthr_bpm"),
            "lthr_source": physiology.get("lthr_source"),
            "max_hr_bpm": physiology.get("max_hr_bpm"),
            "max_hr_source": physiology.get("max_hr_source"),
            "resting_hr_bpm": physiology.get("resting_hr_bpm"),
            "zones": zones,
        },
        "readiness_flags": context.get("readiness_flags") or [],
        "recent_activities": [
            _activity_digest_row(
                activity, clock, include_session_audit=include_session_audit
            )
            for activity in (context.get("recent_activities") or [])[:20]
        ],
        "latest_health": coros.get("latest_health"),
        "health_trend": coros.get("health_trend") or [],
        "fitness": coros.get("fitness"),
        "training_load": coros.get("training_load"),
        "upcoming_schedule": coros.get("schedule") or [],
        "season": context.get("season"),
    }
    return json.dumps(digest, indent=2, default=str)


def _plan_digest(plan: dict | None, clock: dict) -> str:
    if not plan:
        return "CURRENT WEEK PLAN: none generated yet. The athlete can still generate this week from the chat."
    workouts = []
    for workout in (plan.get("plan") or {}).get("workouts") or []:
        try:
            day = date.fromisoformat(str(workout.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        workouts.append(
            {
                "date": day.isoformat(),
                "when": _when_label(day, clock["today"]),
                "title": workout.get("title"),
                "session_type": workout.get("session_type"),
                "intensity": workout.get("intensity"),
                "duration_min": workout.get("duration_min"),
                "completed": bool(workout.get("completed_activity_id")),
            }
        )
    return json.dumps(
        {
            "title": (plan.get("plan") or {}).get("title"),
            "on_schedule": bool(plan.get("on_schedule")),
            "workouts": workouts,
        },
        indent=2,
    )


_QUALITY_TOKENS = (
    "hard",
    "threshold",
    "interval",
    "vo2",
    "quality",
    "race",
    "tempo",
    "sweet spot",
)

_SCIENCE_QUERY_BOOST = (
    ("acwr", "acute chronic workload ratio injury risk training load"),
    ("hrv", "heart rate variability recovery autonomic nervous system"),
    ("ftp", "functional threshold power cycling training zones"),
    ("vo2", "VO2max intervals aerobic capacity"),
    ("lthr", "lactate threshold heart rate endurance zones"),
    ("sleep", "sleep recovery training adaptation"),
    ("menstrual", "menstrual cycle training female athlete"),
    ("periodization", "periodization mesocycle recovery endurance"),
    ("zone 2", "zone 2 aerobic base mitochondrial fat oxidation"),
    ("overreaching", "functional overreaching recovery load management"),
)


def _mean(values: list) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _looks_quality(blob: str) -> bool:
    text = (blob or "").lower()
    return any(token in text for token in _QUALITY_TOKENS)


def _chat_retrieval_query(message: str) -> str:
    """Ground GENERAL_CHAT in the science corpus, not the last ride file."""
    text = (message or "").lower()
    extra = [boost for needle, boost in _SCIENCE_QUERY_BOOST if needle in text]
    if extra:
        return f"{(message or '')[:240]} {' '.join(extra[:2])}"
    return message


def build_week_review_packet(
    context: dict,
    clock: dict,
    review_plan: dict | None,
    message: str,
) -> dict:
    """Planned vs executed for one training week. No laps, no last-file telemetry."""
    start, end, label = review_week_window(clock, message)
    tz = clock["tz"]
    executed_by_day: dict[date, list[dict]] = {}
    for activity in context.get("recent_activities") or []:
        day = _parse_local_date(
            activity.get("activity_date") or activity.get("date"), tz
        )
        if day is None or day < start or day > end:
            continue
        minutes = activity.get("minutes")
        if minutes is None:
            minutes = round((activity.get("moving_time_s") or 0) / 60.0)
        km = activity.get("km")
        if km is None:
            km = round((activity.get("distance_m") or 0) / 1000.0, 2)
        executed_by_day.setdefault(day, []).append(
            {
                "name": activity.get("name") or activity.get("sport") or "Session",
                "sport": activity.get("sport") or activity.get("sport_type"),
                "minutes": minutes,
                "km": km,
                "avg_hr": activity.get("avg_hr") or activity.get("average_heartrate"),
                "when": _when_label(day, clock["today"]),
            }
        )

    planned_by_day: dict[date, list[dict]] = {}
    for workout in ((review_plan or {}).get("plan") or {}).get("workouts") or []:
        try:
            day = date.fromisoformat(str(workout.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        if day < start or day > end:
            continue
        planned_by_day.setdefault(day, []).append(
            {
                "title": workout.get("title") or workout.get("session_type") or "Planned",
                "sport": workout.get("sport"),
                "session_type": workout.get("session_type"),
                "intensity": workout.get("intensity"),
                "duration_min": workout.get("duration_min"),
                "completed": bool(workout.get("completed_activity_id")),
            }
        )

    days = []
    cursor = start
    total_minutes = 0
    total_km = 0.0
    session_count = 0
    quality_days = 0
    while cursor <= end:
        planned = planned_by_day.get(cursor) or []
        executed = executed_by_day.get(cursor) or []
        weekday = WEEKDAYS[cursor.weekday()]
        planned_rest = any(
            str(item.get("session_type") or item.get("title") or "").lower() in {"rest", "off"}
            or "rest" in str(item.get("title") or "").lower()
            for item in planned
        )
        if executed:
            names = " + ".join(str(item.get("name") or "Session") for item in executed)
            minutes = sum(item.get("minutes") or 0 for item in executed)
            total_minutes += minutes
            total_km += sum(float(item.get("km") or 0) for item in executed)
            session_count += len(executed)
            quality = any(
                _looks_quality(
                    f"{item.get('name') or ''} {item.get('sport') or ''}"
                )
                for item in executed
            ) or any(
                _looks_quality(
                    f"{item.get('title') or ''} {item.get('session_type') or ''} {item.get('intensity') or ''}"
                )
                for item in planned
            )
            if quality:
                quality_days += 1
            status = "Unplanned" if not planned else "Done"
            note = f"{minutes:.0f} min" if minutes else "Completed"
            days.append(
                {
                    "date": cursor.isoformat(),
                    "day": weekday,
                    "session": names,
                    "status": status,
                    "note": note,
                    "planned": planned,
                    "executed": executed,
                }
            )
        elif planned_rest or (
            planned and all(
                str(item.get("session_type") or "").lower() in {"rest", "mobility", "easy"}
                and "rest" in str(item.get("title") or item.get("session_type") or "").lower()
                for item in planned
            )
        ):
            title = (planned[0].get("title") if planned else None) or "Rest"
            days.append(
                {
                    "date": cursor.isoformat(),
                    "day": weekday,
                    "session": title,
                    "status": "Rest",
                    "note": "Planned off",
                    "planned": planned,
                    "executed": [],
                }
            )
        elif planned:
            title = " + ".join(str(item.get("title") or "Planned") for item in planned)
            days.append(
                {
                    "date": cursor.isoformat(),
                    "day": weekday,
                    "session": title,
                    "status": "Missed",
                    "note": "No file synced",
                    "planned": planned,
                    "executed": [],
                }
            )
        else:
            days.append(
                {
                    "date": cursor.isoformat(),
                    "day": weekday,
                    "session": "—",
                    "status": "Rest",
                    "note": "No plan, no file",
                    "planned": [],
                    "executed": [],
                }
            )
        cursor += timedelta(days=1)

    nights = []
    for row in ((context.get("coros") or {}).get("health_trend") or []):
        try:
            night = date.fromisoformat(str(row.get("metric_date"))[:10])
        except (TypeError, ValueError):
            continue
        if start <= night <= end:
            nights.append(row)

    safety = context.get("safety") or {}
    load = safety.get("load") or {}
    return {
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": label,
        },
        "days": days,
        "totals": {
            "sessions": session_count,
            "minutes": round(total_minutes),
            "km": round(total_km, 1),
            "quality_days": quality_days,
            "planned_sessions": sum(len(items) for items in planned_by_day.values()),
        },
        "recovery": {
            "nights": len(nights),
            "avg_sleep_score": _mean([row.get("sleep_score") for row in nights]),
            "avg_sleep_min": _mean([row.get("sleep_duration_min") for row in nights]),
            "avg_hrv": _mean([row.get("hrv") for row in nights]),
            "avg_stress": _mean([row.get("stress") for row in nights]),
            "avg_rhr": _mean([row.get("resting_heart_rate") for row in nights]),
        },
        "load": {
            "acute_minutes": load.get("acute_minutes"),
            "chronic_minutes": load.get("chronic_minutes"),
            "minutes_acwr": load.get("minutes_acwr"),
        },
    }


def _retrieve(
    db: Session,
    query: str,
    profile: AthleteProfile,
    k: int = 6,
    extra_sports: list[str] | None = None,
) -> list[dict]:
    sports = list(extra_sports or []) + list(sports_for_retrieval(profile))
    return retrieve_science(db, query, sports=sports, k=k)


def _call_provider(system: str, user: str) -> tuple[dict, str, str] | None:
    """Try each configured provider once. Returns (data, provider, model) or None."""
    for provider in provider_chain():
        started = time.perf_counter()
        if AI_DEBUG:
            logger.info("Coach AI trying %s/%s", provider.name, provider.model)
        try:
            response = provider.generate_json(system, user)
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "Coach AI %s/%s succeeded in %.0fms",
                response.provider,
                response.model,
                elapsed_ms,
            )
            return response.data, response.provider, response.model
        except ProviderError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "Provider %s failed after %.0fms: %s",
                provider.name,
                elapsed_ms,
                exc,
            )
        except Exception as exc:  # noqa: BLE001 - never let a provider break the request
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "Provider %s raised after %.0fms: %s",
                provider.name,
                elapsed_ms,
                exc,
            )
    return None


# ---------------------------------------------------------------- weekly plan


def build_week_plan_prompt(
    context: dict,
    safety: dict,
    hits: list[dict],
    week_start: date,
    clock: dict | None = None,
) -> str:
    """Shared by the live endpoint and the provider evaluation harness."""
    clock = clock or resolve_clock()
    remaining_start = max(clock["today"], week_start)
    remaining_end = week_start + timedelta(days=6)
    return f"""{format_clock_block(clock)}

{format_data_sources_block(context)}

ATHLETE CONTEXT
{_context_digest(context, clock)}

{season_prompt_block(context.get("season"))}

SAFETY RULES (hard limits)
{safety_prompt_rules(safety, weekday_index=clock["weekday_index"])}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

TASK
Build the training week starting {week_start.isoformat()} (Monday).
Today is {clock['weekday']} {clock['local_date']}. Do not prescribe new training on dates before today
— those days already happened. Plan only {remaining_start.isoformat()} through {remaining_end.isoformat()}.
If they already trained today, do not stack another hard session on top.
Give every remaining session a concrete main set, not a vague label. Respect every safety limit above.
Every workout must include structure with Warm-up, Main set, and Cool-down. Main set names the actual work
(exercises, interval reps, swim sets, yoga poses). Cool-down includes stretches, foam roll, or mobility.

Respond with JSON matching exactly this shape:
{WEEK_PLAN_SCHEMA}"""


def plan_retrieval_query(context: dict, profile: AthleteProfile) -> str:
    goal = context["profile"].get("primary_goal") or "general fitness"
    season = context.get("season") or {}
    phase = (season.get("current_phase") or {}).get("phase_type")
    phase_bit = f" {phase} phase periodization" if phase else ""
    return f"weekly training structure for {goal}{phase_bit} {' '.join(sports_for_retrieval(profile))}"


def generate_week_plan(
    db: Session,
    profile: AthleteProfile,
    week_start: date | None = None,
    persist: bool = True,
    timezone_name: str | None = None,
) -> dict:
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
    safety = context["safety"]
    start = _monday_of(week_start or clock["today"])
    allowed = current_week_monday(clock["today"])
    if start != allowed:
        raise PlanWeekNotCurrentError(
            f"Only the current week ({allowed.isoformat()}) can be planned."
        )

    hits = _retrieve(db, plan_retrieval_query(context, profile), profile)
    user_prompt = build_week_plan_prompt(context, safety, hits, start, clock=clock)

    result = _call_provider(SYSTEM_PROMPT, user_prompt)
    provider_name, model_name = "rules", "deterministic-template"
    plan_data: dict | None = None
    generation_notes: list[str] = []

    if result is not None:
        raw, provider_name, model_name = result
        try:
            plan_data = WeekPlanJSON.model_validate(raw).model_dump(mode="json")
        except ValidationError as exc:
            generation_notes.append(
                f"{provider_name} returned invalid plan JSON ({exc.error_count()} issue(s)); "
                "used the deterministic template instead."
            )
            logger.warning("Plan schema validation failed for %s: %s", provider_name, exc)
            plan_data = None
            provider_name, model_name = "rules", "deterministic-template"
    else:
        generation_notes.append(
            "No AI provider is configured or reachable; built the week from deterministic rules."
        )

    if plan_data is None:
        plan_data = build_template_week(context, safety, start, today=clock["today"])

    # Force the requested week regardless of what the model produced.
    plan_data["week_start"] = start.isoformat()

    validation = validate_plan(plan_data, safety)
    if validation["blocked"]:
        generation_notes.append(
            "Generated plan failed safety validation and was replaced with a conservative week."
        )
        fallback = build_template_week(context, safety, start, today=clock["today"])
        validation = validate_plan(fallback, safety)
        provider_name, model_name = "rules", "deterministic-template"
        if validation["blocked"]:
            # Last resort: an all-easy week is always safe to show.
            validation = validate_plan(strip_intensity(fallback), safety)

    plan_data = validation["plan"]
    issues = validation["issues"]
    plan_data = enrich_plan(plan_data, safety)
    citations = citation_slugs(hits) if provider_name != "rules" else []

    stored_id = None
    if persist:
        stored_id = _persist_plan(
            db,
            profile,
            plan_data,
            start,
            provider_name,
            model_name,
            issues,
            citations,
            safety=safety,
        )

    return {
        "plan_id": stored_id,
        "provider": provider_name,
        "model": model_name,
        "week_start": start.isoformat(),
        "plan": plan_data,
        "safety_issues": issues,
        "generation_notes": generation_notes,
        "citations": [hit["citation"] for hit in hits] if citations else [],
        "disclaimer": safety["disclaimer"],
        "on_schedule": False,
    }


def _persist_plan(
    db: Session,
    profile: AthleteProfile,
    plan_data: dict,
    week_start: date,
    provider: str,
    model: str,
    issues: list[dict],
    citations: list[str],
    safety: dict | None = None,
) -> int:
    existing = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_profile_id == profile.id,
            TrainingPlan.week_start == week_start,
            TrainingPlan.status == "active",
        )
        .all()
    )
    for plan in existing:
        plan.status = "superseded"

    record = TrainingPlan(
        athlete_profile_id=profile.id,
        week_start=week_start,
        title=plan_data.get("title"),
        summary=plan_data.get("summary"),
        focus=plan_data.get("focus"),
        provider=provider,
        model=model,
        status="active",
        published_at=None,
        safety_notes=json.dumps(issues),
        citations=json.dumps(citations),
        raw_json=json.dumps(plan_data, default=str),
    )
    db.add(record)
    db.flush()

    for workout in plan_data.get("workouts") or []:
        try:
            workout_date = date.fromisoformat(str(workout.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        filled = enrich_workout(workout, safety)
        db.add(
            PlannedWorkout(
                training_plan_id=record.id,
                athlete_profile_id=profile.id,
                workout_date=workout_date,
                sport=filled.get("sport"),
                title=filled.get("title"),
                session_type=filled.get("session_type"),
                duration_min=filled.get("duration_min"),
                distance_m=filled.get("distance_m"),
                intensity=filled.get("intensity"),
                description=filled.get("description"),
                structure_json=json.dumps(filled.get("structure") or []),
            )
        )

    db.commit()
    return record.id


def get_active_plan(db: Session, profile_id: int, week_start: date | None = None) -> dict | None:
    query = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_profile_id == profile_id,
        TrainingPlan.status == "active",
    )
    if week_start is not None:
        query = query.filter(TrainingPlan.week_start == week_start)
    record = query.order_by(TrainingPlan.week_start.desc()).first()
    if record is None:
        return None

    workouts = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.training_plan_id == record.id)
        .order_by(PlannedWorkout.workout_date.asc())
        .all()
    )

    def _load(value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    return {
        "plan_id": record.id,
        "provider": record.provider,
        "model": record.model,
        "week_start": record.week_start.isoformat(),
        "plan": {
            "title": record.title,
            "summary": record.summary,
            "focus": record.focus,
            "week_start": record.week_start.isoformat(),
            "workouts": [
                enrich_workout(
                    {
                        "id": workout.id,
                        "date": workout.workout_date.isoformat(),
                        "sport": workout.sport,
                        "title": workout.title,
                        "session_type": workout.session_type,
                        "duration_min": workout.duration_min,
                        "distance_m": workout.distance_m,
                        "intensity": workout.intensity,
                        "description": workout.description,
                        "structure": _load(workout.structure_json, []),
                        "completed_activity_id": workout.completed_activity_id,
                    }
                )
                for workout in workouts
            ],
            "coach_notes": (_load(record.raw_json, {}) or {}).get("coach_notes"),
        },
        "safety_issues": _load(record.safety_notes, []),
        "generation_notes": [],
        "citations": [],
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "on_schedule": record.published_at is not None,
    }


def publish_plan_to_schedule(db: Session, profile: AthleteProfile, plan_id: int) -> dict:
    """Put one generated week on the Schedule. Earlier published copies of this week drop off."""
    record = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.id == plan_id,
            TrainingPlan.athlete_profile_id == profile.id,
        )
        .first()
    )
    if record is None:
        raise LookupError("plan_not_found")
    if record.status != "active":
        raise ValueError("Only the current draft of this week can be added to the schedule.")

    others = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_profile_id == profile.id,
            TrainingPlan.week_start == record.week_start,
            TrainingPlan.id != record.id,
            TrainingPlan.published_at.is_not(None),
        )
        .all()
    )
    for other in others:
        other.published_at = None

    record.published_at = datetime.utcnow()
    db.commit()

    payload = get_active_plan(db, profile.id, record.week_start) or {}
    payload["disclaimer"] = None
    return payload


def persist_week_from_chat(
    db: Session,
    profile: AthleteProfile,
    *,
    plan_data: dict,
    clock: dict,
    safety: dict,
    hits: list[dict] | None,
    provider: str,
    model: str,
) -> dict:
    """Save a chat-revised week as the active draft, replacing the previous draft."""
    start = clock["week_start"]
    plan_data = dict(plan_data)
    plan_data["week_start"] = start.isoformat()
    validation = validate_plan(plan_data, safety)
    plan_data = enrich_plan(validation["plan"], safety)
    issues = validation["issues"]
    citations = citation_slugs(hits or []) if provider != "rules" else []
    plan_id = _persist_plan(
        db,
        profile,
        plan_data,
        start,
        provider,
        model,
        issues,
        citations,
        safety=safety,
    )
    _copy_completions_from_superseded(db, profile.id, start, plan_id)
    payload = get_active_plan(db, profile.id, start) or {}
    payload["disclaimer"] = safety.get("disclaimer")
    payload["generation_notes"] = payload.get("generation_notes") or []
    payload["safety_issues"] = issues
    return payload


def _workout_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _row_as_workout(row: PlannedWorkout) -> dict:
    try:
        structure = json.loads(row.structure_json) if row.structure_json else []
    except json.JSONDecodeError:
        structure = []
    return {
        "date": row.workout_date.isoformat(),
        "sport": row.sport,
        "title": row.title,
        "session_type": row.session_type,
        "duration_min": row.duration_min,
        "distance_m": row.distance_m,
        "intensity": row.intensity,
        "description": row.description,
        "structure": structure,
        "completed_activity_id": row.completed_activity_id,
    }


def persist_today_adjustment(
    db: Session,
    profile: AthleteProfile,
    *,
    today: date,
    week_start: date,
    plan_data: dict | None,
    safety: dict,
    hits: list[dict] | None,
    provider: str,
    model: str,
) -> dict:
    """Rewrite only today's PlannedWorkout rows. Other days stay put."""
    proposed = []
    for workout in (plan_data or {}).get("workouts") or []:
        if _workout_date(workout.get("date")) == today:
            proposed.append(dict(workout))

    record = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_profile_id == profile.id,
            TrainingPlan.week_start == week_start,
            TrainingPlan.status == "active",
        )
        .order_by(TrainingPlan.id.desc())
        .first()
    )
    if record is None:
        seed = proposed or [
            downgrade_today_workout(
                {
                    "date": today.isoformat(),
                    "sport": "Mobility",
                    "title": "Restore / mobility",
                    "session_type": "mobility",
                    "duration_min": 30,
                    "intensity": "Recovery",
                    "description": None,
                    "structure": [],
                },
                safety,
            )
        ]
        draft = {
            "title": f"Week of {week_start.isoformat()}",
            "summary": "Today's session adjusted for readiness. Other days were not rewritten.",
            "focus": "Today only",
            "week_start": week_start.isoformat(),
            "workouts": [enrich_workout(item, safety) for item in seed],
        }
        validation = validate_plan(draft, safety)
        plan_id = _persist_plan(
            db,
            profile,
            enrich_plan(validation["plan"], safety),
            week_start,
            provider,
            model,
            validation["issues"],
            citation_slugs(hits or []) if provider != "rules" else [],
            safety=safety,
        )
        payload = get_active_plan(db, profile.id, week_start) or {}
        payload["disclaimer"] = safety.get("disclaimer")
        payload["safety_issues"] = validation["issues"]
        payload["generation_notes"] = ["Adjusted today only — no full-week rewrite."]
        payload["plan_id"] = plan_id
        return payload

    existing = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.training_plan_id == record.id,
            PlannedWorkout.workout_date == today,
        )
        .order_by(PlannedWorkout.id.asc())
        .all()
    )
    keep_completed = [row for row in existing if row.completed_activity_id]
    open_rows = [row for row in existing if not row.completed_activity_id]
    if keep_completed and not open_rows:
        payload = get_active_plan(db, profile.id, week_start) or {}
        payload["disclaimer"] = safety.get("disclaimer")
        payload["generation_notes"] = [
            "Today's planned session is already completed — no further change."
        ]
        return payload
    if not proposed:
        proposed = [downgrade_today_workout(_row_as_workout(row), safety) for row in open_rows]
        if not proposed:
            proposed = [
                downgrade_today_workout(
                    {
                        "date": today.isoformat(),
                        "sport": "Mobility",
                        "title": "Restore / mobility",
                        "session_type": "mobility",
                        "duration_min": 30,
                        "intensity": "Recovery",
                        "structure": [],
                    },
                    safety,
                )
            ]
    else:
        proposed = [downgrade_today_workout(item, safety) for item in proposed]

    for row in open_rows:
        db.delete(row)
    db.flush()
    for workout in proposed:
        filled = enrich_workout(workout, safety)
        db.add(
            PlannedWorkout(
                training_plan_id=record.id,
                athlete_profile_id=profile.id,
                workout_date=today,
                sport=filled.get("sport"),
                title=filled.get("title"),
                session_type=filled.get("session_type"),
                duration_min=filled.get("duration_min"),
                distance_m=filled.get("distance_m"),
                intensity=filled.get("intensity"),
                description=filled.get("description"),
                structure_json=json.dumps(filled.get("structure") or []),
            )
        )
    notes = [
        {
            "level": "info",
            "code": "today_only_adjustment",
            "message": "Only today's session was changed for readiness. The rest of the week was left as planned.",
        }
    ]
    record.safety_notes = json.dumps(notes)
    db.commit()
    payload = get_active_plan(db, profile.id, week_start) or {}
    payload["disclaimer"] = safety.get("disclaimer")
    payload["safety_issues"] = notes
    payload["generation_notes"] = ["Adjusted today only — other days were left as planned."]
    return payload


def extract_week_plan_from_chat(
    *,
    raw: dict | None,
    reply_text: str,
    week_start: date,
) -> dict | None:
    coerced = coerce_week_plan((raw or {}).get("week_plan"), week_start=week_start)
    if coerced and coerced.get("workouts"):
        return coerced
    return parse_week_plan_from_text(reply_text, week_start=week_start)


def apply_week_from_chat(
    db: Session,
    profile: AthleteProfile,
    *,
    message_id: int | None = None,
    markdown: str | None = None,
    publish: bool = True,
    timezone_name: str | None = None,
) -> dict:
    """Turn a chat week table into the active plan and optionally put it on Schedule."""
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
    safety = context["safety"]
    stored_plan_id = None
    text = (markdown or "").strip()
    if message_id:
        row = (
            db.query(CoachMessage)
            .filter(
                CoachMessage.id == message_id,
                CoachMessage.athlete_profile_id == profile.id,
            )
            .first()
        )
        if row is None:
            raise LookupError("message_not_found")
        meta = _decode_message_meta(row.citations)
        stored_plan_id = meta.get("plan_id")
        if not text:
            text = row.content or ""

    if stored_plan_id:
        record = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.id == stored_plan_id,
                TrainingPlan.athlete_profile_id == profile.id,
            )
            .first()
        )
        if record is not None:
            if record.status != "active":
                record.status = "active"
                others = (
                    db.query(TrainingPlan)
                    .filter(
                        TrainingPlan.athlete_profile_id == profile.id,
                        TrainingPlan.week_start == record.week_start,
                        TrainingPlan.id != record.id,
                        TrainingPlan.status == "active",
                    )
                    .all()
                )
                for other in others:
                    other.status = "superseded"
                db.commit()
            if publish:
                return publish_plan_to_schedule(db, profile, record.id)
            payload = get_active_plan(db, profile.id, record.week_start) or {}
            payload["disclaimer"] = safety.get("disclaimer")
            return payload

    plan_data = parse_week_plan_from_text(text, week_start=clock["week_start"])
    if not plan_data or not plan_data.get("workouts"):
        raise ValueError("No week table found in that coach reply.")
    payload = persist_week_from_chat(
        db,
        profile,
        plan_data=plan_data,
        clock=clock,
        safety=safety,
        hits=[],
        provider="chat",
        model="week-from-chat",
    )
    if publish and payload.get("plan_id"):
        return publish_plan_to_schedule(db, profile, payload["plan_id"])
    return payload


def _copy_completions_from_superseded(
    db: Session, profile_id: int, week_start: date, new_plan_id: int
) -> None:
    old_rows = (
        db.query(PlannedWorkout)
        .join(TrainingPlan, PlannedWorkout.training_plan_id == TrainingPlan.id)
        .filter(
            PlannedWorkout.athlete_profile_id == profile_id,
            TrainingPlan.week_start == week_start,
            TrainingPlan.id != new_plan_id,
            PlannedWorkout.completed_activity_id.isnot(None),
        )
        .all()
    )
    by_date: dict[date, list[int]] = {}
    for row in old_rows:
        by_date.setdefault(row.workout_date, []).append(row.completed_activity_id)
    if not by_date:
        return
    used: set[int] = set()
    new_rows = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.training_plan_id == new_plan_id)
        .order_by(PlannedWorkout.workout_date.asc(), PlannedWorkout.id.asc())
        .all()
    )
    for row in new_rows:
        for activity_id in by_date.get(row.workout_date) or []:
            if activity_id in used:
                continue
            row.completed_activity_id = activity_id
            used.add(activity_id)
            break
    db.commit()


# ---------------------------------------------------------------- daily advice


def advice_input_fingerprint(context: dict, clock: dict) -> str:
    """Hash of the health / recovery / training signals that should rewrite Today."""
    coros = context.get("coros") or {}
    health = coros.get("latest_health") or {}
    fitness = coros.get("fitness") or {}
    load = coros.get("training_load") or {}
    safety = context.get("safety") or {}
    activities = context.get("recent_activities") or []
    latest = activities[0] if activities else {}
    local_date = str(clock.get("local_date") or "")[:10]
    today_count = 0
    for activity in activities:
        stamp = str(activity.get("date") or activity.get("activity_date") or "")[:10]
        if stamp == local_date:
            today_count += 1
    payload = {
        "date": local_date,
        "health": {
            "metric_date": health.get("metric_date"),
            "sleep_score": health.get("sleep_score"),
            "sleep_duration_min": health.get("sleep_duration_min"),
            "hrv": health.get("hrv"),
            "hrv_assessment": health.get("hrv_assessment"),
            "stress": health.get("stress"),
            "resting_heart_rate": health.get("resting_heart_rate"),
        },
        "recovery": {
            "recovery_pct": fitness.get("recovery_pct"),
            "recovery_level": fitness.get("recovery_level"),
            "vo2max": fitness.get("vo2max"),
            "recovery_full_at": fitness.get("recovery_full_at"),
        },
        "load": {
            "short_load": load.get("short_load"),
            "long_load": load.get("long_load"),
            "load_ratio": load.get("load_ratio"),
        },
        "training": {
            "latest_id": latest.get("id"),
            "latest_date": str(latest.get("date") or latest.get("activity_date") or "")[:19],
            "latest_name": latest.get("name"),
            "today_count": today_count,
        },
        "readiness": (safety.get("readiness") or {}).get("action"),
        "flags": sorted(context.get("readiness_flags") or []),
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def generate_daily_advice(
    db: Session,
    profile: AthleteProfile,
    timezone_name: str | None = None,
    *,
    force: bool = False,
) -> dict:
    """Return today's brief. Rewrite only on Refresh or when signals changed."""
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
    fingerprint = advice_input_fingerprint(context, clock)
    try:
        advice_date = date.fromisoformat(str(clock["local_date"])[:10])
    except ValueError:
        advice_date = clock["today"]

    existing = (
        db.query(DailyAdviceSnapshot)
        .filter(
            DailyAdviceSnapshot.athlete_profile_id == profile.id,
            DailyAdviceSnapshot.advice_date == advice_date,
        )
        .first()
    )
    if existing and not force and existing.fingerprint == fingerprint:
        payload = json.loads(existing.payload_json)
        payload["cached"] = True
        payload["generated_at"] = existing.updated_at or existing.created_at
        return payload

    payload = _compose_daily_advice(db, profile, context, clock)
    payload["cached"] = False
    now = datetime.now(dt_timezone.utc).replace(tzinfo=None)
    payload["generated_at"] = now
    _upsert_advice_snapshot(
        db,
        profile_id=profile.id,
        advice_date=advice_date,
        fingerprint=fingerprint,
        payload=payload,
        existing=existing,
        generated_at=now,
    )
    return payload


def _upsert_advice_snapshot(
    db: Session,
    *,
    profile_id: int,
    advice_date: date,
    fingerprint: str,
    payload: dict,
    existing: DailyAdviceSnapshot | None,
    generated_at: datetime,
) -> DailyAdviceSnapshot:
    stored = dict(payload)
    stored.pop("cached", None)
    body = json.dumps(stored, default=str)
    if existing is None:
        existing = DailyAdviceSnapshot(
            athlete_profile_id=profile_id,
            advice_date=advice_date,
            fingerprint=fingerprint,
            payload_json=body,
            provider=payload.get("provider"),
            model=payload.get("model"),
            created_at=generated_at,
            updated_at=generated_at,
        )
        db.add(existing)
    else:
        existing.fingerprint = fingerprint
        existing.payload_json = body
        existing.provider = payload.get("provider")
        existing.model = payload.get("model")
        existing.updated_at = generated_at
    db.commit()
    db.refresh(existing)
    return existing


def _compose_daily_advice(
    db: Session, profile: AthleteProfile, context: dict, clock: dict
) -> dict:
    safety = context["safety"]
    readiness = safety["readiness"]

    query = f"readiness recovery adjustment {' '.join(context['readiness_flags'])}".strip()
    hits = _retrieve(db, query or "readiness adjustment", profile, k=4)
    current_plan = get_active_plan(db, profile.id, clock["week_start"])

    user_prompt = f"""{format_clock_block(clock)}

ATHLETE CONTEXT
{_context_digest(context, clock)}

CURRENT WEEK PLAN
{_plan_digest(current_plan, clock)}

SAFETY RULES (hard limits)
{safety_prompt_rules(safety, weekday_index=clock["weekday_index"])}

DETERMINISTIC READINESS VERDICT (you must not contradict this)
action={readiness['action']} · {readiness['reason']}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

TASK
Give today's guidance for {clock['weekday']} {clock['local_date']}. If they already trained today,
acknowledge the actual session (use power, %FTP, max HR, and key-session laps — not duration vs
the typical 60-minute weekday length). Do not talk as if the week is starting unless it is Monday
or Tuesday. Reference the athlete's own numbers (sleep, HRV, resting HR, recent load, FTP) in
the rationale. Never more than two consecutive sentences per block.
recommendation MUST contain newline characters. Example shape:
Today: two easy sessions only — no quality work.
1. Easy strength — 40 min
- Focus: anti-extension core only
- Avoid: back squat, deadlift, crunch
2. Z2 indoor spin — 45 min
- Power: 130-174 W
Do not pack sessions into one paragraph. Do not write a wall of **bold**.

Respond with JSON matching exactly this shape:
{ADVICE_SCHEMA}"""

    result = _call_provider(SYSTEM_PROMPT, user_prompt)
    provider_name, model_name = "rules", "deterministic-template"
    advice: dict | None = None

    if result is not None:
        raw, provider_name, model_name = result
        try:
            advice = DailyAdviceJSON.model_validate(raw).model_dump(mode="json")
        except ValidationError as exc:
            logger.warning("Advice schema validation failed for %s: %s", provider_name, exc)
            advice = None
            provider_name, model_name = "rules", "deterministic-template"

    if advice is None:
        advice = build_template_advice(context, safety)

    # The deterministic verdict always wins over the model's framing.
    if readiness["action"] == "rest_or_mobility":
        advice["session_adjustment"] = (
            advice.get("session_adjustment") or "Replace today's session with rest or mobility."
        )

    return {
        "provider": provider_name,
        "model": model_name,
        "date": clock["local_date"],
        "readiness": readiness,
        "advice": advice,
        "citations": [hit["citation"] for hit in hits] if provider_name != "rules" else [],
        "disclaimer": safety["disclaimer"],
    }


def _distance_load_dict(db: Session, profile_id: int) -> dict:
    from app.services.training_load import compute_athlete_stats

    stats = compute_athlete_stats(db, profile_id)
    return {
        "acute_load_km": stats.acute_load_km,
        "chronic_load_km": stats.chronic_load_km,
        "acwr": stats.acwr,
        "weekly_volume_km": [bucket.total_distance_km for bucket in stats.weekly_volume_history],
    }


def _effort_load_dict(context: dict) -> dict:
    load = (context.get("coros") or {}).get("training_load") or {}
    comments = []
    for entry in (load.get("daily_comments") or [])[:8]:
        if isinstance(entry, str) and entry.strip():
            comments.append(entry.strip())
        elif isinstance(entry, dict):
            text = entry.get("comment") or entry.get("text") or ""
            comments.append(
                {
                    "date": entry.get("date"),
                    "comment": text,
                    "load_ratio": entry.get("load_ratio"),
                }
            )
    return {
        "short_load": load.get("short_load"),
        "long_load": load.get("long_load"),
        "load_ratio": load.get("load_ratio"),
        "daily_comments": comments,
    }


WEEK_BRIEF_TOPICS = frozenset(
    {"volume", "load", "hrv", "stress", "rhr", "daily", "sleep", "season"}
)
HEALTH_WEEK_TOPICS = frozenset({"hrv", "stress", "rhr", "daily", "sleep"})


def normalize_week_topic(topic: str | None) -> str:
    value = (topic or "volume").strip().lower()
    return value if value in WEEK_BRIEF_TOPICS else "volume"


def _hrv_status_dict(context: dict) -> dict:
    coros = context.get("coros") or {}
    latest = coros.get("latest_health") or {}
    trend = coros.get("health_trend") or []
    nights = [row.get("hrv") for row in trend if row.get("hrv") is not None]
    last7 = nights[:7]
    avg7 = sum(last7) / len(last7) if last7 else None
    last = latest.get("hrv")
    ratio = (float(last) / float(avg7)) if last is not None and avg7 else None
    return {
        "hrv": last,
        "hrv_assessment": latest.get("hrv_assessment"),
        "avg_7d": round(avg7, 1) if avg7 is not None else None,
        "nights_7d": len(last7),
        "ratio_vs_usual": round(ratio, 2) if ratio is not None else None,
        "recent_hrv": nights[:14],
    }


def _stress_status_dict(context: dict) -> dict:
    coros = context.get("coros") or {}
    latest = coros.get("latest_health") or {}
    trend = coros.get("health_trend") or []
    days = [row.get("stress") for row in trend if row.get("stress") is not None]
    last7 = days[:7]
    avg7 = sum(last7) / len(last7) if last7 else None
    last = latest.get("stress")
    ratio = (float(last) / float(avg7)) if last is not None and avg7 else None
    return {
        "stress": last,
        "avg_7d": round(avg7, 1) if avg7 is not None else None,
        "days_7d": len(last7),
        "ratio_vs_usual": round(ratio, 2) if ratio is not None else None,
        "high_absolute": bool(last is not None and float(last) >= 70),
        "recent_stress": days[:14],
    }


def _rhr_status_dict(context: dict) -> dict:
    coros = context.get("coros") or {}
    latest = coros.get("latest_health") or {}
    trend = coros.get("health_trend") or []
    nights = [row.get("resting_heart_rate") for row in trend if row.get("resting_heart_rate") is not None]
    last7 = nights[:7]
    avg7 = sum(last7) / len(last7) if last7 else None
    last = latest.get("resting_heart_rate")
    ratio = (float(last) / float(avg7)) if last is not None and avg7 else None
    delta = (float(last) - float(avg7)) if last is not None and avg7 is not None else None
    return {
        "resting_heart_rate": last,
        "avg_7d": round(avg7, 1) if avg7 is not None else None,
        "nights_7d": len(last7),
        "ratio_vs_usual": round(ratio, 2) if ratio is not None else None,
        "delta_bpm": round(delta, 1) if delta is not None else None,
        "rise_soft": bool(delta is not None and delta >= 5),
        "elevated_rise": bool(delta is not None and delta >= 7),
        "recent_rhr": nights[:14],
    }


def _daily_status_dict(context: dict) -> dict:
    coros = context.get("coros") or {}
    latest = coros.get("latest_health") or {}
    trend = coros.get("health_trend") or []
    days = [row.get("steps") for row in trend if row.get("steps") is not None]
    last7 = days[:7]
    avg7 = sum(last7) / len(last7) if last7 else None
    last = latest.get("steps")
    ratio = (float(last) / float(avg7)) if last is not None and avg7 else None
    cals = [row.get("calories") for row in trend if row.get("calories") is not None]
    cal7 = cals[:7]
    avg_cal = sum(cal7) / len(cal7) if cal7 else None
    hrs = [row.get("avg_heart_rate") for row in trend if row.get("avg_heart_rate") is not None]
    hr7 = hrs[:7]
    avg_hr7 = sum(hr7) / len(hr7) if hr7 else None
    return {
        "steps": last,
        "calories": latest.get("calories"),
        "avg_heart_rate": latest.get("avg_heart_rate"),
        "avg_7d_steps": round(avg7, 0) if avg7 is not None else None,
        "avg_7d_calories": round(avg_cal, 0) if avg_cal is not None else None,
        "avg_7d_hr": round(avg_hr7, 1) if avg_hr7 is not None else None,
        "days_7d": len(last7),
        "ratio_vs_usual": round(ratio, 2) if ratio is not None else None,
        "sedentary": bool(last is not None and float(last) < 5000),
        "recent_steps": days[:14],
    }


def _sleep_status_dict(context: dict) -> dict:
    coros = context.get("coros") or {}
    latest = coros.get("latest_health") or {}
    trend = coros.get("health_trend") or []
    durations = [row.get("sleep_duration_min") for row in trend if row.get("sleep_duration_min") is not None]
    last7 = durations[:7]
    avg7 = sum(last7) / len(last7) if last7 else None
    last = latest.get("sleep_duration_min")
    ratio = (float(last) / float(avg7)) if last is not None and avg7 else None
    scores = [row.get("sleep_score") for row in trend if row.get("sleep_score") is not None]
    score7 = scores[:7]
    avg_score = sum(score7) / len(score7) if score7 else None
    return {
        "sleep_duration_min": last,
        "sleep_score": latest.get("sleep_score"),
        "deep_sleep_pct": latest.get("deep_sleep_pct"),
        "rem_sleep_pct": latest.get("rem_sleep_pct"),
        "light_sleep_pct": latest.get("light_sleep_pct"),
        "nap_duration_min": latest.get("nap_duration_min"),
        "bedtime": latest.get("bedtime"),
        "wake_time": latest.get("wake_time"),
        "avg_7d_min": round(avg7, 0) if avg7 is not None else None,
        "avg_7d_score": round(avg_score, 1) if avg_score is not None else None,
        "nights_7d": len(last7),
        "ratio_vs_usual": round(ratio, 2) if ratio is not None else None,
        "recent_duration_min": durations[:14],
    }


def _attach_replan_triggers(db: Session, profile: AthleteProfile, context: dict) -> None:
    """Put current replan triggers on the season context so the brief can cite them.

    Only the Season brief needs these, and detection costs several queries, so we
    do not pay for them on every coach context build.
    """
    season = context.get("season")
    if not isinstance(season, dict):
        return
    # Lazy import: periodization/season_replan already import from this module's peers.
    from app.services.periodization import get_active_season_plan
    from app.services.season_replan import detect_replan_triggers

    try:
        plan = get_active_season_plan(db, profile.id)
        season["replan_triggers"] = detect_replan_triggers(db, profile, plan=plan)
    except Exception:  # noqa: BLE001 - a brief must never fail on trigger detection
        logger.warning("Replan trigger detection failed for season brief", exc_info=True)
        season["replan_triggers"] = []


def _season_status_dict(context: dict) -> dict:
    """Season packet for the Season page brief — phases plus planner triggers."""
    season = context.get("season") or {}
    a_race = season.get("a_race") or {}
    triggers = season.get("replan_triggers") or []
    trigger_codes = sorted({str(item.get("code")) for item in triggers if item.get("code")})

    if not season.get("has_plan"):
        return {
            "has_plan": False,
            "a_race": {"name": a_race.get("name"), "date": a_race.get("date")} if a_race else None,
            "replan_trigger_codes": trigger_codes,
            "replan_trigger_messages": [str(item.get("message")) for item in triggers],
        }

    phase = season.get("current_phase") or {}
    intent = season.get("week_intent") or {}
    baseline = season.get("baseline") or {}
    feasibility = season.get("a_race_feasibility") or {}
    return {
        "has_plan": True,
        "a_race": {
            "name": a_race.get("name"),
            "date": a_race.get("date"),
            "target_metric": a_race.get("target_metric"),
        },
        "season_start": season.get("start_date"),
        "season_end": season.get("end_date"),
        "current_phase": phase.get("phase_type"),
        "phase_intent": phase.get("intent"),
        "week_in_phase": season.get("week_in_phase"),
        "phase_week_count": phase.get("week_count"),
        "volume_bias": intent.get("volume_bias"),
        "intensity_bias": intent.get("intensity_bias"),
        "long_session_allowed_min": intent.get("long_session_allowed_min"),
        # The reasons the limits are what they are. Fingerprinted so the brief
        # refreshes when the explanation changes, not only when a number does.
        "baseline": {
            "long_session_ceiling_min": baseline.get("long_session_ceiling_min"),
            "recovery_cycle_weeks": baseline.get("recovery_cycle_weeks"),
            "volume_damp": baseline.get("volume_damp"),
            "confidence": baseline.get("confidence"),
            "notes": list(baseline.get("notes") or []),
        },
        "a_race_feasibility": {
            "feasibility": feasibility.get("feasibility"),
            "predicted_a_time": feasibility.get("predicted_a_time"),
        },
        "week_notes": list(intent.get("notes") or []),
        "week_events": list(intent.get("events") or []),
        "phase_outline": [
            {
                "phase_type": row.get("phase_type"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "week_count": row.get("week_count"),
            }
            for row in season.get("phases") or []
        ],
        "upcoming_events": [
            {
                "name": row.get("name"),
                "date": row.get("date"),
                "priority": row.get("priority"),
            }
            for row in season.get("upcoming_events") or []
        ],
        "replan_trigger_codes": trigger_codes,
        "replan_trigger_messages": [str(item.get("message")) for item in triggers],
        "warnings": list(season.get("warnings") or []),
        "a_race_feasibility": season.get("a_race_feasibility"),
    }


def week_brief_input_fingerprint(
    context: dict, clock: dict, distance: dict, topic: str = "volume"
) -> str:
    """Hash of the signals that should rewrite that page's Week brief."""
    topic = normalize_week_topic(topic)
    coros = context.get("coros") or {}
    health = coros.get("latest_health") or {}
    fitness = coros.get("fitness") or {}
    safety = context.get("safety") or {}
    plan = context.get("current_plan") or {}
    shared = {
        "topic": topic,
        "week_start": str(clock.get("week_start_iso") or clock.get("week_start") or "")[:10],
        "readiness": (safety.get("readiness") or {}).get("action"),
        "flags": sorted(context.get("readiness_flags") or []),
        "health": {
            "sleep_score": health.get("sleep_score"),
            "hrv": health.get("hrv"),
            "hrv_assessment": health.get("hrv_assessment"),
            "stress": health.get("stress"),
        },
        "recovery_pct": fitness.get("recovery_pct"),
        "plan_id": plan.get("plan_id") or (plan.get("plan") or {}).get("id"),
    }
    if topic == "load":
        effort = (coros.get("training_load") or {})
        payload = {
            **shared,
            "effort": {
                "short_load": effort.get("short_load"),
                "long_load": effort.get("long_load"),
                "load_ratio": effort.get("load_ratio"),
                "comments": effort.get("daily_comments") or [],
            },
        }
    elif topic == "hrv":
        payload = {"topic": topic, "week_start": shared["week_start"], "hrv": _hrv_status_dict(context)}
    elif topic == "stress":
        payload = {"topic": topic, "week_start": shared["week_start"], "stress": _stress_status_dict(context)}
    elif topic == "rhr":
        payload = {"topic": topic, "week_start": shared["week_start"], "rhr": _rhr_status_dict(context)}
    elif topic == "daily":
        payload = {"topic": topic, "week_start": shared["week_start"], "daily": _daily_status_dict(context)}
    elif topic == "sleep":
        payload = {"topic": topic, "week_start": shared["week_start"], "sleep": _sleep_status_dict(context)}
    elif topic == "season":
        payload = {
            "topic": topic,
            "week_start": shared["week_start"],
            "season": _season_status_dict(context),
        }
    else:
        load = safety.get("load") or {}
        payload = {
            **shared,
            "distance": {
                "acwr": distance.get("acwr"),
                "acute_load_km": distance.get("acute_load_km"),
                "chronic_load_km": distance.get("chronic_load_km"),
                "weekly_volume_km": distance.get("weekly_volume_km") or [],
            },
            "minutes_acwr": load.get("minutes_acwr"),
        }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def generate_week_brief(
    db: Session,
    profile: AthleteProfile,
    timezone_name: str | None = None,
    *,
    force: bool = False,
    topic: str = "volume",
) -> dict:
    """Return this week's page brief. Rewrite on Refresh or when that topic's signals change."""
    topic = normalize_week_topic(topic)
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
    current_plan = get_active_plan(db, profile.id, clock["week_start"])
    context["current_plan"] = current_plan or {}
    distance = _distance_load_dict(db, profile.id) if topic == "volume" else {}
    if topic == "season":
        _attach_replan_triggers(db, profile, context)
    fingerprint = week_brief_input_fingerprint(context, clock, distance, topic)
    week_start = clock["week_start"]

    existing = (
        db.query(WeeklyAdviceSnapshot)
        .filter(
            WeeklyAdviceSnapshot.athlete_profile_id == profile.id,
            WeeklyAdviceSnapshot.week_start == week_start,
            WeeklyAdviceSnapshot.topic == topic,
        )
        .first()
    )
    if existing and not force and existing.fingerprint == fingerprint:
        payload = json.loads(existing.payload_json)
        payload["cached"] = True
        payload["generated_at"] = existing.updated_at or existing.created_at
        return payload

    payload = _compose_week_brief(
        db, profile, context, clock, distance, current_plan, topic=topic
    )
    payload["cached"] = False
    now = datetime.now(dt_timezone.utc).replace(tzinfo=None)
    payload["generated_at"] = now
    _upsert_week_brief_snapshot(
        db,
        profile_id=profile.id,
        week_start=week_start,
        topic=topic,
        fingerprint=fingerprint,
        payload=payload,
        existing=existing,
        generated_at=now,
    )
    return payload


def _upsert_week_brief_snapshot(
    db: Session,
    *,
    profile_id: int,
    week_start: date,
    topic: str,
    fingerprint: str,
    payload: dict,
    existing: WeeklyAdviceSnapshot | None,
    generated_at: datetime,
) -> WeeklyAdviceSnapshot:
    stored = dict(payload)
    stored.pop("cached", None)
    body = json.dumps(stored, default=str)
    if existing is None:
        existing = WeeklyAdviceSnapshot(
            athlete_profile_id=profile_id,
            week_start=week_start,
            topic=topic,
            fingerprint=fingerprint,
            payload_json=body,
            provider=payload.get("provider"),
            model=payload.get("model"),
            created_at=generated_at,
            updated_at=generated_at,
        )
        db.add(existing)
    else:
        existing.topic = topic
        existing.fingerprint = fingerprint
        existing.payload_json = body
        existing.provider = payload.get("provider")
        existing.model = payload.get("model")
        existing.updated_at = generated_at
    db.commit()
    db.refresh(existing)
    return existing


def _compose_week_brief(
    db: Session,
    profile: AthleteProfile,
    context: dict,
    clock: dict,
    distance: dict,
    current_plan: dict | None,
    topic: str = "volume",
) -> dict:
    topic = normalize_week_topic(topic)
    safety = context["safety"]
    readiness = safety["readiness"]
    effort = _effort_load_dict(context) if topic == "load" else {}
    hrv = _hrv_status_dict(context) if topic == "hrv" else {}
    stress = _stress_status_dict(context) if topic == "stress" else {}
    rhr = _rhr_status_dict(context) if topic == "rhr" else {}
    daily = _daily_status_dict(context) if topic == "daily" else {}
    sleep = _sleep_status_dict(context) if topic == "sleep" else {}
    season = _season_status_dict(context) if topic == "season" else {}

    if topic == "hrv":
        query = "HRV heart-rate variability overnight milliseconds rMSSD"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""OVERNIGHT HRV ONLY (milliseconds vs the athlete's 7-day usual)
{json.dumps(hrv, indent=2, default=str)}

TASK
Write THIS WEEK's HRV brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with last night vs 7-day usual (ratio_vs_usual). Below ~0.90 is suppressed, ~0.95-1.08 typical,
above that a high night. Use hrv ms, avg_7d, and hrv_assessment (balanced/unbalanced).
If hrv is missing, say they need an overnight HRV recording — do not invent milliseconds.
{HEALTH_METRIC_BAN}"""
    elif topic == "stress":
        query = "daily stress allostatic load wearable stress score"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""DAILY STRESS ONLY (all-day average vs the athlete's 7-day usual)
{json.dumps(stress, indent=2, default=str)}

TASK
Write THIS WEEK's Stress brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with today vs 7-day usual. Below ~0.90 is quiet, ~0.90-1.10 typical, 1.10-1.25 elevated,
above that high. A raw score of 70+ (high_absolute) is high even if the ratio looks modest.
If stress is missing, say they need a daily-stress recording — do not invent scores.
{HEALTH_METRIC_BAN}"""
    elif topic == "rhr":
        query = "resting heart rate overnight bpm baseline"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""RESTING HEART RATE ONLY (overnight bpm vs the athlete's 7-day usual)
{json.dumps(rhr, indent=2, default=str)}

TASK
Write THIS WEEK's Resting HR brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with last night vs 7-day usual and delta_bpm. Below ~0.97 is quieter than usual,
~0.97-1.05 typical, 1.05-1.08 a little high, above that elevated. About +5 bpm is a little high;
about +7 bpm is elevated even if the ratio looks modest.
If resting_heart_rate is missing, say they need an overnight recording — do not invent bpm.
{HEALTH_METRIC_BAN}"""
    elif topic == "daily":
        query = "daily steps incidental movement calories day average heart rate"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""DAILY HEALTH ONLY (steps vs 7-day usual; calories and day-average HR are companions on this page)
{json.dumps(daily, indent=2, default=str)}

TASK
Write THIS WEEK's Daily Health brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with today vs 7-day usual steps. Below ~0.75 is quiet, ~0.75-1.20 typical, 1.20-1.50 busy,
above that very high. Under 5,000 steps (sedentary=true) is quiet even if the ratio looks modest.
You may mention calories and day-average HR because they belong to this page. Nothing else.
If steps are missing, say they need a daily-health recording — do not invent step counts.
{HEALTH_METRIC_BAN}"""
    elif topic == "sleep":
        query = "sleep duration stages bedtime sleep score naps overnight"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""SLEEP ONLY (overnight duration, stages, naps, bedtime vs the athlete's 7-day usual)
{json.dumps(sleep, indent=2, default=str)}

TASK
Write THIS WEEK's Sleep brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with last night's sleep_duration_min vs avg_7d_min (ratio_vs_usual). You may use sleep_score,
deep/rem/light percentages, nap_duration_min, bedtime, and wake_time. Nothing else.
If sleep_duration_min is missing, say they need an overnight sleep recording — do not invent minutes.
{HEALTH_METRIC_BAN}"""
    elif topic == "season":
        query = "periodization macro base build peak taper season plan"
        hits = _retrieve(db, query, profile, k=4)
        focus_block = f"""SEASON PLAN ONLY (macro phases drawn backward from the A-race)
{json.dumps(season, indent=2, default=str)}

TASK
Write THIS WEEK's Season brief. Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
If has_plan is false, tell them to generate the season from their A-race — nothing else.
Otherwise lead with the current phase and week_in_phase of phase_week_count, plus how far the A-race is.
Explain what this phase is for using phase_intent, volume_bias, and intensity_bias.
Then numbered points in this shape:
Lead sentence.
1. Point — short constraint
- Label: value
If replan_trigger_codes is non-empty, the session_adjustment must recommend Replan and name the reason.
If it is empty, the session_adjustment must say no plan change is needed this week.
Recommend Rebuild only when there is no plan or the A-race itself changed.
{SEASON_BAN}"""
    elif topic == "load":
        query = f"training load TRIMP short-term long-term effort {' '.join(context['readiness_flags'])}".strip()
        hits = _retrieve(db, query or "training-load management", profile, k=4)
        focus_block = f"""COROS EFFORT LOAD (this page — heart-rate TRIMP, not kilometres)
{json.dumps(effort, indent=2, default=str)}

TASK
Write THIS WEEK's Training Load brief (not today's single session, not the Volume/ACWR page).
Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with whether short-term vs long-term effort is underloaded (<0.8), in the sweet spot
(about 0.8-1.3), caution (1.3-1.5), or spiking (above 1.5). Use their short_load, long_load,
and load_ratio numbers. If daily_comments exist, weave one concrete COROS note in.
Then numbered remaining-week actions with newlines in the same shape as daily advice:
Lead sentence.
1. Action — duration or constraint
- Label: value
If recovery says rest, remaining days stay easy even if the ratio looks productive.
If short/long/ratio are missing, say they need a COROS sync — do not invent numbers.
Do not mention kilometres, GPS distance, or ACWR. This brief is effort only.
Never more than two consecutive sentences per block. Do not pack into one paragraph."""
    else:
        query = f"ACWR weekly volume load-management {' '.join(context['readiness_flags'])}".strip()
        hits = _retrieve(db, query or "ACWR load-management", profile, k=4)
        focus_block = f"""DISTANCE LOAD (this page's ACWR — kilometres, not COROS effort)
{json.dumps(distance, indent=2, default=str)}

TASK
Write THIS WEEK's Volume & ACWR brief (not today's single session, not the Training Load page).
Week of Monday {clock['week_start_iso']} through Sunday {clock['week_end_iso']}.
Today is {clock['weekday']} {clock['local_date']}.
Lead with whether they are underloaded, in the sweet spot (about 0.8-1.3 ACWR), caution (1.3-1.5),
or spiking (above 1.5). Use their own km numbers. Then numbered remaining-week actions with newlines
in the same shape as daily advice:
Lead sentence.
1. Action — duration or constraint
- Label: value
If recovery says rest, remaining days stay easy even if ACWR looks productive.
If the 28-day baseline is thin (many weekly_volume_km zeros), say the ratio is jumpy — not a verdict.
Do not discuss COROS short-term load, long-term load, or load ratio. This brief is kilometres only.
Never more than two consecutive sentences per block. Do not pack into one paragraph."""

    metric_only = topic in HEALTH_WEEK_TOPICS
    if metric_only:
        user_prompt = f"""{format_clock_block(clock)}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

{focus_block}

Respond with JSON matching exactly this shape:
{HEALTH_METRIC_ADVICE_SCHEMA}"""
        system_prompt = HEALTH_METRIC_SYSTEM_PROMPT
    elif topic == "season":
        user_prompt = f"""{format_clock_block(clock)}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

{focus_block}

Respond with JSON matching exactly this shape:
{SEASON_ADVICE_SCHEMA}"""
        system_prompt = SEASON_SYSTEM_PROMPT
    else:
        user_prompt = f"""{format_clock_block(clock)}

{format_data_sources_block(context)}

ATHLETE CONTEXT
{_context_digest(context, clock)}

CURRENT WEEK PLAN
{_plan_digest(current_plan, clock)}

SAFETY RULES (hard limits)
{safety_prompt_rules(safety, weekday_index=clock["weekday_index"])}

DETERMINISTIC READINESS VERDICT (you must not contradict this)
action={readiness['action']} · {readiness['reason']}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

{focus_block}

Respond with JSON matching exactly this shape:
{ADVICE_SCHEMA}"""
        system_prompt = SYSTEM_PROMPT

    result = _call_provider(system_prompt, user_prompt)
    provider_name, model_name = "rules", "deterministic-template"
    advice: dict | None = None

    if result is not None:
        raw, provider_name, model_name = result
        try:
            advice = DailyAdviceJSON.model_validate(raw).model_dump(mode="json")
            if metric_only and health_brief_off_topic(topic, advice):
                logger.warning("Health week brief for %s mentioned other topics; using template", topic)
                advice = None
                provider_name, model_name = "rules", "deterministic-template"
            elif topic == "season" and season_brief_off_topic(season, advice):
                logger.warning("Season brief drifted into sessions or a false replan; using template")
                advice = None
                provider_name, model_name = "rules", "deterministic-template"
        except ValidationError as exc:
            logger.warning("Week brief schema validation failed for %s: %s", provider_name, exc)
            advice = None
            provider_name, model_name = "rules", "deterministic-template"

    if advice is None:
        if topic == "load":
            advice = build_template_load_brief(context, safety, effort)
        elif topic == "hrv":
            advice = build_template_hrv_brief(context, safety, hrv)
        elif topic == "stress":
            advice = build_template_stress_brief(context, safety, stress)
        elif topic == "rhr":
            advice = build_template_rhr_brief(context, safety, rhr)
        elif topic == "daily":
            advice = build_template_daily_brief(context, safety, daily)
        elif topic == "sleep":
            advice = build_template_sleep_brief(context, safety, sleep)
        elif topic == "season":
            advice = build_template_season_brief(context, safety, season)
        else:
            advice = build_template_week_brief(context, safety, distance)

    if topic not in HEALTH_WEEK_TOPICS and topic != "season" and readiness["action"] == "rest_or_mobility":
        fallback = {
            "load": "Keep remaining days easy or rest — do not chase weekly load points.",
            "hrv": "Keep remaining days easy or rest — a recovered HRV number does not override rest.",
            "stress": "Keep remaining days easy or rest — a calmer stress score does not override rest.",
            "rhr": "Keep remaining days easy or rest — a quieter resting HR does not override rest.",
            "daily": "Keep remaining days easy or rest — extra walking does not override rest.",
            "volume": "Keep remaining days easy or rest — do not chase weekly kilometres.",
        }
        advice["session_adjustment"] = (
            advice.get("session_adjustment") or fallback.get(topic) or fallback["volume"]
        )

    return {
        "provider": provider_name,
        "model": model_name,
        "date": clock["local_date"],
        "week_start": clock["week_start"],
        "scope": "week",
        "topic": topic,
        "readiness": readiness,
        "advice": advice,
        "citations": [hit["citation"] for hit in hits] if provider_name != "rules" else [],
        "disclaimer": safety["disclaimer"],
    }


# ---------------------------------------------------------------- chat


def _load_session_telemetry(
    db: Session,
    profile: AthleteProfile,
    context: dict,
    message: str,
    clock: dict,
    activity_id: int | None = None,
) -> dict | None:
    matched = None
    if activity_id:
        matched = (
            db.query(Activity)
            .filter(
                Activity.id == activity_id,
                Activity.athlete_profile_id == profile.id,
            )
            .first()
        )
        if matched is not None and matched.canonical_activity_id:
            parent = (
                db.query(Activity)
                .filter(Activity.id == matched.canonical_activity_id)
                .first()
            )
            if parent is not None:
                matched = parent

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == profile.id,
            Activity.canonical_activity_id.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(40)
        .all()
    )
    if matched is None:
        if not activities:
            return None
        today_ids = set()
        for activity in activities:
            local = _parse_local_date(activity.activity_date, clock["tz"])
            if local == clock["today"]:
                today_ids.add(activity.id)
        matched = match_activity_for_message(
            message, activities, today_ids=today_ids, activity_id=activity_id
        )
    if matched is None:
        return None
    matched = _ensure_activity_laps(db, profile, matched)
    packet = analyze_activity(matched, context.get("physiology") or {})
    packet["modality"] = coach_modality(packet.get("sport"), packet.get("family"))
    local = _parse_local_date(matched.activity_date, clock["tz"])
    packet["when"] = _when_label(local, clock["today"]) if local else None
    packet["date"] = local.isoformat() if local else None
    notes = (
        db.query(ActivityNote)
        .filter(ActivityNote.activity_id == matched.id)
        .order_by(ActivityNote.created_at.desc())
        .all()
    )
    bodies = [row.body.strip() for row in notes if (row.body or "").strip()]
    if bodies:
        packet["athlete_notes"] = " | ".join(bodies)[:800]
    return packet


def _ensure_activity_laps(
    db: Session, profile: AthleteProfile, activity: Activity
) -> Activity:
    """Re-fetch provider laps when stored detail is a single session-length block."""
    from app.services.activity_detail import enrich_activity_detail, parse_activity_detail

    detail = parse_activity_detail(activity) or {}
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    if not laps_are_uninformative(laps, activity.moving_time_s or 0):
        return activity
    client = None
    try:
        from app.services.coros_sync import _client_for_connection, get_coros_connection

        connection = get_coros_connection(db, profile.id)
        if connection is not None:
            client = _client_for_connection(db, connection)
            client.initialize()
    except Exception:  # noqa: BLE001
        client = None
    try:
        enrich_activity_detail(db, activity, client=client, force=True)
        db.refresh(activity)
    except Exception:  # noqa: BLE001
        logger.warning("Could not refresh laps before autopsy for activity %s", activity.id)
    return activity


def chat_history(db: Session, profile_id: int, limit: int = 30) -> list[dict]:
    rows = (
        db.query(CoachMessage)
        .filter(CoachMessage.athlete_profile_id == profile_id)
        .order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            **_history_meta_fields(row.citations),
        }
        for row in rows
    ]


def _recent_transcript(history: list[dict], *, drop_assistant: bool) -> str:
    """Prior turns only. Drop stale autopsies so a correction cannot be copied."""
    prior = list(history[:-1][-8:] if history else [])
    if drop_assistant:
        prior = [entry for entry in prior if entry.get("role") != "assistant"]
    return "\n".join(
        f"{entry['role'].upper()}: {entry['content']}" for entry in prior
    )


def coach_chat(
    db: Session,
    profile: AthleteProfile,
    message: str,
    timezone_name: str | None = None,
    activity_id: int | None = None,
    intent: str | None = None,
    *,
    persist_plan: bool | None = None,
) -> dict:
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
    safety = context["safety"]
    red_flags = detect_red_flags(message)

    db.add(
        CoachMessage(athlete_profile_id=profile.id, role="user", content=message.strip())
    )
    db.commit()

    if red_flags:
        reply = {
            "reply": ESCALATION_REPLY,
            "citations": ["aal-safety-and-load"],
            "escalate": True,
            "escalation_reason": f"Red-flag symptom mentioned: {', '.join(red_flags)}.",
        }
        _store_assistant_message(db, profile.id, reply, "safety-gate")
        return {
            "provider": "safety-gate",
            "model": "deterministic-rules",
            "reply": reply,
            "citations": [],
            "history": chat_history(db, profile.id),
            "disclaimer": safety["disclaimer"],
        }

    if intent:
        resolved_intent = normalize_intent(intent)
        decision_source = "caller"
    else:
        decision = classify_chat_intent_detailed(message, activity_id=activity_id)
        resolved_intent = decision.intent
        decision_source = decision.source
        logger.info(
            "Coach intent=%s source=%s audit=%s schedule=%s review=%s",
            decision.intent,
            decision.source,
            decision.audit_score,
            decision.schedule_score,
            decision.review_score,
        )
    intent = resolved_intent
    if intent not in (
        WORKOUT_AUDIT,
        WEEK_REVIEW,
        WEEK_PLAN_REVIEW,
        SCHEDULE_UPDATE,
        DAY_ADJUST,
        SCIENCE_LOOKUP,
        CLINICAL_VETO,
        OFF_TOPIC,
        GENERAL_CHAT,
    ):
        intent = GENERAL_CHAT

    if persist_plan is None:
        persist_plan = intent in {SCHEDULE_UPDATE, DAY_ADJUST}

    clinical = detect_clinical_boundary(message)
    if clinical:
        intent = CLINICAL_VETO

    if intent == CLINICAL_VETO:
        clinical = clinical or {"kind": "tissue_pain", "region": None, "hits": []}
        flag_clinical_injury(
            db,
            profile.id,
            message,
            region=clinical.get("region"),
        )
        plan_changes = apply_joint_safe_recovery_mode(
            db,
            profile.id,
            today=clock["today"],
            week_start=clock["week_start"],
            region=clinical.get("region"),
        )
        db.commit()
        reply = template_clinical_veto(
            message,
            region=clinical.get("region"),
            kind=clinical.get("kind"),
            plan_changes=plan_changes,
        )
        _store_assistant_message(db, profile.id, reply, "clinical-veto")
        return {
            "provider": "clinical-veto",
            "model": "deterministic-rules",
            "reply": reply,
            "citations": ["aal-safety-and-load"],
            "history": chat_history(db, profile.id),
            "disclaimer": safety["disclaimer"],
        }

    if intent == OFF_TOPIC:
        reply = template_off_topic(message)
        _store_assistant_message(db, profile.id, reply, "domain-gate")
        return {
            "provider": "domain-gate",
            "model": "deterministic-rules",
            "reply": reply,
            "citations": [],
            "history": chat_history(db, profile.id),
            "disclaimer": safety["disclaimer"],
        }

    history = chat_history(db, profile.id, limit=12)
    current_plan = get_active_plan(db, profile.id, clock["week_start"])
    session_packet = None
    week_packet = None
    review_plan = current_plan
    modality = None
    science_grounded = False
    if intent == WORKOUT_AUDIT:
        session_packet = _load_session_telemetry(
            db, profile, context, message, clock, activity_id=activity_id
        )
        if session_packet is not None:
            overlay = build_session_plan_overlay(
                message=message,
                history=history,
                laps=session_packet.get("laps") or [],
                ftp=(session_packet.get("anchors_used") or {}).get("ftp_watts"),
                week_plan=current_plan,
                session_date=session_packet.get("date"),
                family=session_packet.get("family") or session_packet.get("modality"),
            )
            session_packet.update(overlay)
            if overlay.get("prescribed_vs_executed"):
                session_packet["work_laps"] = [
                    lap
                    for lap in (session_packet.get("laps") or [])
                    if lap.get("role") in {"over", "under", "work", "vo2_cap"}
                ]
                session_packet["work_lap_count"] = len(session_packet["work_laps"])
            if overlay.get("classification_note"):
                session_packet["classification"] = "over-under-vo2"
        modality = (session_packet or {}).get("modality") or coach_modality(
            (session_packet or {}).get("sport"),
            (session_packet or {}).get("family"),
        )
        query = retrieval_query_for_modality(
            modality,
            (session_packet or {}).get("classification") or "",
            message,
        )
        if session_packet and session_packet.get("prescription"):
            query += " planned versus executed VO2 cap over-under lactate clearance"
        hits = _retrieve(
            db,
            query,
            profile,
            k=6,
            extra_sports=science_sports_for_modality(modality, sports_for_retrieval(profile)),
        )
    elif intent == WEEK_REVIEW:
        window_start, _window_end, _label = review_week_window(clock, message)
        review_plan = get_active_plan(db, profile.id, window_start) or current_plan
        week_packet = build_week_review_packet(context, clock, review_plan, message)
        hits = _retrieve(
            db,
            "weekly training load ACWR adherence periodization recovery sleep HRV "
            + message[:180],
            profile,
            k=5,
        )
    elif intent in {SCHEDULE_UPDATE, WEEK_PLAN_REVIEW, DAY_ADJUST}:
        hits = _retrieve(
            db,
            "weekly training plan ACWR consecutive hard days spinal load recovery sleep HRV "
            + message[:180],
            profile,
            k=5,
        )
    elif intent == SCIENCE_LOOKUP:
        hits = _retrieve(db, _chat_retrieval_query(message), profile, k=6)
        strong = grounded_hits(hits)
        science_grounded = bool(strong)
        hits = strong if science_grounded else []
    else:
        hits = _retrieve(db, _chat_retrieval_query(message), profile, k=5)
        strong = grounded_hits(hits)
        if intent == GENERAL_CHAT:
            hits = strong if strong else hits[:1]

    has_prescription = bool(
        session_packet
        and (session_packet.get("prescription") or session_packet.get("prescribed_vs_executed"))
    )
    drop_assistant = has_prescription or intent != WORKOUT_AUDIT
    transcript = _recent_transcript(history, drop_assistant=drop_assistant)

    extra_block = ""
    if intent == WORKOUT_AUDIT and session_packet:
        extra_block = f"""
COMPUTED SESSION TELEMETRY (ground truth — do not invent or change these numbers)
{json.dumps(session_packet, indent=2, default=str)}

{athlete_state_block(context, safety)}
"""
        if has_prescription:
            extra_block += """
CORRECTION / PRESCRIPTION RULES (hard)
- prescribed_vs_executed lap roles override %FTP labels.
- vo2_cap laps are VO2 finishers, never generic overs. Lap 7 in this Colombia file is an over (260 W), not a VO2 cap.
- Score planned_w vs executed_w. Hit = within 8 W or 4%.
- Match week_plan_session to CURRENT WEEK PLAN for that date.
- Do NOT copy a previous assistant autopsy. Produce a new planned-vs-executed audit.
"""
    elif intent == WEEK_REVIEW:
        extra_block = f"""
WEEK REVIEW PACKET (ground truth for the recap window — do not invent sessions or swap in a ride outside this window)
{json.dumps(week_packet, indent=2, default=str)}

{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is WEEK_REVIEW. This is a week debrief, not a file autopsy.
Do not load or invent session telemetry. Completely skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
Do not quote NP, IF, TSS, laps, or a single ride's watts as if they were the whole week.
Sunday's long ride is one row in 📅 WHAT LANDED.
Use the packet window. If today is Monday and they said they finished the week, recap last Mon–Sun.
Never more than two consecutive sentences per block.
"""
    elif intent == WEEK_PLAN_REVIEW:
        extra_block = f"""
{today_call_prompt_block(context, safety)}

{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is WEEK_PLAN_REVIEW. Review only — do NOT build or save a week plan yet.
Do not autopsy a past ride. Skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
No NP / IF / TSS / laps. No 5-column week table. No week_plan JSON.
Use SEASON PLAN limits and the athlete's stated constraints. Copy TODAY'S CALL status exactly.
"""
    elif intent == SCHEDULE_UPDATE:
        extra_block = f"""
{today_call_prompt_block(context, safety)}

{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is SCHEDULE_UPDATE. Do not autopsy a past ride. Do not load or invent session telemetry.
Completely skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
Do not inject the last synced workout's laps, NP, IF, TSS, or autopsy metrics.
Do not write essays or paragraphs. Never more than two consecutive sentences per block.
Bullets, key-values, and the week table only.
Use CURRENT WEEK PLAN plus the athlete's proposed calendar.
Copy TODAY'S CALL status line exactly. Guard active back/spine limits with non-negotiable DO NOT lifts on strength days.
Every session needs Warm-up, a named Main set, and Cool-down (stretches / foam roll / mobility).
If the athlete's only reason is today's HRV, readiness, stress, or ACWR, do not rewrite other days — that is a today-only change.
"""
    elif intent == DAY_ADJUST:
        extra_block = f"""
{today_call_prompt_block(context, safety)}

{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is DAY_ADJUST. Change TODAY only. Do not rewrite the rest of the week.
Do not autopsy a past ride. Skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
Poor HRV, readiness, stress, or ACWR today: convert today's quality to easy (same duration) or mobility if REST.
Fill Warm-up, named Main set, Cool-down for today's session only.
week_plan.workouts must contain only today's date.
"""
    elif intent == SCIENCE_LOOKUP:
        extra_block = f"""
{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is SCIENCE_LOOKUP. Teach the concept. Do not autopsy a file.
Grounded retrieval: {"yes — cite only [S#]" if science_grounded else "NO — Evidence: Not in playbook. Do not invent a paper."}
Never more than two consecutive sentences per bullet.
"""
    else:
        extra_block = f"""
{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is GENERAL_CHAT. Completely skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
Do not load, invent, or quote the last synced workout's telemetry, laps, NP, IF, or TSS.
Focus 100% on the athlete's specific biological, schedule-adjacent, or emotional question.
Never more than two consecutive sentences per bullet.
If they feel they failed or cut a session short: 💬 REFRAME as spaced **bold** bullets.
"""

    if intent == WORKOUT_AUDIT:
        task = autopsy_task_for_packet(modality, session_packet)
        chat_schema = AUTOPSY_SCHEMA
        system_prompt = system_prompt_for_modality(modality)
    elif intent == WEEK_REVIEW:
        task = week_review_task()
        chat_schema = WEEK_REVIEW_SCHEMA
        system_prompt = week_review_system_prompt()
    elif intent == WEEK_PLAN_REVIEW:
        task = week_plan_review_task()
        chat_schema = WEEK_PLAN_REVIEW_SCHEMA
        system_prompt = schedule_system_prompt()
    elif intent == SCHEDULE_UPDATE:
        task = schedule_task()
        chat_schema = SCHEDULE_SCHEMA
        system_prompt = schedule_system_prompt()
    elif intent == DAY_ADJUST:
        task = day_adjust_task()
        chat_schema = DAY_ADJUST_SCHEMA
        system_prompt = schedule_system_prompt()
    elif intent == SCIENCE_LOOKUP:
        task = science_task(grounded=science_grounded)
        chat_schema = SCIENCE_SCHEMA
        system_prompt = science_system_prompt()
    else:
        task = chat_task()
        chat_schema = CHAT_SCHEMA
        system_prompt = chat_system_prompt()

    review_plan_block = ""
    if intent == WEEK_REVIEW and review_plan is not current_plan:
        review_plan_block = f"""
REVIEW WEEK PLAN (the recap window — not necessarily this Monday's plan)
{_plan_digest(review_plan, clock)}
"""

    user_prompt = f"""{format_clock_block(clock)}

{format_data_sources_block(context)}

ATHLETE CONTEXT
{_context_digest(context, clock, include_session_audit=(intent == WORKOUT_AUDIT))}

CURRENT WEEK PLAN
{_plan_digest(current_plan, clock)}
{review_plan_block}
SAFETY RULES (hard limits)
{safety_prompt_rules(safety, weekday_index=clock["weekday_index"])}

RECENT CONVERSATION
{transcript or '(none)'}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits, grounded=(science_grounded if intent == SCIENCE_LOOKUP else None))}
{extra_block}
ATHLETE MESSAGE
{message.strip()}

TASK
{task}

Respond with JSON matching exactly this shape:
{chat_schema}"""

    result = None
    if not (intent == SCIENCE_LOOKUP and not science_grounded):
        result = _call_provider(system_prompt, user_prompt)
    provider_name, model_name = "rules", "deterministic-template"
    reply: dict | None = None
    raw_payload: dict | None = None

    if result is not None:
        raw, provider_name, model_name = result
        raw_payload = raw if isinstance(raw, dict) else None
        try:
            reply = ChatReplyJSON.model_validate(raw).model_dump(mode="json")
        except ValidationError as exc:
            logger.warning("Chat schema validation failed for %s: %s", provider_name, exc)
            reply = None
            provider_name, model_name = "rules", "deterministic-template"

    if reply is None:
        if intent == WORKOUT_AUDIT:
            reply = template_autopsy(
                message, safety, hits, session_packet=session_packet, context=context
            )
        elif intent == WEEK_REVIEW:
            reply = template_week_review(
                message,
                safety,
                hits,
                packet=week_packet,
                context=context,
            )
        elif intent == WEEK_PLAN_REVIEW:
            reply = template_week_plan_review(
                message,
                safety,
                hits,
                current_plan=current_plan,
                context=context,
                clock=clock,
            )
        elif intent == SCHEDULE_UPDATE:
            reply = template_schedule(
                message,
                safety,
                hits,
                current_plan=current_plan,
                context=context,
                clock=clock,
            )
        elif intent == DAY_ADJUST:
            reply = template_day_adjust(
                message,
                safety,
                hits,
                current_plan=current_plan,
                context=context,
                clock=clock,
            )
        elif intent == SCIENCE_LOOKUP:
            reply = template_science_lookup(
                message,
                safety,
                hits,
                grounded=science_grounded,
                context=context,
            )
        else:
            reply = template_general_chat(message, safety, hits)

    reply["intent"] = intent
    applied_plan = None
    if intent == DAY_ADJUST and persist_plan:
        plan_data = extract_week_plan_from_chat(
            raw=raw_payload or reply,
            reply_text=reply.get("reply") or "",
            week_start=clock["week_start"],
        )
        try:
            applied_plan = persist_today_adjustment(
                db,
                profile,
                today=clock["today"],
                week_start=clock["week_start"],
                plan_data=plan_data,
                safety=safety,
                hits=hits,
                provider=provider_name,
                model=model_name,
            )
            reply["plan_id"] = applied_plan.get("plan_id")
        except Exception as exc:  # noqa: BLE001 — chat must still return
            logger.warning("Could not persist today-only adjustment: %s", exc)
    elif intent == SCHEDULE_UPDATE and persist_plan:
        plan_data = extract_week_plan_from_chat(
            raw=raw_payload or reply,
            reply_text=reply.get("reply") or "",
            week_start=clock["week_start"],
        )
        if plan_data:
            try:
                applied_plan = persist_week_from_chat(
                    db,
                    profile,
                    plan_data=plan_data,
                    clock=clock,
                    safety=safety,
                    hits=hits,
                    provider=provider_name,
                    model=model_name,
                )
                reply["plan_id"] = applied_plan.get("plan_id")
            except Exception as exc:  # noqa: BLE001 — chat must still return the table
                logger.warning("Could not persist chat week: %s", exc)
    logger.info("Coach routed intent=%s source=%s", intent, decision_source)

    _store_assistant_message(db, profile.id, reply, provider_name)

    return {
        "provider": provider_name,
        "model": model_name,
        "reply": reply,
        "citations": [hit["citation"] for hit in hits],
        "history": chat_history(db, profile.id),
        "disclaimer": safety["disclaimer"],
        "plan": applied_plan,
    }


def _decode_message_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return {
            "citations": data.get("citations") or [],
            "plan_id": data.get("plan_id"),
            "intent": data.get("intent"),
        }
    if isinstance(data, list):
        return {"citations": data}
    return {}


def _history_meta_fields(raw: str | None) -> dict:
    meta = _decode_message_meta(raw)
    fields = {}
    if meta.get("intent"):
        fields["intent"] = meta["intent"]
    if meta.get("plan_id"):
        fields["plan_id"] = meta["plan_id"]
    return fields


def _store_assistant_message(db: Session, profile_id: int, reply: dict, provider: str) -> None:
    citations = reply.get("citations") or []
    payload: dict | list = citations
    if reply.get("plan_id") or reply.get("intent"):
        payload = {
            "citations": citations,
            "plan_id": reply.get("plan_id"),
            "intent": reply.get("intent"),
        }
    db.add(
        CoachMessage(
            athlete_profile_id=profile_id,
            role="assistant",
            content=reply["reply"],
            citations=json.dumps(payload),
            provider=provider,
        )
    )
    db.commit()


def confirm_baseline(db: Session, profile: AthleteProfile) -> AthleteProfile:
    profile.baseline_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile
