"""Match COROS planned workouts to completed activities."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity, CorosScheduleItem

DURATION_TOLERANCE = 0.25  # planned estimates can be rough
DISTANCE_TOLERANCE = 0.25
SPORT_ALIASES = {
    "run": {"run", "running", "trail run", "trail running", "treadmill", "virtual run"},
    "ride": {"ride", "cycling", "bike", "biking", "virtual ride", "gravel", "mtb", "mountain bike"},
    "swim": {"swim", "swimming", "open water", "pool swim"},
    "walk": {"walk", "walking", "hike", "hiking"},
    "weight": {"weight", "weight training", "strength", "gym", "workout"},
    "yoga": {"yoga", "pilates", "flexibility"},
}


def _norm_sport(value: str | None) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    return text


def sports_compatible(plan_sport: str | None, activity_sport: str | None) -> bool:
    """Soft sport match — unknown sports are allowed so we don't miss completions."""
    a = _norm_sport(plan_sport)
    b = _norm_sport(activity_sport)
    if not a or not b:
        return True
    if a == b or a in b or b in a:
        return True
    for aliases in SPORT_ALIASES.values():
        if a in aliases and b in aliases:
            return True
        # partial token overlap against alias set
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        for alias in aliases:
            alias_tokens = set(alias.split())
            if a_tokens & alias_tokens and b_tokens & alias_tokens:
                return True
    return False


def _rel_close(a: float | None, b: float | None, tol: float) -> bool | None:
    """None = skip (insufficient data), True/False = hard result."""
    if a is None or b is None:
        return None
    if a <= 0 or b <= 0:
        return None
    return abs(float(a) - float(b)) / max(float(a), float(b), 1.0) <= tol


def plan_activity_score(plan: CorosScheduleItem, activity: Activity) -> float:
    """Higher is better. <=0 means not a match."""
    plan_day = plan.schedule_date
    act_day = activity.activity_date.date() if isinstance(activity.activity_date, datetime) else activity.activity_date
    if plan_day != act_day:
        # Allow ±1 day for late-night / timezone bleed.
        if abs((plan_day - act_day).days) > 1:
            return -1.0

    if not sports_compatible(plan.sport_type, activity.sport_type):
        # Title/name fallback for sports that don't map cleanly.
        title = (plan.title or "").lower()
        name = (activity.name or "").lower()
        sport = (activity.sport_type or "").lower()
        if title and title not in name and title not in sport:
            return -1.0

    score = 1.0
    if plan_day == act_day:
        score += 2.0
    else:
        score += 0.5

    # Duration: plan minutes vs activity seconds
    plan_duration_s = (plan.duration_min * 60.0) if plan.duration_min else None
    duration_ok = _rel_close(plan_duration_s, float(activity.moving_time_s or 0) or None, DURATION_TOLERANCE)
    if duration_ok is True:
        score += 2.0
    elif duration_ok is False:
        score -= 1.5

    distance_ok = _rel_close(plan.distance_m, float(activity.distance_m or 0) or None, DISTANCE_TOLERANCE)
    if distance_ok is True:
        score += 2.0
    elif distance_ok is False:
        score -= 1.5

    # Title overlap bonus
    title = (plan.title or "").strip().lower()
    name = (activity.name or "").strip().lower()
    if title and name and (title in name or name in title):
        score += 1.5

    # Prefer same-day + any metric agreement
    if score < 1.5:
        return -1.0
    return score


def match_schedule_completions(
    db: Session,
    athlete_profile_id: int,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    """Link open schedule plans to canonical completed activities."""
    start = from_date or (date.today() - timedelta(days=120))
    end = to_date or (date.today() + timedelta(days=7))

    plans = (
        db.query(CorosScheduleItem)
        .filter(
            CorosScheduleItem.athlete_profile_id == athlete_profile_id,
            CorosScheduleItem.schedule_date >= start,
            CorosScheduleItem.schedule_date <= end,
        )
        .order_by(CorosScheduleItem.schedule_date.asc())
        .all()
    )
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.canonical_activity_id.is_(None),
            Activity.activity_date
            >= datetime.combine(start - timedelta(days=1), datetime.min.time()),
            Activity.activity_date
            <= datetime.combine(end + timedelta(days=1), datetime.max.time().replace(microsecond=0)),
        )
        .order_by(Activity.activity_date.asc())
        .all()
    )

    used_activity_ids = {
        plan.completed_activity_id
        for plan in plans
        if plan.completed_activity_id is not None
    }
    linked = 0
    cleared = 0

    # Drop stale links if the activity was deleted / became a duplicate.
    activity_by_id = {a.id: a for a in activities}
    # Also load linked activities outside the filtered set for validation
    for plan in plans:
        if plan.completed_activity_id is None:
            continue
        linked_row = activity_by_id.get(plan.completed_activity_id)
        if linked_row is None:
            linked_row = (
                db.query(Activity)
                .filter(
                    Activity.id == plan.completed_activity_id,
                    Activity.athlete_profile_id == athlete_profile_id,
                    Activity.canonical_activity_id.is_(None),
                )
                .first()
            )
        if linked_row is None:
            plan.completed_activity_id = None
            cleared += 1

    open_plans = [p for p in plans if p.completed_activity_id is None]
    available = [a for a in activities if a.id not in used_activity_ids]

    # Greedy best-score matching per day group
    pairs: list[tuple[float, CorosScheduleItem, Activity]] = []
    for plan in open_plans:
        for activity in available:
            score = plan_activity_score(plan, activity)
            if score > 0:
                pairs.append((score, plan, activity))
    pairs.sort(key=lambda item: item[0], reverse=True)

    claimed_plans: set[int] = set()
    claimed_activities: set[int] = set()
    for score, plan, activity in pairs:
        if plan.id in claimed_plans or activity.id in claimed_activities:
            continue
        if plan.completed_activity_id is not None:
            continue
        plan.completed_activity_id = activity.id
        claimed_plans.add(plan.id)
        claimed_activities.add(activity.id)
        used_activity_ids.add(activity.id)
        linked += 1

    if linked or cleared:
        db.commit()

    return {
        "scanned_plans": len(plans),
        "linked": linked,
        "cleared": cleared,
    }
