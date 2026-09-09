"""What the athlete's recent training can actually carry.

The periodization engine owns the *shape* of a season — which phase comes next
and how many weeks it gets. This module owns the *size* of the work inside that
shape: how long the long day may run, how often a recovery week is needed, and
whether volume should be held back. Splitting the two keeps the phase skeleton
deterministic and reviewable while the numbers inside it track real history.

Every number here is paired with an athlete-facing note explaining where it came
from, because a cap the athlete cannot explain is a cap they will ignore.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Activity, AthleteInjury, AthleteProfile
from app.services.session_telemetry import parse_duration_minutes
from app.services.training_load import compute_acwr

# Six weeks spans a full mesocycle including its recovery week, so a single easy
# block cannot make an athlete look untrained.
LOOKBACK_DAYS = 42

# A long day may exceed the longest session the athlete has actually completed,
# but only by a step. Single-session jumps beyond ~30% are where durability work
# turns into an injury.
LONG_SESSION_STEP_UP = 1.30
LONG_SESSION_ROUNDING_MIN = 15
MIN_LONG_SESSION_MIN = 60

# With no history at all, twice the athlete's typical weekday session is the most
# we will assume, floored so a plan is still usable.
UNKNOWN_HISTORY_MULTIPLE = 2.0
UNKNOWN_HISTORY_FLOOR_MIN = 90

# Fewer than this many training weeks in the lookback means ratios are jumpy and
# the plan should start conservative.
THIN_BASELINE_WEEKS = 2

HIGH_ACWR = 1.5
# Below this many logged weeks the 28-day denominator is too empty for the ratio
# to mean anything.
ACWR_MIN_WEEKS = 3
MASTERS_AGE = 50

DEFAULT_RECOVERY_CYCLE_WEEKS = 4
SHORT_RECOVERY_CYCLE_WEEKS = 3

SEVERE_INJURY_DAMP = 0.80
ACTIVE_INJURY_DAMP = 0.88
HIGH_ACWR_DAMP = 0.90

LOADING_PHASES = frozenset({"base", "build", "peak"})


def _round_to_step(minutes: float) -> int:
    steps = max(1, round(minutes / LONG_SESSION_ROUNDING_MIN))
    return int(steps * LONG_SESSION_ROUNDING_MIN)


def _is_beginner(fitness_level: str | None) -> bool:
    return (fitness_level or "").strip().lower().startswith("beginner")


def compose_season_baseline(
    *,
    fitness_level: str | None = None,
    age: int | None = None,
    typical_session_minutes: int | None = None,
    longest_recent_session: str | int | None = None,
    chronic_weekly_minutes: int | None = None,
    chronic_weekly_km: float | None = None,
    acwr: float | None = None,
    longest_logged_minutes: int | None = None,
    weeks_with_training: int = 0,
    active_injuries: list[str] | None = None,
    has_severe_active_injury: bool = False,
) -> dict[str, Any]:
    """Pure baseline rules, so tests and the eval harness share one definition."""
    active_injuries = list(active_injuries or [])
    typical = int(typical_session_minutes or 45)

    reported = (
        int(longest_recent_session)
        if isinstance(longest_recent_session, (int, float))
        else parse_duration_minutes(longest_recent_session)
    )
    logged = int(longest_logged_minutes) if longest_logged_minutes else None

    # Recorded sessions beat self-report, but a longer self-report still counts:
    # an athlete may have trained for years before connecting a device.
    if logged and reported:
        longest = max(logged, reported)
        source = "logged" if logged >= reported else "reported"
    elif logged:
        longest, source = logged, "logged"
    elif reported:
        longest, source = reported, "reported"
    else:
        longest, source = None, "typical"

    notes: list[str] = []

    if longest:
        anchor = longest
    else:
        anchor = max(UNKNOWN_HISTORY_FLOOR_MIN, round(typical * UNKNOWN_HISTORY_MULTIPLE))
    ceiling = max(MIN_LONG_SESSION_MIN, _round_to_step(anchor * LONG_SESSION_STEP_UP))

    if source == "logged":
        notes.append(
            f"Long-day ceiling {ceiling} min — your longest session in the last "
            f"{LOOKBACK_DAYS // 7} weeks was {longest} min, stepped up by no more than "
            f"{round((LONG_SESSION_STEP_UP - 1) * 100)}%."
        )
    elif source == "reported":
        notes.append(
            f"Long-day ceiling {ceiling} min — based on the {longest} min longest "
            "session on your profile. It will follow your logged sessions once you "
            "record a longer one."
        )
    else:
        notes.append(
            f"Long-day ceiling {ceiling} min — no long sessions on record yet, so this "
            f"starts from your typical {typical} min session and rises as you log more."
        )

    thin_baseline = weeks_with_training < THIN_BASELINE_WEEKS
    if thin_baseline:
        notes.append(
            f"Only {weeks_with_training} of the last {LOOKBACK_DAYS // 7} weeks have "
            "logged training, so the plan starts conservative and opens up as you train."
        )

    damp = 1.0
    if has_severe_active_injury:
        damp = SEVERE_INJURY_DAMP
    elif active_injuries:
        damp = ACTIVE_INJURY_DAMP

    # A 28-day average needs 28 days behind it. With only a week or two logged,
    # the ratio reads as a huge spike purely because the denominator is empty,
    # and damping a brand-new athlete's plan for that would be wrong.
    acwr_is_trustworthy = weeks_with_training >= ACWR_MIN_WEEKS and not thin_baseline
    spiking = acwr is not None and acwr >= HIGH_ACWR and acwr_is_trustworthy
    if spiking:
        damp = min(damp, HIGH_ACWR_DAMP)

    if active_injuries and damp < 1.0:
        notes.append(
            f"Volume held at {round(damp * 100)}% of the phase target while "
            f"{', '.join(active_injuries)} is active."
        )
    elif damp < 1.0:
        notes.append(
            f"Volume held at {round(damp * 100)}% of the phase target — your 7-day load "
            f"is {acwr}× your 28-day average, which is above the {HIGH_ACWR}× safe band."
        )

    masters = bool(age and age >= MASTERS_AGE)
    beginner = _is_beginner(fitness_level)
    short_cycle_reasons: list[str] = []
    if active_injuries:
        short_cycle_reasons.append("an active injury")
    if masters:
        short_cycle_reasons.append(f"age {age}")
    if beginner:
        short_cycle_reasons.append("a beginner training history")
    if thin_baseline:
        short_cycle_reasons.append("a thin training baseline")

    cycle = SHORT_RECOVERY_CYCLE_WEEKS if short_cycle_reasons else DEFAULT_RECOVERY_CYCLE_WEEKS
    if short_cycle_reasons:
        notes.append(
            f"Recovery week every {cycle} weeks instead of {DEFAULT_RECOVERY_CYCLE_WEEKS} "
            f"because of {short_cycle_reasons[0]}."
        )
    else:
        notes.append(
            f"Recovery week every {cycle} weeks — three loading weeks then one week to "
            "absorb the work."
        )

    if weeks_with_training >= 3 and source == "logged":
        confidence = "high"
    elif weeks_with_training >= 1 or longest:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "chronic_weekly_minutes": chronic_weekly_minutes,
        "chronic_weekly_km": chronic_weekly_km,
        "acwr": acwr,
        "weeks_with_training": weeks_with_training,
        "lookback_weeks": LOOKBACK_DAYS // 7,
        "longest_session_min": longest,
        "longest_session_source": source,
        "typical_session_minutes": typical,
        "long_session_ceiling_min": ceiling,
        "volume_damp": round(damp, 2),
        "recovery_cycle_weeks": cycle,
        "thin_baseline": thin_baseline,
        "active_injuries": active_injuries,
        "confidence": confidence,
        "notes": notes,
    }


def _longest_logged_minutes(
    db: Session, athlete_profile_id: int, *, window_start: datetime, window_end: datetime
) -> int | None:
    longest_s = (
        db.query(func.max(Activity.moving_time_s))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= window_start,
            Activity.activity_date <= window_end,
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
    )
    if not longest_s:
        return None
    return max(1, int(round(float(longest_s) / 60.0)))


def _weeks_with_training(
    db: Session, athlete_profile_id: int, *, window_start: datetime, window_end: datetime
) -> int:
    rows = (
        db.query(Activity.activity_date)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= window_start,
            Activity.activity_date <= window_end,
            Activity.canonical_activity_id.is_(None),
        )
        .all()
    )
    weeks = set()
    for (activity_date,) in rows:
        if activity_date is None:
            continue
        day = activity_date.date() if isinstance(activity_date, datetime) else activity_date
        weeks.add(day - timedelta(days=day.weekday()))
    return len(weeks)


def _active_injuries(db: Session, athlete_profile_id: int) -> tuple[list[str], bool]:
    rows = (
        db.query(AthleteInjury)
        .filter(
            AthleteInjury.athlete_profile_id == athlete_profile_id,
            AthleteInjury.status == "active",
        )
        .all()
    )
    labels = [
        row.body_region if not row.condition else f"{row.body_region} ({row.condition})"
        for row in rows
    ]
    severe = any((row.severity or "").strip().lower() == "severe" for row in rows)
    return labels, severe


def build_season_baseline(
    db: Session,
    profile: AthleteProfile,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Read the athlete's recent training and turn it into planning limits."""
    as_of = as_of or date.today()
    window_end = datetime.combine(as_of, time.max)
    window_start = datetime.combine(as_of - timedelta(days=LOOKBACK_DAYS), time.min)

    load = compute_acwr(db, profile.id)
    injuries, severe = _active_injuries(db, profile.id)

    return compose_season_baseline(
        fitness_level=profile.fitness_level,
        age=profile.age,
        typical_session_minutes=profile.workout_duration_minutes,
        longest_recent_session=profile.longest_recent_session,
        chronic_weekly_minutes=load.get("chronic_minutes"),
        chronic_weekly_km=load.get("chronic_km"),
        acwr=load.get("acwr"),
        longest_logged_minutes=_longest_logged_minutes(
            db, profile.id, window_start=window_start, window_end=window_end
        ),
        weeks_with_training=_weeks_with_training(
            db, profile.id, window_start=window_start, window_end=window_end
        ),
        active_injuries=injuries,
        has_severe_active_injury=severe,
    )


