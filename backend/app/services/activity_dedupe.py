"""Cross-provider activity deduplication (Strava ↔ COROS).

Policy: keep one visible "canonical" row per real-world workout.
Prefer Strava as canonical (better streams); link the other row via
`canonical_activity_id` so lists/Schedule can hide duplicates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity

# Tight window when both sides have real start timestamps.
TIME_WINDOW = timedelta(minutes=15)
# Same calendar-day fallback when one side is date-only / midnight.
DAY_DURATION_TOLERANCE = 0.08  # 8%
DAY_DISTANCE_TOLERANCE = 0.05  # 5%
TIGHT_DURATION_TOLERANCE = 0.05
TIGHT_DISTANCE_TOLERANCE = 0.02


def _rel_close(a: float, b: float, tol: float) -> bool:
    """Return True only when both sides have real values within relative tolerance."""
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b, 1.0) <= tol


def _metrics_match(
    distance_a: float,
    duration_a: float,
    distance_b: float,
    duration_b: float,
    *,
    distance_tol: float,
    duration_tol: float,
) -> bool:
    """Require at least one comparable metric; zero/missing metrics never match alone."""
    distance_ok = _rel_close(distance_a, distance_b, distance_tol)
    duration_ok = _rel_close(duration_a, duration_b, duration_tol)
    has_distance = distance_a > 0 and distance_b > 0
    has_duration = duration_a > 0 and duration_b > 0
    if has_distance and has_duration:
        return distance_ok and duration_ok
    if has_distance:
        return distance_ok
    if has_duration:
        return duration_ok
    return False


def fingerprint_match(
    *,
    date_a: datetime,
    distance_a: float,
    duration_a: int,
    date_b: datetime,
    distance_b: float,
    duration_b: int,
) -> bool:
    """Return True when two activity fingerprints likely describe the same workout."""
    if date_a is None or date_b is None:
        return False

    # Normalize naive datetimes for comparison.
    da = date_a.replace(tzinfo=None) if date_a.tzinfo else date_a
    db_ = date_b.replace(tzinfo=None) if date_b.tzinfo else date_b

    delta = abs(da - db_)
    same_calendar_day = da.date() == db_.date()

    # Midnight (or near) on either side → treat as weak timestamp; use day + metrics.
    weak_time = (
        (da.hour == 0 and da.minute == 0 and da.second == 0)
        or (db_.hour == 0 and db_.minute == 0 and db_.second == 0)
    )

    if delta <= TIME_WINDOW and not weak_time:
        return _metrics_match(
            distance_a,
            float(duration_a),
            distance_b,
            float(duration_b),
            distance_tol=TIGHT_DISTANCE_TOLERANCE,
            duration_tol=TIGHT_DURATION_TOLERANCE,
        )

    if same_calendar_day or (weak_time and delta <= timedelta(hours=36)):
        return _metrics_match(
            distance_a,
            float(duration_a),
            distance_b,
            float(duration_b),
            distance_tol=DAY_DISTANCE_TOLERANCE,
            duration_tol=DAY_DURATION_TOLERANCE,
        )
    return False


def choose_canonical(a: Activity, b: Activity) -> tuple[Activity, Activity]:
    """Return (canonical, duplicate). Prefer Strava, then row with stream points."""
    if a.provider == "strava" and b.provider != "strava":
        return a, b
    if b.provider == "strava" and a.provider != "strava":
        return b, a
    if a.points_file_path and not b.points_file_path:
        return a, b
    if b.points_file_path and not a.points_file_path:
        return b, a
    # Stable: older id stays canonical.
    if a.id and b.id and a.id < b.id:
        return a, b
    return b, a


def link_duplicate(db: Session, canonical: Activity, duplicate: Activity) -> bool:
    """Point duplicate → canonical. Returns True if a change was made."""
    if canonical.id is None or duplicate.id is None:
        return False
    if canonical.id == duplicate.id:
        return False
    changed = False
    if duplicate.canonical_activity_id != canonical.id:
        duplicate.canonical_activity_id = canonical.id
        changed = True
    # Canonical must not point at anything (it is the visible row).
    if canonical.canonical_activity_id is not None:
        canonical.canonical_activity_id = None
        changed = True
    # Avoid chains: anything that pointed at duplicate should point at canonical.
    if changed:
        chained = (
            db.query(Activity)
            .filter(Activity.canonical_activity_id == duplicate.id)
            .all()
        )
        for row in chained:
            row.canonical_activity_id = canonical.id
    return changed


def find_cross_provider_match(
    db: Session,
    *,
    athlete_profile_id: int,
    activity_date: datetime,
    distance_m: float,
    moving_time_s: int,
    other_provider: str,
    exclude_id: int | None = None,
) -> Activity | None:
    """Find the best matching activity from the other provider."""
    if activity_date is None:
        return None
    day = activity_date.date() if hasattr(activity_date, "date") else activity_date
    window_start = datetime.combine(day, datetime.min.time()) - timedelta(days=1)
    window_end = datetime.combine(day, datetime.max.time().replace(microsecond=0)) + timedelta(
        days=1
    )

    query = db.query(Activity).filter(
        Activity.athlete_profile_id == athlete_profile_id,
        Activity.provider == other_provider,
        Activity.activity_date >= window_start,
        Activity.activity_date <= window_end,
    )
    if exclude_id is not None:
        query = query.filter(Activity.id != exclude_id)

    candidates = query.all()
    best: Activity | None = None
    best_delta: timedelta | None = None
    for candidate in candidates:
        if not fingerprint_match(
            date_a=activity_date,
            distance_a=float(distance_m or 0.0),
            duration_a=int(moving_time_s or 0),
            date_b=candidate.activity_date,
            distance_b=float(candidate.distance_m or 0.0),
            duration_b=int(candidate.moving_time_s or 0),
        ):
            continue
        delta = abs(
            (activity_date.replace(tzinfo=None) if activity_date.tzinfo else activity_date)
            - (
                candidate.activity_date.replace(tzinfo=None)
                if candidate.activity_date.tzinfo
                else candidate.activity_date
            )
        )
        if best is None or best_delta is None or delta < best_delta:
            best = candidate
            best_delta = delta
    return best


def link_new_activity_to_peer(db: Session, activity: Activity) -> Activity | None:
    """After inserting an activity, link it with a cross-provider peer if found.

    Returns the peer if linked, else None.
    """
    other = "coros" if activity.provider == "strava" else "strava"
    peer = find_cross_provider_match(
        db,
        athlete_profile_id=activity.athlete_profile_id,
        activity_date=activity.activity_date,
        distance_m=float(activity.distance_m or 0.0),
        moving_time_s=int(activity.moving_time_s or 0),
        other_provider=other,
        exclude_id=activity.id,
    )
    if peer is None:
        return None
    canonical, duplicate = choose_canonical(activity, peer)
    link_duplicate(db, canonical, duplicate)
    db.commit()
    return peer


def backfill_athlete_duplicates(db: Session, athlete_profile_id: int) -> dict[str, Any]:
    """Scan athlete activities and link unlinked Strava↔COROS pairs."""
    strava_rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == "strava",
        )
        .order_by(Activity.activity_date.asc())
        .all()
    )
    linked = 0
    scanned = 0
    for strava in strava_rows:
        scanned += 1
        # Find unmatched COROS peer (prefer unlinked COROS).
        peer = find_cross_provider_match(
            db,
            athlete_profile_id=athlete_profile_id,
            activity_date=strava.activity_date,
            distance_m=float(strava.distance_m or 0.0),
            moving_time_s=int(strava.moving_time_s or 0),
            other_provider="coros",
            exclude_id=strava.id,
        )
        if peer is None:
            continue
        # Skip if already correctly linked either way.
        if peer.canonical_activity_id == strava.id or strava.canonical_activity_id == peer.id:
            continue
        # If peer already linked to a different activity, skip (avoid stealing).
        if peer.canonical_activity_id is not None and peer.canonical_activity_id != strava.id:
            continue
        if strava.canonical_activity_id is not None and strava.canonical_activity_id != peer.id:
            continue

        canonical, duplicate = choose_canonical(strava, peer)
        if link_duplicate(db, canonical, duplicate):
            linked += 1

    if linked:
        db.commit()
    return {"scanned_strava": scanned, "linked": linked}
