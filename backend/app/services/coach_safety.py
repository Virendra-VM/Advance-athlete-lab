"""Deterministic safety layer.

The LLM proposes; this module decides. It derives hard caps from the athlete's
profile, injuries, readiness signals, and recent load, then validates (and where
possible repairs) a generated plan before the athlete ever sees it.

Nothing here calls a model, so it is fully testable and always runs.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Activity, AthleteInjury, AthleteProfile, DailyHealthMetric
from app.services.athlete_profile import load_json_column

HARD_SESSION_TYPES = {"intervals", "vo2", "threshold", "tempo", "race", "hills", "speed", "hard"}
REST_SESSION_TYPES = {"rest", "off", "recovery", "mobility"}

# Conservative planning defaults for an athlete with an ACTIVE issue.
# These reduce risk in generated plans; they are not treatment.
INJURY_RULES: dict[str, dict] = {
    "knee": {
        "avoid_keywords": ["plyometric", "jump", "box jump", "downhill", "deep squat", "lunge jump"],
        "avoid_session_types": ["hills", "speed"],
        "prefer": ["cycling", "swimming", "hip-dominant strength"],
    },
    "lower back": {
        "avoid_keywords": ["deadlift", "good morning", "sit-up", "crunch", "loaded twist", "back squat"],
        "avoid_session_types": [],
        "prefer": ["walking", "swimming", "anti-extension core work"],
    },
    "ankle": {
        "avoid_keywords": ["jump", "plyometric", "trail", "sprint"],
        "avoid_session_types": ["hills", "speed"],
        "prefer": ["cycling", "swimming", "pool running"],
    },
    "foot": {
        "avoid_keywords": ["jump", "plyometric", "barefoot", "sprint"],
        "avoid_session_types": ["hills", "speed"],
        "prefer": ["cycling", "swimming"],
    },
    "hip": {
        "avoid_keywords": ["deep squat", "sprint", "high-knee"],
        "avoid_session_types": ["speed"],
        "prefer": ["swimming", "controlled glute strength"],
    },
    "shoulder": {
        "avoid_keywords": ["overhead press", "snatch", "pull-up", "freestyle volume", "bench press"],
        "avoid_session_types": [],
        "prefer": ["lower-body strength", "scapular strength"],
    },
    "achilles": {
        "avoid_keywords": ["jump", "plyometric", "sprint", "hill repeat"],
        "avoid_session_types": ["hills", "speed", "intervals"],
        "prefer": ["cycling", "isometric calf loading"],
    },
    "calf": {
        "avoid_keywords": ["jump", "plyometric", "sprint", "hill repeat"],
        "avoid_session_types": ["hills", "speed"],
        "prefer": ["cycling", "swimming"],
    },
    "hamstring": {
        "avoid_keywords": ["sprint", "stride", "deadlift", "kick"],
        "avoid_session_types": ["speed"],
        "prefer": ["cycling", "eccentric hamstring loading"],
    },
    "wrist": {
        "avoid_keywords": ["push-up", "front rack", "handstand", "bench press"],
        "avoid_session_types": [],
        "prefer": ["lower-body strength", "machine-based work"],
    },
    "elbow": {
        "avoid_keywords": ["pull-up", "curl", "push-up"],
        "avoid_session_types": [],
        "prefer": ["lower-body strength"],
    },
    "neck": {
        "avoid_keywords": ["overhead press", "shrug", "bridge"],
        "avoid_session_types": [],
        "prefer": ["walking", "cycling upright"],
    },
}

# Phrases that mean "stop and see a professional", never "here is a workaround".
RED_FLAG_PATTERNS = [
    r"chest (pain|pressure|tight)",
    r"\bfaint(ed|ing)?\b",
    r"\bblack(ed)? out\b",
    r"can'?t (breathe|bear weight)",
    r"\bnumb(ness)?\b",
    r"slurred speech",
    r"stress fracture",
    r"\bfever\b",
    r"\bdizzy\b|\bdizziness\b",
    r"sharp (bone|shin) pain",
    r"\bswollen joint\b",
]


def _text(value) -> str:
    return (value or "").strip().lower()


def detect_red_flags(text: str) -> list[str]:
    """Return the red-flag phrases present in free text (athlete question or notes)."""
    haystack = _text(text)
    hits = []
    for pattern in RED_FLAG_PATTERNS:
        match = re.search(pattern, haystack)
        if match:
            hits.append(match.group(0))
    return hits


def _injury_rule(body_region: str) -> dict | None:
    region = _text(body_region)
    for key, rule in INJURY_RULES.items():
        if key in region:
            return rule
    return None


def injury_constraints_from_records(rows) -> dict:
    """Pure form of :func:`injury_constraints`.

    ``rows`` only needs ``body_region``, ``condition``, ``status``, ``severity``,
    so synthetic athletes (eval harness, tests) can reuse the same rules.
    """
    active, past = [], []
    avoid_keywords: set[str] = set()
    avoid_session_types: set[str] = set()
    prefer: set[str] = set()

    for row in rows:
        label = row.body_region if not row.condition else f"{row.body_region} ({row.condition})"
        if row.status == "active":
            active.append(label)
            rule = _injury_rule(row.body_region)
            if rule:
                avoid_keywords.update(rule["avoid_keywords"])
                avoid_session_types.update(rule["avoid_session_types"])
                prefer.update(rule["prefer"])
        else:
            past.append(label)

    return {
        "active": active,
        "past": past,
        "avoid_keywords": sorted(avoid_keywords),
        "avoid_session_types": sorted(avoid_session_types),
        "prefer": sorted(prefer),
        "has_severe_active": any(
            row.status == "active" and _text(row.severity) == "severe" for row in rows
        ),
    }


def injury_constraints(db: Session, athlete_profile_id: int) -> dict:
    rows = (
        db.query(AthleteInjury)
        .filter(AthleteInjury.athlete_profile_id == athlete_profile_id)
        .all()
    )
    return injury_constraints_from_records(rows)


def readiness_flags_from_signals(
    *,
    recovery_pct: float | None = None,
    sleep_score: float | None = None,
    stress: float | None = None,
    hrv: float | None = None,
    hrv_assessment: str | None = None,
    load_ratio: float | None = None,
) -> list[str]:
    """Single definition of the readiness flag vocabulary."""
    flags: list[str] = []
    if recovery_pct is not None:
        if recovery_pct < 40:
            flags.append("low_recovery")
        elif recovery_pct < 70:
            flags.append("moderate_recovery")
        else:
            flags.append("good_recovery")
    if sleep_score is not None and sleep_score < 60:
        flags.append("poor_sleep")
    if stress is not None and stress >= 70:
        flags.append("elevated_stress")
    if hrv is not None and hrv_assessment:
        flags.append(f"hrv_{str(hrv_assessment).lower()}")
    if load_ratio is not None:
        if load_ratio >= 1.5:
            flags.append("high_training_load_ratio")
        elif load_ratio <= 0.8:
            flags.append("low_training_load_ratio")
    return flags


def readiness_directive(readiness_flags: list[str]) -> dict:
    """Translate readiness flags into one deterministic instruction."""
    flags = set(readiness_flags or [])
    poor = {"poor_sleep", "elevated_stress", "low_recovery"} & flags
    hrv_poor = any(
        flag.startswith("hrv_") and any(word in flag for word in ("unbalanced", "low", "poor"))
        for flag in flags
    )
    if hrv_poor:
        poor.add("hrv_unbalanced")
    if "high_training_load_ratio" in flags:
        poor.add("high_training_load_ratio")

    if len(poor) >= 2:
        return {
            "action": "rest_or_mobility",
            "max_hard_sessions_today": 0,
            "reason": "Two or more recovery markers are poor: "
            + ", ".join(sorted(poor)).replace("_", " ")
            + ".",
        }
    if poor:
        return {
            "action": "downgrade_to_easy",
            "max_hard_sessions_today": 0,
            "reason": "One recovery marker is poor: "
            + ", ".join(sorted(poor)).replace("_", " ")
            + ".",
        }
    return {
        "action": "proceed",
        "max_hard_sessions_today": 1,
        "reason": "Recovery markers look normal.",
    }


def _recent_weekly_minutes(db: Session, athlete_profile_id: int) -> dict:
    now = datetime.utcnow()
    last_7 = (
        db.query(func.coalesce(func.sum(Activity.moving_time_s), 0))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= now - timedelta(days=7),
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
        or 0
    )
    last_28 = (
        db.query(func.coalesce(func.sum(Activity.moving_time_s), 0))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= now - timedelta(days=28),
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
        or 0
    )
    acute = round(float(last_7) / 60.0)
    chronic = round(float(last_28) / 60.0 / 4.0)
    ratio = round(acute / chronic, 2) if chronic > 0 else None
    return {"acute_minutes": acute, "chronic_minutes": chronic, "minutes_acwr": ratio}


def max_hard_sessions_for_week(days_per_week: int | None, fitness_level: str | None) -> int:
    days = days_per_week or 3
    level = _text(fitness_level)
    if level.startswith("complete beginner"):
        return 0 if days <= 2 else 1
    if days <= 2:
        return 1
    if days <= 3:
        return 1
    if days <= 5:
        return 2
    return 3


def compose_safety_profile(
    *,
    days_per_week: int | None,
    session_minutes: int | None,
    weekly_minutes_budget: int | None,
    fitness_level: str | None,
    injuries: dict,
    readiness_flags: list[str],
    load: dict,
    latest_health_date: str | None = None,
    longest_recent_session: str | int | None = None,
) -> dict:
    """Pure constraint builder shared by the live path and the eval harness."""
    from app.services.session_telemetry import parse_duration_minutes

    directive = readiness_directive(readiness_flags)

    days = days_per_week or 3
    typical = session_minutes or 45
    session_minutes = typical
    if isinstance(longest_recent_session, (int, float)):
        longest = int(longest_recent_session)
    else:
        longest = parse_duration_minutes(longest_recent_session) or 0

    # Typical weekday length is a mode, not a cap. Allow a long endurance day.
    max_session_minutes = min(420, max(round(typical * 4), longest, round(typical * 1.5), 90))

    auto_budget = days * typical
    explicit = weekly_minutes_budget
    looks_like_days_times_typical = explicit is None or abs(explicit - auto_budget) <= max(
        15, round(typical * 0.1)
    )
    # Onboarding stores days × typical as a default. That must not freeze every
    # session at typical length or block a single 2–4 hour ride.
    if looks_like_days_times_typical:
        budget = auto_budget + max(typical, longest, 90)
    else:
        budget = explicit

    # Clamp growth against recorded history, but only when there is enough of it to
    # trust — otherwise an athlete who just connected a device would get a 0-minute week.
    baseline = max(load["acute_minutes"], load["chronic_minutes"])
    if baseline >= 60:
        growth_cap = round(baseline * 1.15)
        max_weekly_minutes = max(min(budget, growth_cap), min(budget, 180))
    else:
        max_weekly_minutes = budget

    # Poor readiness costs one quality session for the week, and rule 8 also forces
    # the opening session easy.
    base_hard = max_hard_sessions_for_week(days, fitness_level)
    if directive["action"] == "rest_or_mobility":
        max_hard = max(0, base_hard - 1)
    elif directive["action"] == "downgrade_to_easy":
        max_hard = max(0, base_hard - 1) if base_hard > 1 else base_hard
    else:
        max_hard = base_hard

    # A severe active injury removes intensity entirely — the validator blocks any
    # plan that prescribes it, so the caps must agree.
    if injuries.get("has_severe_active"):
        max_hard = 0

    return {
        "max_days_per_week": days,
        "typical_session_minutes": typical,
        "max_session_minutes": max_session_minutes,
        "weekly_minutes_budget": budget,
        "max_weekly_minutes": max_weekly_minutes,
        "max_hard_sessions": max_hard,
        "require_rest_day": days < 7,
        "no_consecutive_hard_days": True,
        "injuries": injuries,
        "readiness": directive,
        "load": load,
        "latest_health_date": latest_health_date,
        "disclaimer": (
            "Training guidance only — not medical advice. Stop and seek professional "
            "assessment for chest pain, faintness, new neurological symptoms, or acute injury."
        ),
    }


def build_safety_profile(
    db: Session,
    profile: AthleteProfile,
    readiness_flags: list[str],
) -> dict:
    """The hard constraints a generated plan must satisfy, for a stored athlete."""
    latest_health = (
        db.query(DailyHealthMetric)
        .filter(DailyHealthMetric.athlete_profile_id == profile.id)
        .order_by(DailyHealthMetric.metric_date.desc())
        .first()
    )
    return compose_safety_profile(
        days_per_week=profile.days_per_week,
        session_minutes=profile.workout_duration_minutes,
        weekly_minutes_budget=profile.weekly_minutes_budget,
        fitness_level=profile.fitness_level,
        injuries=injury_constraints(db, profile.id),
        readiness_flags=readiness_flags,
        load=_recent_weekly_minutes(db, profile.id),
        latest_health_date=latest_health.metric_date.isoformat() if latest_health else None,
        longest_recent_session=profile.longest_recent_session,
    )


# ---------------------------------------------------------------- validation


def _session_text(workout: dict) -> str:
    return " ".join(
        _text(workout.get(field))
        for field in ("title", "description", "session_type", "intensity", "sport")
    )


def _is_hard(workout: dict) -> bool:
    session_type = _text(workout.get("session_type"))
    if session_type in HARD_SESSION_TYPES:
        return True
    intensity = _text(workout.get("intensity"))
    return any(word in intensity for word in ("hard", "vo2", "threshold", "race pace"))


def _is_rest(workout: dict) -> bool:
    return _text(workout.get("session_type")) in REST_SESSION_TYPES


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def validate_plan(plan: dict, safety: dict) -> dict:
    """Repair what is repairable, report everything, and flag blocking problems.

    Returns ``{"plan": <adjusted>, "issues": [...], "blocked": bool}``.
    """
    issues: list[dict] = []
    workouts = list(plan.get("workouts") or [])

    def add(level: str, code: str, message: str) -> None:
        issues.append({"level": level, "code": code, "message": message})

    # Sort by date so consecutive-day rules are meaningful.
    workouts.sort(key=lambda item: str(item.get("date") or ""))

    # 1. Session duration ceiling.
    max_session = safety["max_session_minutes"]
    for workout in workouts:
        duration = workout.get("duration_min")
        if isinstance(duration, (int, float)) and duration > max_session:
            add(
                "adjusted",
                "session_too_long",
                f"{workout.get('title') or 'Session'} trimmed from {round(duration)} to {max_session} min.",
            )
            workout["duration_min"] = max_session

    # 2. Injury contraindications.
    avoid_keywords = safety["injuries"]["avoid_keywords"]
    avoid_types = set(safety["injuries"]["avoid_session_types"])
    for workout in workouts:
        text = _session_text(workout)
        hit = next((keyword for keyword in avoid_keywords if keyword in text), None)
        session_type = _text(workout.get("session_type"))
        if hit or (session_type and session_type in avoid_types):
            reason = hit or session_type
            add(
                "adjusted",
                "injury_contraindication",
                f"{workout.get('title') or 'Session'} conflicts with an active injury ({reason}); "
                "converted to easy aerobic work.",
            )
            workout["session_type"] = "easy"
            workout["intensity"] = "Easy / conversational"
            workout["title"] = f"Easy {workout.get('sport') or 'aerobic'} session"
            workout["description"] = (
                "Replaced automatically to protect an active injury. Keep effort conversational and "
                "stop if you feel pain. Preferred alternatives: "
                + (", ".join(safety["injuries"]["prefer"]) or "low-impact aerobic work")
                + "."
            )

    # 3. Hard-session budget.
    max_hard = safety["max_hard_sessions"]
    hard_indexes = [index for index, workout in enumerate(workouts) if _is_hard(workout)]
    if len(hard_indexes) > max_hard:
        for index in hard_indexes[max_hard:]:
            workout = workouts[index]
            add(
                "adjusted",
                "too_many_hard_sessions",
                f"{workout.get('title') or 'Session'} downgraded to easy — "
                f"weekly cap is {max_hard} hard session(s).",
            )
            workout["session_type"] = "easy"
            workout["intensity"] = "Easy / conversational"
        hard_indexes = hard_indexes[:max_hard]

    # 4. No back-to-back hard days.
    if safety["no_consecutive_hard_days"]:
        previous_hard_date: date | None = None
        for workout in workouts:
            if not _is_hard(workout):
                continue
            current = _parse_date(workout.get("date"))
            if previous_hard_date and current and (current - previous_hard_date).days <= 1:
                add(
                    "adjusted",
                    "consecutive_hard_days",
                    f"{workout.get('title') or 'Session'} downgraded to easy — hard days must be separated.",
                )
                workout["session_type"] = "easy"
                workout["intensity"] = "Easy / conversational"
                continue
            previous_hard_date = current or previous_hard_date

    # 5. Weekly volume ceiling.
    total_minutes = sum(
        float(workout.get("duration_min") or 0)
        for workout in workouts
        if not _is_rest(workout)
    )
    max_weekly = safety["max_weekly_minutes"]
    if total_minutes > max_weekly * 1.05 and total_minutes > 0:
        scale = max_weekly / total_minutes
        add(
            "adjusted",
            "weekly_volume_exceeded",
            f"Week scaled from {round(total_minutes)} to {round(max_weekly)} min "
            "to respect the load-progression cap.",
        )
        for workout in workouts:
            if _is_rest(workout):
                continue
            duration = workout.get("duration_min")
            if isinstance(duration, (int, float)):
                workout["duration_min"] = max(10, round(duration * scale))

    # 6. Training-day count.
    training_days = {
        str(workout.get("date"))[:10] for workout in workouts if not _is_rest(workout)
    }
    if len(training_days) > safety["max_days_per_week"]:
        add(
            "warning",
            "too_many_training_days",
            f"Plan uses {len(training_days)} training days; the athlete committed to "
            f"{safety['max_days_per_week']}.",
        )

    # 7. Rest day present.
    if safety["require_rest_day"] and len(training_days) >= 7:
        add("warning", "no_rest_day", "No rest day in the week — at least one is expected.")

    # 8. Readiness directive respected for the first day.
    directive = safety["readiness"]
    if directive["action"] != "proceed" and workouts:
        first = workouts[0]
        if _is_hard(first):
            add(
                "adjusted",
                "readiness_override",
                f"Opening session downgraded: {directive['reason']}",
            )
            first["session_type"] = "rest" if directive["action"] == "rest_or_mobility" else "easy"
            first["intensity"] = "Recovery"

    # 9. Blocking conditions — the plan must not be shown as-is.
    blocked = False
    if not workouts:
        add("blocking", "empty_plan", "Generated plan contained no sessions.")
        blocked = True
    if safety["injuries"]["has_severe_active"] and any(_is_hard(w) for w in workouts):
        add(
            "blocking",
            "severe_active_injury",
            "A severe active injury is on file — intensity cannot be prescribed without "
            "professional clearance.",
        )
        blocked = True

    adjusted = dict(plan)
    adjusted["workouts"] = workouts
    return {"plan": adjusted, "issues": issues, "blocked": blocked}


def strip_intensity(plan: dict) -> dict:
    """Force every session in a plan to easy aerobic work."""
    stripped = dict(plan)
    workouts = []
    for workout in plan.get("workouts") or []:
        session = dict(workout)
        if not _is_rest(session):
            session["session_type"] = "easy"
            session["intensity"] = "Easy / conversational"
        workouts.append(session)
    stripped["workouts"] = workouts
    return stripped


def safety_prompt_rules(safety: dict, weekday_index: int | None = None) -> str:
    """Human-readable constraints injected into the model prompt."""
    injuries = safety["injuries"]
    typical = safety.get("typical_session_minutes") or 45
    lines = [
        f"- Maximum {safety['max_days_per_week']} training days this week.",
        f"- Typical session length is {typical} minutes. That is a usual weekday length, "
        "NOT a target for every session and NOT a cap. Long endurance sessions may be 90-240 minutes.",
        f"- Hard ceiling for any single session: {safety['max_session_minutes']} minutes.",
        f"- Weekly minutes target is about {safety['max_weekly_minutes']}. Do not build the week as "
        f"{safety['max_days_per_week']} × {typical} equal sessions.",
        f"- Maximum {safety['max_hard_sessions']} hard/quality session(s); never on consecutive days.",
    ]
    if safety["require_rest_day"]:
        lines.append("- Include at least one full rest day.")
    if injuries["has_severe_active"]:
        lines.append(
            "- A severe active injury is on file: prescribe no intensity at all, keep every "
            "session easy or mobility, and tell the athlete to seek professional clearance."
        )
    if injuries["active"]:
        lines.append(
            f"- Active injuries: {', '.join(injuries['active'])}. "
            f"Avoid: {', '.join(injuries['avoid_keywords']) or 'high-impact loading'}. "
            f"Prefer: {', '.join(injuries['prefer']) or 'low-impact aerobic work'}."
        )
    if injuries["past"]:
        lines.append(f"- Past injuries to respect: {', '.join(injuries['past'])}.")
    readiness = safety["readiness"]
    if readiness["action"] != "proceed":
        if weekday_index is not None and weekday_index >= 5:
            lines.append(
                f"- Readiness: {readiness['reason']} The week is almost over — coach remaining "
                "days only. Do not tell them to start the week over."
            )
        elif weekday_index is not None and weekday_index >= 3:
            lines.append(
                f"- Readiness: {readiness['reason']} Adjust remaining sessions this week; "
                "do not restart from Monday."
            )
        else:
            lines.append(
                f"- Readiness: {readiness['reason']} Start the week easy or with recovery."
            )
    load = safety["load"]
    if load["acute_minutes"] or load["chronic_minutes"]:
        lines.append(
            f"- Recent load: {load['acute_minutes']} min last 7 days vs "
            f"{load['chronic_minutes']} min/week 28-day average"
            + (f" (ratio {load['minutes_acwr']})." if load["minutes_acwr"] else ".")
        )
    lines.append(
        "- Never diagnose, prescribe rehabilitation, or claim medical authority. Refer to a "
        "professional for pain, illness, or red-flag symptoms."
    )
    return "\n".join(lines)


def sports_for_retrieval(profile: AthleteProfile) -> list[str]:
    sports = load_json_column(profile.primary_sports) or []
    if isinstance(sports, dict):
        sports = list(sports.keys())
    return [str(sport) for sport in sports]
