"""Coach generation pipeline.

    athlete context + science retrieval + safety rules
        -> provider (JSON) -> pydantic validation -> safety validator -> persist

Every surface degrades gracefully: provider missing or failing falls back to the
deterministic templates, and a plan that fails the safety validator is replaced
rather than shown.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import AI_DEBUG
from app.ai_schemas import ChatReplyJSON, DailyAdviceJSON, WeekPlanJSON
from app.models import Activity, ActivityNote, AthleteProfile, CoachMessage, PlannedWorkout, TrainingPlan
from app.services.ai import ProviderError, provider_chain
from app.services.athlete_coach_context import build_athlete_coach_context
from app.services.coach_safety import (
    detect_red_flags,
    safety_prompt_rules,
    sports_for_retrieval,
    strip_intensity,
    validate_plan,
)
from app.services.coach_templates import (
    build_template_advice,
    build_template_week,
)
from app.services.science_kb import (
    citation_slugs,
    format_science_for_prompt,
    retrieve_science,
)
from app.services.ai_coach import (
    AUTOPSY_SCHEMA,
    BASE_SYSTEM_PROMPT as SYSTEM_PROMPT,
    athlete_state_block,
    autopsy_task_for_packet,
    coach_modality,
    retrieval_query_for_modality,
    science_sports_for_modality,
    schedule_system_prompt,
    schedule_task,
    system_prompt_for_modality,
    template_autopsy,
    template_general_chat,
    template_schedule,
    today_call_prompt_block,
)
from app.services.coach_intent import (
    SCHEDULE_UPDATE,
    WORKOUT_AUDIT,
    classify_chat_intent_detailed,
    normalize_intent,
)
from app.services.session_plan import build_session_plan_overlay
from app.services.week_from_chat import coerce_week_plan, parse_week_plan_from_text
from app.services.session_telemetry import (
    analyze_activity,
    laps_are_uninformative,
    match_activity_for_message,
)

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
      "description": "string with warm-up, main set, cool-down",
      "structure": [{"segment": "string", "duration_min": number, "intensity": "string"}]
    }
  ],
  "coach_notes": "string",
  "citations": ["S1"]
}"""

ADVICE_SCHEMA = """{
  "headline": "string, max 10 words",
  "recommendation": "string, what to do today",
  "session_adjustment": "string or null",
  "rationale": "string referencing the athlete's own numbers",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null
}"""

CHAT_SCHEMA = """{
  "reply": "string, conversational but specific",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "GENERAL_CHAT"
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
        "description": "string"
      }
    ]
  }
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


def _activity_digest_row(activity: dict, clock: dict) -> dict:
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


def _context_digest(context: dict, clock: dict | None = None) -> str:
    """Compact, prompt-friendly view of the athlete. Excludes sensitive extras."""
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
            _activity_digest_row(activity, clock)
            for activity in (context.get("recent_activities") or [])[:20]
        ],
        "recent_key_sessions": [
            _activity_digest_row(session, clock)
            for session in (context.get("focal_sessions") or [])[:3]
        ],
        "latest_health": coros.get("latest_health"),
        "health_trend": coros.get("health_trend") or [],
        "fitness": coros.get("fitness"),
        "training_load": coros.get("training_load"),
        "upcoming_schedule": coros.get("schedule") or [],
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

ATHLETE CONTEXT
{_context_digest(context, clock)}

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

Respond with JSON matching exactly this shape:
{WEEK_PLAN_SCHEMA}"""


