from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Activity, StravaConnection
from app.services.strava_api import (
    StravaApiError,
    download_activity_fit,
    get_activity,
    get_valid_access_token,
    list_athlete_activities,
)
from app.services.strava_import import import_single_fit_file

sync_status: dict = {
    "running": False,
    "total": 0,
    "processed": 0,
    "imported": 0,
    "skipped": 0,
    "errors": [],
}


def get_sync_status() -> dict:
    return dict(sync_status)


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
    return (
        db.query(Activity.id)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.strava_activity_id == strava_activity_id,
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

    imported = import_activity_summary(db, athlete_profile_id, activity)
    return "imported" if imported else "skipped"


def sync_activities_for_athlete(
    db: Session,
    athlete_profile_id: int,
    *,
    max_pages: int = 5,
    per_page: int = 50,
) -> dict:
    connection = get_connection_for_athlete(db, athlete_profile_id)
    if connection is None:
        raise StravaApiError("No Strava connection found for this athlete profile.")

    if connection.athlete_profile_id is None:
        connection.athlete_profile_id = athlete_profile_id
        db.commit()
        db.refresh(connection)

    sync_status.update(
        {
            "running": True,
            "total": 0,
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [],
        }
    )

    imported = 0
    skipped = 0
    errors: list[str] = []

    try:
        access_token = get_valid_access_token(connection, db)
        all_activities: list[dict] = []

        for page in range(1, max_pages + 1):
            page_rows = list_athlete_activities(
                access_token,
                page=page,
                per_page=per_page,
            )
            if not page_rows:
                break
            all_activities.extend(page_rows)
            if len(page_rows) < per_page:
                break

        sync_status["total"] = len(all_activities)

        for activity in all_activities:
            sync_status["processed"] += 1
            strava_activity_id = int(activity["id"])
            try:
                if _activity_exists(db, athlete_profile_id, strava_activity_id):
                    skipped += 1
                    sync_status["skipped"] = skipped
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

                if result:
                    imported += 1
                    sync_status["imported"] = imported
                else:
                    skipped += 1
                    sync_status["skipped"] = skipped
            except Exception as exc:
                db.rollback()
                message = f"Activity {strava_activity_id}: {exc}"
                errors.append(message)
                sync_status["errors"].append(message)

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total_fetched": len(all_activities),
        }
    finally:
        sync_status["running"] = False


def sync_activities_in_background(athlete_profile_id: int) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        sync_activities_for_athlete(db, athlete_profile_id)
    except Exception as exc:
        sync_status["errors"].append(str(exc))
        sync_status["running"] = False
    finally:
        db.close()


def sync_single_activity_in_background(
    strava_athlete_id: int,
    strava_activity_id: int,
) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        connection = (
            db.query(StravaConnection)
            .filter(StravaConnection.strava_athlete_id == strava_athlete_id)
            .order_by(StravaConnection.id.desc())
            .first()
        )
        if connection is None or connection.athlete_profile_id is None:
            return
        sync_single_activity(db, connection, strava_activity_id)
    except Exception as exc:
        sync_status["errors"].append(str(exc))
    finally:
        db.close()
