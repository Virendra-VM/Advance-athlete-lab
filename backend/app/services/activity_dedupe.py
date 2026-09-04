"""Cross-provider activity deduplication (Strava ↔ COROS).

Policy: keep one visible "canonical" row per real-world workout.
Prefer Strava as canonical (better streams); link the other row via
`canonical_activity_id` so lists/Schedule can hide duplicates.

Failure modes this matcher handles
----------------------------------
1) UTC vs local start (e.g. COROS 13:31Z vs Strava 19:01 IST).
2) Outdoor twins with near-identical distance but different moving/elapsed time.
3) Indoor gym twins with *no GPS distance*: COROS labels them ``Strength`` while
   Strava uses ``WeightTraining``, and durations often differ ~25–40% (paused
   rest vs moving time). Those must match on sport-family + duration, not distance.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity

# Same-clock starts (after stripping tzinfo / comparing as naive clocks).
TIME_WINDOW = timedelta(minutes=25)
# How close a delta must be to a civil timezone offset to count as "skew".
# Keep tight: with a 30-minute tolerance, the 0.5h offset wrongly treated two
# gym sessions ~45 minutes apart as the same UTC↔local start.
TZ_SKEW_TOLERANCE = timedelta(minutes=12)
# Ignore tiny deltas here — those are handled by TIME_WINDOW, not "timezone".
TZ_SKEW_MIN = timedelta(hours=1)
# Civil timezone offsets commonly seen between UTC storage and local wall time.
# Omit 0.5h — it collides with back-to-back indoor sessions on the same evening.
_COMMON_TZ_OFFSET_HOURS = (
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
    5.5,  # India
    6.0,
    6.5,
    7.0,
    8.0,
    9.0,
    9.5,
    10.0,
    10.5,
    11.0,
    12.0,
    12.75,
    13.0,
    14.0,
)

# Distance is the strongest cross-provider signal for outdoor sports.
TIGHT_DISTANCE_TOLERANCE = 0.03  # 3%
DAY_DISTANCE_TOLERANCE = 0.06  # 6%
TIGHT_DURATION_TOLERANCE = 0.12  # 12%
LOOSE_DURATION_TOLERANCE = 0.45  # 45% — moving vs elapsed / gym rest pauses
# Indoor (no GPS): allow slightly looser duration when sport family matches.
INDOOR_DURATION_TOLERANCE = 0.50  # 50%

# Normalized sport families so COROS "Strength" ↔ Strava "WeightTraining".
_SPORT_FAMILIES: dict[str, set[str]] = {
    "strength": {
        "strength",
        "weighttraining",
        "weight_training",
        "workout",
        "traditionalstrengthtraining",
        "functionalstrengthtraining",
        "crossfit",
        "gym",
        "weightlifting",
    },
    "run": {"run", "trailrun", "virtualrun", "treadmill"},
    "ride": {"ride", "virtualride", "gravelride", "mountainbikeride", "ebikeride", "cycling"},
    "walk": {"walk", "hike", "hiking"},
    "swim": {"swim", "swimming", "openwaterswim"},
    "row": {"rowing", "virtualrow", "canoeing", "kayaking"},
    "yoga": {"yoga", "pilates", "stretching"},
}


def _naive(dt: datetime) -> datetime:
    if dt is None:
        raise ValueError("datetime required")
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _norm_sport(sport: str | None) -> str:
    if not sport:
        return ""
    return "".join(ch for ch in str(sport).lower() if ch.isalnum())


def sport_family(sport: str | None) -> str | None:
    """Return canonical family name, or None if unknown."""
    key = _norm_sport(sport)
    if not key:
        return None
    for family, members in _SPORT_FAMILIES.items():
        if key in members:
            return family
    return None


def sports_compatible(sport_a: str | None, sport_b: str | None) -> bool:
    """True when sports are the same family, or identical raw labels."""
    a = _norm_sport(sport_a)
    b = _norm_sport(sport_b)
    if not a or not b:
        # Missing sport: allow only when both missing (rare); otherwise require family.
        return not a and not b
    if a == b:
        return True
    fa = sport_family(sport_a)
    fb = sport_family(sport_b)
    return fa is not None and fa == fb


def _rel_close(a: float, b: float, tol: float) -> bool:
    """Return True only when both sides have real values within relative tolerance."""
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b, 1.0) <= tol


def _is_timezone_skew(delta: timedelta) -> bool:
    """True when |delta| is within tolerance of a common UTC↔local offset."""
    seconds = abs(delta.total_seconds())
    if seconds < TZ_SKEW_MIN.total_seconds():
        return False
    tol = TZ_SKEW_TOLERANCE.total_seconds()
    for hours in _COMMON_TZ_OFFSET_HOURS:
        if abs(seconds - hours * 3600.0) <= tol:
            return True
    return False


def _same_or_adjacent_calendar_day(da: datetime, db_: datetime) -> bool:
    return abs((da.date() - db_.date()).days) <= 1


def _metrics_support_match(
    distance_a: float,
    duration_a: float,
    distance_b: float,
    duration_b: float,
    *,
    mode: str,
    sports_ok: bool,
) -> bool:
    """Decide whether distance/duration/sport support a duplicate link.

    mode:
      - "aligned": starts already agree (tight clock or timezone-skew)
      - "same_day": weaker time signal; need stronger metrics
    """
    has_distance = distance_a > 0 and distance_b > 0
    has_duration = duration_a > 0 and duration_b > 0
    indoor = (distance_a <= 0) and (distance_b <= 0)
    distance_tight = has_distance and _rel_close(
        distance_a, distance_b, TIGHT_DISTANCE_TOLERANCE
    )
    distance_ok = has_distance and _rel_close(
        distance_a, distance_b, DAY_DISTANCE_TOLERANCE
    )
    duration_tight = has_duration and _rel_close(
        duration_a, duration_b, TIGHT_DURATION_TOLERANCE
    )
    duration_loose = has_duration and _rel_close(
        duration_a, duration_b, LOOSE_DURATION_TOLERANCE
    )
    duration_indoor = has_duration and _rel_close(
        duration_a, duration_b, INDOOR_DURATION_TOLERANCE
    )

    if mode == "aligned":
        # Same start (or UTC vs local of the same start): distance alone is enough
        # when nearly identical — duration often disagrees (moving vs elapsed).
        if distance_tight:
            return True
        if distance_ok and (duration_loose or not has_duration):
            return True
        if indoor and sports_ok and duration_indoor:
            return True
        if duration_tight and not has_distance and sports_ok:
            return True
        return False

    # same_day / weak time — outdoor needs distance; indoor must NOT match on
    # duration alone across a whole day (two gym sessions can share duration).
    if distance_tight and duration_loose:
        return True
    if distance_tight and not has_duration:
        return True
    if distance_ok and duration_tight:
        return True
    # Indoor gym: refuse same-day-only matches. Two Strength sessions on one
    # evening often have similar duration; without start alignment they are
    # different workouts. Aligned branch above still covers true twins.
    return False


def fingerprint_match(
    *,
    date_a: datetime,
    distance_a: float,
    duration_a: int,
    date_b: datetime,
    distance_b: float,
    duration_b: int,
    sport_a: str | None = None,
    sport_b: str | None = None,
) -> bool:
    """Return True when two activity fingerprints likely describe the same workout."""
    if date_a is None or date_b is None:
        return False

    da = _naive(date_a)
    db_ = _naive(date_b)
    delta = abs(da - db_)
    sports_ok = sports_compatible(sport_a, sport_b)

    # Outdoor twins can match without sport labels; indoor gym must agree on family.
    indoor = float(distance_a or 0.0) <= 0 and float(distance_b or 0.0) <= 0
    if indoor and not sports_ok:
        return False

    weak_time = (
        (da.hour == 0 and da.minute == 0 and da.second == 0)
        or (db_.hour == 0 and db_.minute == 0 and db_.second == 0)
    )

    aligned = (delta <= TIME_WINDOW and not weak_time) or _is_timezone_skew(delta)
    if aligned:
        return _metrics_support_match(
            float(distance_a or 0.0),
            float(duration_a or 0.0),
            float(distance_b or 0.0),
            float(duration_b or 0.0),
            mode="aligned",
            sports_ok=sports_ok,
        )

    if _same_or_adjacent_calendar_day(da, db_) or (
        weak_time and delta <= timedelta(hours=36)
    ):
        return _metrics_support_match(
            float(distance_a or 0.0),
            float(duration_a or 0.0),
            float(distance_b or 0.0),
            float(duration_b or 0.0),
            mode="same_day",
            sports_ok=sports_ok,
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
    # Prefer longer duration when both are indoor (more complete gym session).
    da = float(a.distance_m or 0.0)
    db = float(b.distance_m or 0.0)
    if da <= 0 and db <= 0:
        if int(a.moving_time_s or 0) > int(b.moving_time_s or 0):
            return a, b
        if int(b.moving_time_s or 0) > int(a.moving_time_s or 0):
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


def match_quality_score(
    *,
    date_a: datetime,
    distance_a: float,
    duration_a: int,
    date_b: datetime,
    distance_b: float,
    duration_b: int,
    sport_a: str | None = None,
    sport_b: str | None = None,
) -> tuple[float, float, float] | None:
    """Lower is better. Returns None when fingerprints do not match."""
    if not fingerprint_match(
        date_a=date_a,
        distance_a=distance_a,
        duration_a=duration_a,
        date_b=date_b,
        distance_b=distance_b,
        duration_b=duration_b,
        sport_a=sport_a,
        sport_b=sport_b,
    ):
        return None
    da = _naive(date_a)
    db_ = _naive(date_b)
    delta_s = abs((da - db_).total_seconds())
    dist_err = abs(float(distance_a or 0.0) - float(distance_b or 0.0))
    dur_err = abs(float(duration_a or 0.0) - float(duration_b or 0.0))
    align_penalty = delta_s
    if _is_timezone_skew(timedelta(seconds=delta_s)):
        align_penalty = 0.0
    elif delta_s <= TIME_WINDOW.total_seconds():
        align_penalty = 0.0
    return (align_penalty, dist_err, dur_err)


def find_cross_provider_match(
    db: Session,
    *,
    athlete_profile_id: int,
    activity_date: datetime,
    distance_m: float,
    moving_time_s: int,
    other_provider: str,
    sport_type: str | None = None,
    exclude_id: int | None = None,
    allow_already_linked: bool = False,
    for_activity_id: int | None = None,
) -> Activity | None:
    """Find the best matching activity from the other provider.

    By default skips candidates already linked to a *different* activity so a
    later Strava import cannot leave a COROS twin stuck on the wrong parent,
    and a same-day gym twin cannot steal another session's peer.
    """
    if activity_date is None:
        return None
    day = activity_date.date() if hasattr(activity_date, "date") else activity_date
    # Wide window: UTC vs local can land on adjacent calendar days near midnight.
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
    best_score: tuple[float, float, float] | None = None
    for candidate in candidates:
        # One COROS ↔ one Strava. Do not reuse a twin already claimed elsewhere
        # unless the caller explicitly allows reclaim scoring.
        if not allow_already_linked:
            linked_to = candidate.canonical_activity_id
            if linked_to is not None and for_activity_id is not None and linked_to != for_activity_id:
                continue
            if linked_to is not None and for_activity_id is None:
                # Candidate already owned by someone else.
                continue
            # If we are matching FROM a duplicate row, also skip when the
            # candidate (Strava) already has a different COROS twin that is a
            # better time-aligned owner — handled in reclaim path.

        if not fingerprint_match(
            date_a=activity_date,
            distance_a=float(distance_m or 0.0),
            duration_a=int(moving_time_s or 0),
            date_b=candidate.activity_date,
            distance_b=float(candidate.distance_m or 0.0),
            duration_b=int(candidate.moving_time_s or 0),
            sport_a=sport_type,
            sport_b=candidate.sport_type,
        ):
            continue
        score = match_quality_score(
            date_a=activity_date,
            distance_a=float(distance_m or 0.0),
            duration_a=int(moving_time_s or 0),
            date_b=candidate.activity_date,
            distance_b=float(candidate.distance_m or 0.0),
            duration_b=int(candidate.moving_time_s or 0),
            sport_a=sport_type,
            sport_b=candidate.sport_type,
        )
        if score is None:
            continue
        if best is None or best_score is None or score < best_score:
            best = candidate
            best_score = score
    return best


def _existing_owner_score(
    db: Session, owner: Activity, peer: Activity
) -> tuple[float, float, float] | None:
    return match_quality_score(
        date_a=owner.activity_date,
        distance_a=float(owner.distance_m or 0.0),
        duration_a=int(owner.moving_time_s or 0),
        date_b=peer.activity_date,
        distance_b=float(peer.distance_m or 0.0),
        duration_b=int(peer.moving_time_s or 0),
        sport_a=owner.sport_type,
        sport_b=peer.sport_type,
    )


def link_new_activity_to_peer(db: Session, activity: Activity) -> Activity | None:
    """After inserting an activity, link it with a cross-provider peer if found.

    Returns the peer if linked, else None.
    """
    other = "coros" if activity.provider == "strava" else "strava"
    # First try unclaimed peers only.
    peer = find_cross_provider_match(
        db,
        athlete_profile_id=activity.athlete_profile_id,
        activity_date=activity.activity_date,
        distance_m=float(activity.distance_m or 0.0),
        moving_time_s=int(activity.moving_time_s or 0),
        other_provider=other,
        sport_type=activity.sport_type,
        exclude_id=activity.id,
        allow_already_linked=False,
        for_activity_id=activity.id,
    )
    # Reclaim a wrongly linked peer when we are a clearly better match
    # (typically same start time vs a same-day duration collision).
    if peer is None:
        peer = find_cross_provider_match(
            db,
            athlete_profile_id=activity.athlete_profile_id,
            activity_date=activity.activity_date,
            distance_m=float(activity.distance_m or 0.0),
            moving_time_s=int(activity.moving_time_s or 0),
            other_provider=other,
            sport_type=activity.sport_type,
            exclude_id=activity.id,
            allow_already_linked=True,
            for_activity_id=activity.id,
        )
        if peer is not None and peer.canonical_activity_id not in (None, activity.id):
            owner = (
                db.query(Activity)
                .filter(Activity.id == peer.canonical_activity_id)
                .first()
            )
            my_score = match_quality_score(
                date_a=activity.activity_date,
                distance_a=float(activity.distance_m or 0.0),
                duration_a=int(activity.moving_time_s or 0),
                date_b=peer.activity_date,
                distance_b=float(peer.distance_m or 0.0),
                duration_b=int(peer.moving_time_s or 0),
                sport_a=activity.sport_type,
                sport_b=peer.sport_type,
            )
            owner_score = _existing_owner_score(db, owner, peer) if owner else None
            if my_score is None or (owner_score is not None and not (my_score < owner_score)):
                return None
    if peer is None:
        return None
    canonical, duplicate = choose_canonical(activity, peer)
    link_duplicate(db, canonical, duplicate)
    db.commit()
    return peer


def backfill_athlete_duplicates(db: Session, athlete_profile_id: int) -> dict[str, Any]:
    """Scan athlete activities and link unlinked Strava↔COROS pairs.

    Prefer matching longer Strava sessions first so a short WeightTraining
    fragment does not steal the COROS Strength twin from the real gym workout.
    Also reclaim peers that were wrongly linked to a worse Strava parent.
    """
    strava_rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == "strava",
        )
        .order_by(Activity.moving_time_s.desc().nullslast(), Activity.activity_date.asc())
        .all()
    )
    linked = 0
    reclaimed = 0
    scanned = 0
    for strava in strava_rows:
        scanned += 1
        # Prefer an unclaimed COROS twin.
        peer = find_cross_provider_match(
            db,
            athlete_profile_id=athlete_profile_id,
            activity_date=strava.activity_date,
            distance_m=float(strava.distance_m or 0.0),
            moving_time_s=int(strava.moving_time_s or 0),
            other_provider="coros",
            sport_type=strava.sport_type,
            exclude_id=strava.id,
            allow_already_linked=False,
            for_activity_id=strava.id,
        )
        reclaim = False
        if peer is None:
            peer = find_cross_provider_match(
                db,
                athlete_profile_id=athlete_profile_id,
                activity_date=strava.activity_date,
                distance_m=float(strava.distance_m or 0.0),
                moving_time_s=int(strava.moving_time_s or 0),
                other_provider="coros",
                sport_type=strava.sport_type,
                exclude_id=strava.id,
                allow_already_linked=True,
                for_activity_id=strava.id,
            )
            if peer is not None and peer.canonical_activity_id not in (None, strava.id):
                owner = (
                    db.query(Activity)
                    .filter(Activity.id == peer.canonical_activity_id)
                    .first()
                )
                my_score = match_quality_score(
                    date_a=strava.activity_date,
                    distance_a=float(strava.distance_m or 0.0),
                    duration_a=int(strava.moving_time_s or 0),
                    date_b=peer.activity_date,
                    distance_b=float(peer.distance_m or 0.0),
                    duration_b=int(peer.moving_time_s or 0),
                    sport_a=strava.sport_type,
                    sport_b=peer.sport_type,
                )
                owner_score = _existing_owner_score(db, owner, peer) if owner else None
                if my_score is None or (
                    owner_score is not None and not (my_score < owner_score)
                ):
                    continue
                reclaim = True
        if peer is None:
            continue
        # Skip if already correctly linked either way.
        if peer.canonical_activity_id == strava.id or strava.canonical_activity_id == peer.id:
            continue
        if strava.canonical_activity_id is not None and strava.canonical_activity_id != peer.id:
            continue

        canonical, duplicate = choose_canonical(strava, peer)
        if link_duplicate(db, canonical, duplicate):
            linked += 1
            if reclaim:
                reclaimed += 1

    if linked:
        db.commit()
    return {"scanned_strava": scanned, "linked": linked, "reclaimed": reclaimed}
