from __future__ import annotations

import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sqlalchemy.orm import Session

from app.models import Activity, StravaConnection
from app.services.strava_api import (
    StravaApiError,
    download_activity_fit,
    fetch_activity_streams,
    get_activity,
    get_valid_access_token,
    list_athlete_activities,
)
from app.services.strava_import import import_single_fit_file

# Per-athlete sync status (avoids one global lock across athletes)
_DEFAULT_STATUS: dict[str, Any] = {
    "running": False,
    "total": 0,
    "processed": 0,
    "imported": 0,
    "skipped": 0,
    "errors": [],
}
_sync_status: dict[int, dict[str, Any]] = {}
_status_lock = threading.Lock()


def get_sync_status(athlete_profile_id: int) -> dict[str, Any]:
    status = _sync_status.get(athlete_profile_id, _DEFAULT_STATUS)
    return {
        "running": bool(status.get("running")),
        "total": int(status.get("total") or 0),
        "processed": int(status.get("processed") or 0),
        "imported": int(status.get("imported") or 0),
        "skipped": int(status.get("skipped") or 0),
        "errors": list(status.get("errors") or []),
    }


def _set_status(athlete_profile_id: int, **kwargs: Any) -> None:
    status = get_sync_status(athlete_profile_id)
    status.update(kwargs)
    _sync_status[athlete_profile_id] = status


def is_sync_running(athlete_profile_id: int) -> bool:
    return bool(get_sync_status(athlete_profile_id).get("running"))


def _claim_sync(athlete_profile_id: int) -> bool:
    """Claim the per-athlete sync slot. Returns False if already running."""
    with _status_lock:
        if get_sync_status(athlete_profile_id).get("running"):
            return False
        _set_status(
            athlete_profile_id,
            running=True,
            total=0,
            processed=0,
            imported=0,
            skipped=0,
            errors=[],
        )
        return True


def try_start_strava_sync(
    db: Session,
    athlete_profile_id: int,
    *,
    inline: bool = False,
) -> dict[str, Any]:
    """Start Strava sync for an athlete if one is not already running.

    inline=True runs sync in the current thread (used after COROS sync).
    inline=False only reports whether a background sync may be queued;
    the caller should schedule ``sync_activities_in_background``.
    """
    if is_sync_running(athlete_profile_id):
        return {
            "started": False,
            "skipped": True,
            "reason": "already_running",
            "result": None,
        }

    if get_connection_for_athlete(db, athlete_profile_id) is None:
        return {
            "started": False,
            "skipped": True,
            "reason": "no_connection",
            "result": None,
        }

    if not inline:
        return {
            "started": True,
            "skipped": False,
            "reason": None,
            "result": None,
        }

    result = sync_activities_for_athlete(db, athlete_profile_id)
    if result.get("already_running"):
        return {
            "started": False,
            "skipped": True,
            "reason": "already_running",
            "result": result,
        }
    return {
        "started": True,
        "skipped": False,
        "reason": None,
        "result": result,
    }


def get_connection_for_athlete(
    db: Session, athlete_profile_id: int
) -> StravaConnection | None:
    connection = (
        db.query(StravaConnection)
        .filter(StravaConnection.athlete_profile_id == athlete_profile_id)
        .order_by(StravaConnection.id.desc())
        .first()
    )
    if connection is not None:
        return connection

    orphan = (
        db.query(StravaConnection)
        .filter(StravaConnection.athlete_profile_id.is_(None))
        .order_by(StravaConnection.id.desc())
        .first()
    )
    if orphan is None:
        return None

    orphan.athlete_profile_id = athlete_profile_id
    db.commit()
    db.refresh(orphan)
    return orphan


def api_activity_to_metadata(activity: dict) -> dict:
    start_date = activity.get("start_date_local") or activity.get("start_date")
    activity_date = None
    if start_date:
        parsed = datetime.fromisoformat(str(start_date).replace("Z", "+00:00"))
        activity_date = parsed.replace(tzinfo=None)

    sport_type = activity.get("sport_type") or activity.get("type")

    return {
        "name": activity.get("name"),
        "activity_date": activity_date,
        "distance_m": float(activity.get("distance") or 0.0),
        "moving_time_s": int(activity.get("moving_time") or 0),
        "average_heartrate": activity.get("average_heartrate"),
        "max_heartrate": activity.get("max_heartrate"),
        "sport_type": sport_type,
    }


