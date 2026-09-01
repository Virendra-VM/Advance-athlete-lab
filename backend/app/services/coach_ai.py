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
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai_schemas import ChatReplyJSON, DailyAdviceJSON, WeekPlanJSON
from app.models import AthleteProfile, CoachMessage, PlannedWorkout, TrainingPlan
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
    template_chat_reply,
)
from app.services.science_kb import (
    citation_slugs,
    format_science_for_prompt,
    retrieve_science,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the coaching engine inside Advance Athlete Lab, an endurance and \
general-fitness training platform. You write training guidance for one athlete at a time using \
their profile, wearable data, and the retrieved evidence provided.

Non-negotiable rules:
- You are a coach, not a clinician. Never diagnose, never prescribe rehabilitation protocols, \
never give clinical nutrition or medication advice.
- Respect every numeric constraint in the SAFETY RULES section exactly. They are hard limits.
- Cite only the retrieved evidence labels ([S1], [S2], ...). Never invent a source, author, or year.
- If the evidence does not cover something, say it is your coaching judgement or that the evidence \
is unclear.
- If the athlete reports a red-flag symptom (chest pain, faintness, numbness, suspected fracture, \
fever), set escalate to true and tell them to seek professional assessment instead of training.
- The NOW block is ground truth for date, time, weekday, and whose local timezone this is. \
If an activity is labelled "today", it already happened today — never describe it as a past date \
without saying it is today. Late in the week, do not say "start this week"; coach remaining days only.
- Reply with a single JSON object and nothing else. No prose, no markdown fences."""

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
  "escalation_reason": null
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
    local = _parse_local_date(activity.get("activity_date"), clock["tz"])
    return {
        "date": local.isoformat() if local else str(activity.get("activity_date") or "")[:10],
        "when": _when_label(local, clock["today"]) if local else None,
        "sport": activity.get("sport_type"),
        "name": activity.get("name"),
        "km": round((activity.get("distance_m") or 0) / 1000.0, 2),
        "minutes": round((activity.get("moving_time_s") or 0) / 60.0),
        "avg_hr": activity.get("average_heartrate"),
    }


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
    digest = {
        "profile": profile,
        "readiness_flags": context.get("readiness_flags") or [],
        "recent_activities": [
            _activity_digest_row(activity, clock)
            for activity in (context.get("recent_activities") or [])[:20]
        ],
        "latest_health": coros.get("latest_health"),
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


def _retrieve(db: Session, query: str, profile: AthleteProfile, k: int = 6) -> list[dict]:
    return retrieve_science(db, query, sports=sports_for_retrieval(profile), k=k)


def _call_provider(system: str, user: str) -> tuple[dict, str, str] | None:
    """Try each configured provider once. Returns (data, provider, model) or None."""
    for provider in provider_chain():
        try:
            response = provider.generate_json(system, user)
            return response.data, response.provider, response.model
        except ProviderError as exc:
            logger.warning("Provider %s failed: %s", provider.name, exc)
        except Exception as exc:  # noqa: BLE001 - never let a provider break the request
            logger.warning("Provider %s raised: %s", provider.name, exc)
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
acknowledge it. Do not talk as if the week is starting unless it is Monday or Tuesday.
Reference the athlete's own numbers (sleep, HRV, resting HR, recent load) in the rationale.

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
        }
        for row in rows
    ]


def coach_chat(
    db: Session,
    profile: AthleteProfile,
    message: str,
    timezone_name: str | None = None,
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

    hits = _retrieve(db, message, profile, k=5)
    history = chat_history(db, profile.id, limit=12)
    transcript = "\n".join(
        f"{entry['role'].upper()}: {entry['content']}" for entry in history[:-1][-8:]
    )
    current_plan = get_active_plan(db, profile.id, clock["week_start"])

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

ATHLETE MESSAGE
{message.strip()}

TASK
Answer as their coach. Use the NOW block: if they trained today, say today — not only the date.
If it is Friday–Sunday, do not tell them to "start this week easy"; talk about remaining days.
Be specific to their data and constraints, keep it under 220 words, and never contradict the safety rules.

Respond with JSON matching exactly this shape:
{CHAT_SCHEMA}"""

    result = _call_provider(SYSTEM_PROMPT, user_prompt)
    provider_name, model_name = "rules", "deterministic-template"
    reply: dict | None = None

    if result is not None:
        raw, provider_name, model_name = result
        try:
            reply = ChatReplyJSON.model_validate(raw).model_dump(mode="json")
        except ValidationError as exc:
            logger.warning("Chat schema validation failed for %s: %s", provider_name, exc)
            reply = None
            provider_name, model_name = "rules", "deterministic-template"

    if reply is None:
        reply = template_chat_reply(message, safety, hits)

    _store_assistant_message(db, profile.id, reply, provider_name)

    return {
        "provider": provider_name,
        "model": model_name,
        "reply": reply,
        "citations": [hit["citation"] for hit in hits],
        "history": chat_history(db, profile.id),
        "disclaimer": safety["disclaimer"],
    }


def _store_assistant_message(db: Session, profile_id: int, reply: dict, provider: str) -> None:
    db.add(
        CoachMessage(
            athlete_profile_id=profile_id,
            role="assistant",
            content=reply["reply"],
            citations=json.dumps(reply.get("citations") or []),
            provider=provider,
        )
    )
    db.commit()


def confirm_baseline(db: Session, profile: AthleteProfile) -> AthleteProfile:
    profile.baseline_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile
