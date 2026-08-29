"""Download COROS FIT files and attach timeline streams (HR/power/etc.)."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import ACTIVITY_POINTS_DIR, COROS_FIT_DAILY_LIMIT, COROS_FIT_RECENT_LIMIT
from app.models import Activity, ProviderConnection
from app.services.coros_mcp import CorosMcpClient, CorosMcpError
from app.services.strava_import import (
    _fit_file_to_dataframes,
    extract_lap_summary,
    normalize_point_dataframe,
    write_points_parquet,
)

PROVIDER = "coros"
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def _parse_json_maybe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def extract_fit_url(payload: Any) -> str | None:
    """Best-effort extract of a FIT download URL from MCP tool responses."""
    data = _parse_json_maybe(payload)

    def from_dict(item: dict[str, Any]) -> str | None:
        for key in (
            "url",
            "downloadUrl",
            "download_url",
            "fitUrl",
            "fit_url",
            "fileUrl",
            "file_url",
        ):
            value = item.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        for nested_key in ("data", "result", "file", "files"):
            nested = item.get(nested_key)
            found = extract_fit_url(nested)
            if found:
                return found
        return None

    if isinstance(data, dict):
        found = from_dict(data)
        if found:
            return found
        for value in data.values():
            found = extract_fit_url(value)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = extract_fit_url(item)
            if found:
                return found
    if isinstance(data, str):
        if data.startswith("http"):
            return data.split()[0].rstrip("),]};\"'")
        match = URL_RE.search(data)
        if match:
            return match.group(0).rstrip("),]};\"'")
    return None


def _reset_daily_quota_if_needed(connection: ProviderConnection) -> None:
    today = date.today()
    if connection.fit_downloads_day != today:
        connection.fit_downloads_today = 0
        connection.fit_downloads_day = today


def remaining_fit_quota(connection: ProviderConnection) -> int:
    _reset_daily_quota_if_needed(connection)
    return max(0, COROS_FIT_DAILY_LIMIT - int(connection.fit_downloads_today or 0))


def resolve_coros_fit_source(
    db: Session, activity: Activity
) -> tuple[Activity, str] | None:
    """Return (target_activity_to_receive_points, coros_external_id) or None."""
    if activity.provider == PROVIDER:
        target = activity
        if activity.canonical_activity_id:
            parent = (
                db.query(Activity)
                .filter(Activity.id == activity.canonical_activity_id)
                .first()
            )
            if parent is not None:
                target = parent
        return target, str(activity.external_activity_id)

    if activity.provider == "strava":
        twin = (
            db.query(Activity)
            .filter(
                Activity.athlete_profile_id == activity.athlete_profile_id,
                Activity.provider == PROVIDER,
                Activity.canonical_activity_id == activity.id,
            )
            .order_by(Activity.id.desc())
            .first()
        )
        if twin is None:
            return None
        return activity, str(twin.external_activity_id)

    return None


def fetch_coros_fit_url(client: CorosMcpClient, coros_external_id: str) -> str | None:
    payloads: list[Any] = []
    for tool, args in (
        (
            "queryActivityFitFileDownloadUrls",
            {"activityIds": [coros_external_id], "activityId": coros_external_id},
        ),
        (
            "downloadActivityFitFiles",
            {"activityIds": [coros_external_id], "activityId": coros_external_id},
        ),
    ):
        try:
            payloads.append(client.call_tool(tool, args))
        except CorosMcpError:
            continue
    for payload in payloads:
        url = extract_fit_url(payload)
        if url:
            return url
    return None


def download_fit_bytes(fit_url: str) -> bytes:
    import httpx

    with httpx.Client(timeout=90.0, follow_redirects=True) as http:
        response = http.get(fit_url)
        response.raise_for_status()
        return response.content


def attach_fit_bytes_to_activity(
    db: Session,
    *,
    target: Activity,
    fit_bytes: bytes,
    coros_external_id: str,
    connection: ProviderConnection | None = None,
    count_quota: bool = True,
) -> dict[str, Any]:
    """Parse FIT bytes and write parquet streams onto target activity."""
    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(fit_bytes)
        tmp_path = Path(tmp.name)

    try:
        points_root = Path(ACTIVITY_POINTS_DIR).expanduser().resolve()
        points_root.mkdir(parents=True, exist_ok=True)
        lap_df, point_df = _fit_file_to_dataframes(str(tmp_path))
        normalized = normalize_point_dataframe(point_df)
        if normalized.empty:
            return {
                "ok": False,
                "reason": "empty_points",
                "activity_id": target.id,
            }

        file_id = target.external_activity_id or target.id
        points_path = write_points_parquet(
            normalized,
            target.athlete_profile_id,
            file_id,
            points_root,
            provider=target.provider or PROVIDER,
        )
        target.points_file_path = points_path
        summary = extract_lap_summary(lap_df)
        if summary.get("distance_m"):
            target.distance_m = float(summary["distance_m"] or target.distance_m or 0)
        if summary.get("moving_time_s"):
            target.moving_time_s = int(summary["moving_time_s"] or target.moving_time_s or 0)
        if summary.get("average_heartrate") and not target.average_heartrate:
            target.average_heartrate = summary.get("average_heartrate")
        if summary.get("max_heartrate") and not target.max_heartrate:
            target.max_heartrate = summary.get("max_heartrate")
        target.source_fit_file = f"coros_fit:{coros_external_id}"

        if count_quota and connection is not None:
            _reset_daily_quota_if_needed(connection)
            connection.fit_downloads_today = int(connection.fit_downloads_today or 0) + 1

        db.commit()
        db.refresh(target)
        return {
            "ok": True,
            "activity_id": target.id,
            "points_file_path": points_path,
            "point_rows": int(len(normalized)),
            "coros_external_id": coros_external_id,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def attach_coros_fit_to_activity(
    client: CorosMcpClient,
    db: Session,
    connection: ProviderConnection,
    activity: Activity,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch COROS FIT for an activity (or its COROS twin) and attach streams."""
    if activity.points_file_path and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_has_points",
            "activity_id": activity.id,
        }

    resolved = resolve_coros_fit_source(db, activity)
    if resolved is None:
        return {
            "ok": False,
            "reason": "no_coros_source",
            "activity_id": activity.id,
        }
    target, coros_external_id = resolved

    if target.points_file_path and not force:
        # Canonical already has streams; mirror path onto COROS row if needed.
        if activity.id != target.id and not activity.points_file_path:
            activity.points_file_path = target.points_file_path
            db.commit()
        return {
            "ok": True,
            "skipped": True,
            "reason": "target_already_has_points",
            "activity_id": target.id,
        }

    if remaining_fit_quota(connection) <= 0:
        return {
            "ok": False,
            "reason": "quota_exhausted",
            "activity_id": activity.id,
            "quota": COROS_FIT_DAILY_LIMIT,
        }

    fit_url = fetch_coros_fit_url(client, coros_external_id)
    if not fit_url:
        return {
            "ok": False,
            "reason": "no_fit_url",
            "activity_id": activity.id,
            "coros_external_id": coros_external_id,
        }

    fit_bytes = download_fit_bytes(fit_url)
    result = attach_fit_bytes_to_activity(
        db,
        target=target,
        fit_bytes=fit_bytes,
        coros_external_id=coros_external_id,
        connection=connection,
        count_quota=True,
    )
    if result.get("ok") and activity.id != target.id:
        activity.points_file_path = target.points_file_path
        activity.source_fit_file = f"coros_fit:{coros_external_id}"
        db.commit()
    return result


def backfill_coros_fit_for_athlete(
    db: Session,
    athlete_profile_id: int,
    *,
    client: CorosMcpClient | None = None,
    connection: ProviderConnection | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Backfill FIT streams for recent activities missing points."""
    from app.services.coros_sync import _client_for_connection, get_coros_connection

    connection = connection or get_coros_connection(db, athlete_profile_id)
    if connection is None:
        return {"ok": False, "reason": "not_connected", "filled": 0, "attempted": 0}

    client = client or _client_for_connection(db, connection)
    quota = remaining_fit_quota(connection)
    max_items = min(limit or COROS_FIT_RECENT_LIMIT, quota, COROS_FIT_RECENT_LIMIT)
    if max_items <= 0:
        return {
            "ok": False,
            "reason": "quota_exhausted",
            "filled": 0,
            "attempted": 0,
            "remaining_quota": quota,
        }

    # Prefer canonical rows missing points that have a COROS source.
    candidates: list[Activity] = []

    coros_missing = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == PROVIDER,
            Activity.points_file_path.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(max_items * 3)
        .all()
    )
    for row in coros_missing:
        target = row
        if row.canonical_activity_id:
            parent = (
                db.query(Activity)
                .filter(Activity.id == row.canonical_activity_id)
                .first()
            )
            if parent is not None and parent.points_file_path:
                row.points_file_path = parent.points_file_path
                db.commit()
                continue
            if parent is not None:
                target = parent
        if target.points_file_path:
            continue
        if target not in candidates:
            candidates.append(target)

    strava_missing = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == "strava",
            Activity.canonical_activity_id.is_(None),
            Activity.points_file_path.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(max_items * 2)
        .all()
    )
    for row in strava_missing:
        twin = (
            db.query(Activity.id)
            .filter(
                Activity.athlete_profile_id == athlete_profile_id,
                Activity.provider == PROVIDER,
                Activity.canonical_activity_id == row.id,
            )
            .first()
        )
        if twin and row not in candidates:
            candidates.append(row)

    candidates = candidates[:max_items]
    filled = 0
    attempted = 0
    errors: list[str] = []
    details: list[dict[str, Any]] = []

    try:
        client.initialize()
    except CorosMcpError as exc:
        return {"ok": False, "reason": str(exc), "filled": 0, "attempted": 0}

    for activity in candidates:
        attempted += 1
        try:
            result = attach_coros_fit_to_activity(client, db, connection, activity)
            details.append(result)
            if result.get("ok") and not result.get("skipped"):
                filled += 1
            elif not result.get("ok") and result.get("reason"):
                errors.append(f"{activity.id}:{result['reason']}")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append(f"{activity.id}:{exc}")

    return {
        "ok": True,
        "filled": filled,
        "attempted": attempted,
        "remaining_quota": remaining_fit_quota(connection),
        "errors": errors[-20:],
        "details": details,
        "updated_at": datetime.utcnow().isoformat(),
    }