def plan_retrieval_query(context: dict, profile: AthleteProfile) -> str:
    goal = context["profile"].get("primary_goal") or "general fitness"
    return f"weekly training structure for {goal} {' '.join(sports_for_retrieval(profile))}"


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
        db.add(
            PlannedWorkout(
                training_plan_id=record.id,
                athlete_profile_id=profile.id,
                workout_date=workout_date,
                sport=workout.get("sport"),
                title=workout.get("title"),
                session_type=workout.get("session_type"),
                duration_min=workout.get("duration_min"),
                distance_m=workout.get("distance_m"),
                intensity=workout.get("intensity"),
                description=workout.get("description"),
                structure_json=json.dumps(workout.get("structure") or []),
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
    plan_data = validation["plan"]
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
    )
    _copy_completions_from_superseded(db, profile.id, start, plan_id)
    payload = get_active_plan(db, profile.id, start) or {}
    payload["disclaimer"] = safety.get("disclaimer")
    payload["generation_notes"] = payload.get("generation_notes") or []
    payload["safety_issues"] = issues
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


def generate_daily_advice(
    db: Session, profile: AthleteProfile, timezone_name: str | None = None
) -> dict:
    clock = resolve_clock(timezone_name)
    context = build_athlete_coach_context(db, profile.id)
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
the rationale.

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
            "Coach intent=%s source=%s audit=%s schedule=%s",
            decision.intent,
            decision.source,
            decision.audit_score,
            decision.schedule_score,
        )
    intent = resolved_intent

    history = chat_history(db, profile.id, limit=12)
    current_plan = get_active_plan(db, profile.id, clock["week_start"])
    session_packet = None
    modality = None
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
    elif intent == SCHEDULE_UPDATE:
        hits = _retrieve(
            db,
            "weekly training plan ACWR consecutive hard days spinal load recovery sleep HRV "
            + message[:180],
            profile,
            k=5,
        )
    else:
        hits = _retrieve(db, message, profile, k=5)

    has_prescription = bool(
        session_packet
        and (session_packet.get("prescription") or session_packet.get("prescribed_vs_executed"))
    )
    drop_assistant = has_prescription or intent == SCHEDULE_UPDATE
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
    elif intent == SCHEDULE_UPDATE:
        extra_block = f"""
{today_call_prompt_block(context, safety)}

{athlete_state_block(context, safety)}

ROUTING (hard)
Intent is SCHEDULE_UPDATE. Do not autopsy a past ride. Do not load or invent session telemetry.
Do not write essays or paragraphs. Bullets, key-values, and the week table only.
Use CURRENT WEEK PLAN plus the athlete's proposed calendar.
Copy TODAY'S CALL status line exactly. Guard active back/spine limits with non-negotiable DO NOT lifts on strength days.
"""
    else:
        extra_block = f"\n{athlete_state_block(context, safety)}\n"

    if intent == WORKOUT_AUDIT:
        task = autopsy_task_for_packet(modality, session_packet)
        chat_schema = AUTOPSY_SCHEMA
        system_prompt = system_prompt_for_modality(modality)
    elif intent == SCHEDULE_UPDATE:
        task = schedule_task()
        chat_schema = SCHEDULE_SCHEMA
        system_prompt = schedule_system_prompt()
    else:
        task = """Answer as their coach. Use the NOW block: if they trained today, say today — not only the date.
If it is Friday–Sunday, do not tell them to "start this week easy"; talk about remaining days.
Be specific to their data and constraints, keep it under 400 words, and never contradict the safety rules.
Do not treat typical session length as a hard cap on long rides.
Do not autopsy a past workout unless they asked how that session went.
Match the sport of any session you discuss."""
        chat_schema = CHAT_SCHEMA
        system_prompt = SYSTEM_PROMPT

    user_prompt = f"""{format_clock_block(clock)}

ATHLETE CONTEXT
{_context_digest(context, clock)}

CURRENT WEEK PLAN
{_plan_digest(current_plan, clock)}

SAFETY RULES (hard limits)
{safety_prompt_rules(safety, weekday_index=clock["weekday_index"])}

RECENT CONVERSATION
{transcript or '(none)'}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}
{extra_block}
ATHLETE MESSAGE
{message.strip()}

TASK
{task}

Respond with JSON matching exactly this shape:
{chat_schema}"""

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
        elif intent == SCHEDULE_UPDATE:
            reply = template_schedule(
                message,
                safety,
                hits,
                current_plan=current_plan,
                context=context,
                clock=clock,
            )
        else:
            reply = template_general_chat(message, safety, hits)

    reply["intent"] = intent
    applied_plan = None
    if intent == SCHEDULE_UPDATE:
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