# ------------------------------------------------------------------ scaling
# These take the phase default rather than the phase type so this module never
# has to import the periodization engine that imports it.


def scale_long_session(default_min: int | float | None, baseline: dict | None) -> int:
    """Lower a phase's long-day allowance to what the athlete has earned."""
    default = int(default_min or MIN_LONG_SESSION_MIN)
    ceiling = (baseline or {}).get("long_session_ceiling_min")
    if not ceiling:
        return default
    # Never above the phase default, and never below the usable floor.
    return min(default, max(MIN_LONG_SESSION_MIN, int(ceiling)))


def scale_volume_bias(
    default_bias: float | None, baseline: dict | None, *, loading: bool = True
) -> float:
    """Damp loading-phase volume for injury or an already-spiking load."""
    bias = float(default_bias if default_bias is not None else 1.0)
    if not loading or not baseline:
        return round(bias, 2)
    damp = float(baseline.get("volume_damp") or 1.0)
    if damp >= 1.0:
        return round(bias, 2)
    return round(bias * damp, 2)


def is_loading_phase(phase_type: str | None) -> bool:
    return (phase_type or "") in LOADING_PHASES


def recovery_cycle_weeks(baseline: dict | None) -> int:
    cycle = (baseline or {}).get("recovery_cycle_weeks")
    try:
        cycle = int(cycle)
    except (TypeError, ValueError):
        return DEFAULT_RECOVERY_CYCLE_WEEKS
    return cycle if cycle >= 2 else DEFAULT_RECOVERY_CYCLE_WEEKS