def _activity_exists(
    db: Session, athlete_profile_id: int, strava_activity_id: int
) -> bool:
    external_id = str(strava_activity_id)
    return (
        db.query(Activity.id)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == "strava",
            Activity.external_activity_id == external_id,
        )
        .first()
        is not None
    )


def import_activity_summary(
    db: Session,
    athlete_profile_id: int,
    activity: dict,
) -> Activity | None:
    strava_activity_id = int(activity["id"])
    if _activity_exists(db, athlete_profile_id, strava_activity_id):
        return None

    metadata = api_activity_to_metadata(activity)
    if metadata["activity_date"] is None:
        metadata["activity_date"] = datetime.utcnow()

    record = Activity(
        athlete_profile_id=athlete_profile_id,
        provider="strava",
        external_activity_id=str(strava_activity_id),
        strava_activity_id=strava_activity_id,
        name=metadata["name"] or f"Activity {strava_activity_id}",
        activity_date=metadata["activity_date"],
        distance_m=float(metadata["distance_m"] or 0.0),
        moving_time_s=int(metadata["moving_time_s"] or 0),
        average_heartrate=metadata["average_heartrate"],
        max_heartrate=metadata["max_heartrate"],
        sport_type=metadata["sport_type"],
        points_file_path=None,
        source_fit_file=f"strava_api:{strava_activity_id}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    from app.services.activity_dedupe import link_new_activity_to_peer

    link_new_activity_to_peer(db, record)
    db.refresh(record)
    return record


def import_activity_with_fit(
    db: Session,
    athlete_profile_id: int,
    strava_activity_id: int,
    fit_bytes: bytes,
    api_metadata: dict | None = None,
) -> Activity | None:
    if _activity_exists(db, athlete_profile_id, strava_activity_id):
        return None

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(fit_bytes)
        fit_path = Path(tmp.name)

    try:
        return import_single_fit_file(
            db,
            athlete_profile_id,
            fit_path,
            strava_activity_id,
            csv_metadata=api_metadata,
            source_fit_file=f"strava_api:{strava_activity_id}.fit",
        )
    finally:
        fit_path.unlink(missing_ok=True)


def build_points_from_streams(
    streams: dict,
    athlete_profile_id: int,
    strava_activity_id: int,
    activity_date: datetime | None = None,
) -> str | None:
    """Convert Strava streams dict to a parquet file and return its relative path."""
    from app.config import ACTIVITY_POINTS_DIR
    from app.services.strava_import import write_points_parquet

    time_data = streams.get("time", [])
    if not time_data:
        return None

    n = len(time_data)
    base_ts = pd.Timestamp(activity_date) if activity_date else pd.Timestamp.utcnow()
    timestamps = [base_ts + pd.Timedelta(seconds=int(t)) for t in time_data]

    df = pd.DataFrame({"timestamp": timestamps})

    distance_data = streams.get("distance", [])
    if len(distance_data) == n:
        df["distance_m"] = [float(d) for d in distance_data]

    speed_data = streams.get("velocity_smooth", [])
    if len(speed_data) == n:
        df["speed"] = [float(s) for s in speed_data]

    hr_data = streams.get("heartrate", [])
    if len(hr_data) == n:
        df["heart_rate"] = [float(h) if h is not None else None for h in hr_data]

    altitude_data = streams.get("altitude", [])
    if len(altitude_data) == n:
        df["altitude"] = [float(a) for a in altitude_data]

    cadence_data = streams.get("cadence", [])
    if len(cadence_data) == n:
        df["cadence"] = [float(c) for c in cadence_data]

    watts_data = streams.get("watts", [])
    if len(watts_data) == n:
        df["power"] = [float(w) for w in watts_data]

    points_root = Path(ACTIVITY_POINTS_DIR).expanduser().resolve()
    points_root.mkdir(parents=True, exist_ok=True)
    return write_points_parquet(df, athlete_profile_id, strava_activity_id, points_root)


def backfill_streams_for_athlete(
    db: Session,
    athlete_profile_id: int,
) -> dict:
    """Fetch Strava streams for API-imported activities that have no point data and save parquet files."""
    connection = get_connection_for_athlete(db, athlete_profile_id)
    if connection is None:
        raise StravaApiError("No Strava connection found for this athlete profile.")

    access_token = get_valid_access_token(connection, db)

    api_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.points_file_path.is_(None),
            Activity.source_fit_file.like("strava_api:%"),
        )
        .order_by(Activity.activity_date.desc())
        .all()
    )

    backfilled = 0
    skipped = 0
    errors = []

    for activity in api_activities:
        try:
            streams = fetch_activity_streams(access_token, activity.strava_activity_id)
            if not streams or not streams.get("time"):
                skipped += 1
                continue

            points_file_path = build_points_from_streams(
                streams,
                athlete_profile_id,
                activity.strava_activity_id,
                activity_date=activity.activity_date,
            )
            if points_file_path:
                activity.points_file_path = points_file_path
                db.commit()
                backfilled += 1
            else:
                skipped += 1
        except Exception as exc:
            db.rollback()
            errors.append(f"Activity {activity.strava_activity_id}: {exc}")

    return {"backfilled": backfilled, "skipped": skipped, "errors": errors}


def sync_single_activity(
    db: Session,
    connection: StravaConnection,
    strava_activity_id: int,
    *,
    access_token: str | None = None,
) -> str:
    athlete_profile_id = connection.athlete_profile_id
    if athlete_profile_id is None:
        raise StravaApiError("Strava connection is not linked to an athlete profile.")

    if _activity_exists(db, athlete_profile_id, strava_activity_id):
        return "skipped"

    token = access_token or get_valid_access_token(connection, db)
    activity = get_activity(token, strava_activity_id)
    api_metadata = api_activity_to_metadata(activity)

    fit_bytes = download_activity_fit(token, strava_activity_id)
    if fit_bytes:
        imported = import_activity_with_fit(
            db,
            athlete_profile_id,
            strava_activity_id,
            fit_bytes,
            api_metadata=api_metadata,
        )
        if imported:
            return "imported"
        return "skipped"

    # FIT not available — import summary first, then attach streams point data.
    imported_activity = import_activity_summary(db, athlete_profile_id, activity)
    if imported_activity:
        streams = fetch_activity_streams(token, strava_activity_id)
        if streams and streams.get("time"):
            points_file_path = build_points_from_streams(
                streams,
                athlete_profile_id,
                strava_activity_id,
                activity_date=imported_activity.activity_date,
            )
            if points_file_path:
                imported_activity.points_file_path = points_file_path
                db.commit()
        return "imported"
    return "skipped"


def _latest_activity_after_epoch(db: Session, athlete_profile_id: int) -> int | None:
    """Unix timestamp of the newest *Strava* activity for incremental Strava sync.

    Important: do not use COROS (or other provider) timestamps here. COROS often
    imports the same workout first; if we set `after` to that time, Strava's API
    excludes the twin activity (same start time) and it never lands in the app.
    """
    from datetime import timezone

    latest = (
        db.query(Activity.activity_date)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == "strava",
        )
        .order_by(Activity.activity_date.desc())
        .first()
    )
    if latest is None or latest[0] is None:
        return None
    activity_date = latest[0]
    if activity_date.tzinfo is None:
        activity_date = activity_date.replace(tzinfo=timezone.utc)
    # Small lookback so delayed Strava uploads / clock skew still get pulled.
    return max(0, int(activity_date.timestamp()) - 3600)


def sync_activities_for_athlete(
    db: Session,
    athlete_profile_id: int,
    *,
    max_pages: int = 40,
    per_page: int = 50,
) -> dict:
    connection = get_connection_for_athlete(db, athlete_profile_id)
    if connection is None:
        raise StravaApiError("No Strava connection found for this athlete profile.")

    if connection.athlete_profile_id is None:
        connection.athlete_profile_id = athlete_profile_id
        db.commit()
        db.refresh(connection)

    # Do not reset progress / status if another sync is already in flight.
    if not _claim_sync(athlete_profile_id):
        return {
            "imported": 0,
            "skipped": 0,
            "errors": [],
            "total_fetched": 0,
            "deduped": 0,
            "schedule_completed": 0,
            "already_running": True,
        }

    imported = 0
    skipped = 0
    errors: list[str] = []

    try:
        access_token = get_valid_access_token(connection, db)
        after = _latest_activity_after_epoch(db, athlete_profile_id)
        # Incremental sync only needs recent pages; full sync may need more.
        page_limit = max_pages if after is None else min(max_pages, 10)
        all_activities: list[dict] = []

        for page in range(1, page_limit + 1):
            page_rows = list_athlete_activities(
                access_token,
                page=page,
                per_page=per_page,
                after=after,
            )
            if not page_rows:
                break
            all_activities.extend(page_rows)
            if len(page_rows) < per_page:
                break

        _set_status(athlete_profile_id, total=len(all_activities))

        for activity in all_activities:
            processed = get_sync_status(athlete_profile_id)["processed"] + 1
            _set_status(athlete_profile_id, processed=processed)
            strava_activity_id = int(activity["id"])
            try:
                if _activity_exists(db, athlete_profile_id, strava_activity_id):
                    existing = (
                        db.query(Activity)
                        .filter(
                            Activity.athlete_profile_id == athlete_profile_id,
                            Activity.provider == "strava",
                            Activity.external_activity_id == str(strava_activity_id),
                        )
                        .first()
                    )
                    if existing is not None:
                        from app.services.activity_dedupe import link_new_activity_to_peer

                        # Link any unlinked COROS peer (idempotent if already linked).
                        if existing.canonical_activity_id is None:
                            link_new_activity_to_peer(db, existing)
                    skipped += 1
                    _set_status(athlete_profile_id, skipped=skipped)
                    continue

                api_metadata = api_activity_to_metadata(activity)
                fit_bytes = download_activity_fit(access_token, strava_activity_id)
                if fit_bytes:
                    result = import_activity_with_fit(
                        db,
                        athlete_profile_id,
                        strava_activity_id,
                        fit_bytes,
                        api_metadata=api_metadata,
                    )
                else:
                    result = import_activity_summary(db, athlete_profile_id, activity)
                    # FIT unavailable — attach streams point data immediately.
                    if result:
                        streams = fetch_activity_streams(access_token, strava_activity_id)
                        if streams and streams.get("time"):
                            points_file_path = build_points_from_streams(
                                streams,
                                athlete_profile_id,
                                strava_activity_id,
                                activity_date=result.activity_date,
                            )
                            if points_file_path:
                                result.points_file_path = points_file_path
                                db.commit()

                if result:
                    imported += 1
                    _set_status(athlete_profile_id, imported=imported)
                else:
                    skipped += 1
                    _set_status(athlete_profile_id, skipped=skipped)
            except Exception as exc:
                db.rollback()
                message = f"Activity {strava_activity_id}: {exc}"
                errors.append(message)
                _set_status(athlete_profile_id, errors=list(errors))

        from app.services.activity_dedupe import backfill_athlete_duplicates
        from app.services.schedule_completion import match_schedule_completions

        dedupe = backfill_athlete_duplicates(db, athlete_profile_id)
        schedule_links = match_schedule_completions(db, athlete_profile_id)

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total_fetched": len(all_activities),
            "deduped": dedupe.get("linked", 0),
            "schedule_completed": schedule_links.get("linked", 0),
        }
    finally:
        _set_status(athlete_profile_id, running=False)


def sync_activities_in_background(athlete_profile_id: int) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        sync_activities_for_athlete(db, athlete_profile_id)
    except Exception as exc:
        status = get_sync_status(athlete_profile_id)
        errors = list(status.get("errors") or [])
        errors.append(str(exc))
        _set_status(athlete_profile_id, running=False, errors=errors[-20:])
    finally:
        db.close()


def sync_single_activity_in_background(
    strava_athlete_id: int,
    strava_activity_id: int,
) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    athlete_profile_id: int | None = None
    try:
        connection = (
            db.query(StravaConnection)
            .filter(StravaConnection.strava_athlete_id == strava_athlete_id)
            .order_by(StravaConnection.id.desc())
            .first()
        )
        if connection is None or connection.athlete_profile_id is None:
            return
        athlete_profile_id = connection.athlete_profile_id
        sync_single_activity(db, connection, strava_activity_id)
    except Exception as exc:
        if athlete_profile_id is not None:
            status = get_sync_status(athlete_profile_id)
            errors = list(status.get("errors") or [])
            errors.append(str(exc))
            _set_status(athlete_profile_id, errors=errors[-20:])
    finally:
        db.close()
