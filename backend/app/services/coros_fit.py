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

# COROS MCP requires numeric sportType when fetching FIT by labelId.
# Codes confirmed from querySportRecords responses.
COROS_SPORT_TYPE_CODES: dict[str, int] = {
    "outdoor run": 100,
    "run": 100,
    "trail run": 102,
    "hike": 104,
    "cycling": 200,
    "outdoor cycling": 200,
    "road bike": 200,
    "indoor cycling": 201,
    "strength": 402,
    "weight training": 402,
    "weighttraining": 402,
    "gym": 402,
    "walk": 900,
    "yoga": 904,
    "pilates": 904,
    "multisport": 10001,
}


def resolve_coros_sport_type_code(activity: Activity) -> int | None:
    """Resolve COROS numeric sportType for FIT / detail API calls."""
    raw = getattr(activity, "sport_type_code", None)
    if raw is not None and str(raw).strip().isdigit():
        return int(str(raw).strip())

    sport = (activity.sport_type or "").strip().lower()
    if not sport:
        return None
    if sport in COROS_SPORT_TYPE_CODES:
        return COROS_SPORT_TYPE_CODES[sport]
    # Fuzzy: match any known key contained in sport name (or vice versa).
    for key, code in COROS_SPORT_TYPE_CODES.items():
        if key in sport or sport in key:
            return code
    return None


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
    """Return (target_activity_to_receive_points, coros_external_id) or None.

    When several COROS rows incorrectly point at the same Strava parent, pick the
    twin whose start time / duration best matches the viewed activity — never
    just the highest id.
    """
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
        twins = (
            db.query(Activity)
            .filter(
                Activity.athlete_profile_id == activity.athlete_profile_id,
                Activity.provider == PROVIDER,
                Activity.canonical_activity_id == activity.id,
            )
            .all()
        )
        if not twins:
            # Fallback: unlinked COROS twin with the same start / best score.
            from app.services.activity_dedupe import find_cross_provider_match

            twin = find_cross_provider_match(
                db,
                athlete_profile_id=activity.athlete_profile_id,
                activity_date=activity.activity_date,
                distance_m=float(activity.distance_m or 0.0),
                moving_time_s=int(activity.moving_time_s or 0),
                other_provider=PROVIDER,
                sport_type=activity.sport_type,
                exclude_id=activity.id,
                allow_already_linked=True,
                for_activity_id=activity.id,
            )
            if twin is None:
                return None
            return activity, str(twin.external_activity_id)

        if len(twins) == 1:
            return activity, str(twins[0].external_activity_id)

        from app.services.activity_dedupe import match_quality_score

        best = None
        best_score = None
        for twin in twins:
            score = match_quality_score(
                date_a=activity.activity_date,
                distance_a=float(activity.distance_m or 0.0),
                duration_a=int(activity.moving_time_s or 0),
                date_b=twin.activity_date,
                distance_b=float(twin.distance_m or 0.0),
                duration_b=int(twin.moving_time_s or 0),
                sport_a=activity.sport_type,
                sport_b=twin.sport_type,
            )
            # Even if fingerprint fails (wrong links), still rank by time+duration.
            if score is None:
                da = activity.activity_date
                db_ = twin.activity_date
                if da is None or db_ is None:
                    continue
                delta = abs(
                    (da.replace(tzinfo=None) if da.tzinfo else da)
                    - (db_.replace(tzinfo=None) if db_.tzinfo else db_)
                ).total_seconds()
                score = (
                    delta,
                    abs(float(activity.distance_m or 0) - float(twin.distance_m or 0)),
                    abs(float(activity.moving_time_s or 0) - float(twin.moving_time_s or 0)),
                )
            if best is None or best_score is None or score < best_score:
                best = twin
                best_score = score
        if best is None:
            return None
        return activity, str(best.external_activity_id)

    return None


def fetch_coros_fit_url(
    client: CorosMcpClient,
    coros_external_id: str,
    *,
    sport_type_code: int | None = None,
) -> str | None:
    """Ask COROS MCP for a FIT download URL.

    Correct argument shape (from MCP tool schema):
      labelId   : string  — COROS activity label id
      sportType : integer — required when labelId is provided
    """
    payloads: list[Any] = []
    argument_sets: list[dict[str, Any]] = []
    if sport_type_code is not None:
        argument_sets.append(
            {"labelId": str(coros_external_id), "sportType": int(sport_type_code)}
        )
    # Date-window fallback without labelId (returns recent FITs; we match by id).
    argument_sets.append({"limit": 10})

    for tool in ("queryActivityFitFileDownloadUrls", "downloadActivityFitFiles"):
        for args in argument_sets:
            try:
                payloads.append(client.call_tool(tool, args))
            except CorosMcpError:
                continue

    for payload in payloads:
        url = extract_fit_url(payload)
        if url:
            # Prefer a URL that contains this activity's labelId.
            if str(coros_external_id) in url:
                return url
    # Second pass: accept any URL if label-specific match wasn't found.
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


def _merge_exercises_into_detail_json(activity: Activity, exercises: list[dict]) -> None:
    """Write exercises (+ derived muscle map) into activity.detail_json."""
    if not exercises:
        return
    try:
        detail: dict = json.loads(activity.detail_json) if activity.detail_json else {}
    except (json.JSONDecodeError, TypeError):
        detail = {}
    detail["exercises"] = exercises
    try:
        from app.utils.exercise_catalog import build_muscle_map

        detail["muscle_map"] = build_muscle_map(exercises)
    except Exception:
        detail.pop("muscle_map", None)
    activity.detail_json = json.dumps(detail)


_STRENGTH_SPORT_KEYWORDS = {
    "strength", "weight", "gym", "yoga", "pilates", "crossfit",
    "functional", "hiit", "cardio", "dance", "aerobics", "barre",
    "indoor", "training", "workout", "stretch", "mobility",
}


def _is_strength_activity(activity: Activity) -> bool:
    sport = (activity.sport_type or "").lower()
    return any(kw in sport for kw in _STRENGTH_SPORT_KEYWORDS)


def attach_fit_bytes_to_activity(
    db: Session,
    *,
    target: Activity,
    fit_bytes: bytes,
    coros_external_id: str,
    connection: ProviderConnection | None = None,
    count_quota: bool = True,
) -> dict[str, Any]:
    """Parse FIT bytes, write parquet streams, and extract exercise/set data."""
    from app.utils.fit_strength_parser import extract_exercises_from_fit_bytes

    # Always attempt exercise extraction for strength-family activities.
    exercises = extract_exercises_from_fit_bytes(fit_bytes)
    if exercises:
        _merge_exercises_into_detail_json(target, exercises)

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(fit_bytes)
        tmp_path = Path(tmp.name)

    try:
        points_root = Path(ACTIVITY_POINTS_DIR).expanduser().resolve()
        points_root.mkdir(parents=True, exist_ok=True)
        target.source_fit_file = f"coros_fit:{coros_external_id}"
        normalized = None

        # Stream extraction is best-effort — strength FITs often have no GPS points
        # and some converters choke on COROS set/event quirks. Exercises already
        # extracted above must still be saved.
        try:
            lap_df, point_df = _fit_file_to_dataframes(str(tmp_path))
            normalized = normalize_point_dataframe(point_df)
        except Exception:
            lap_df = None
            normalized = None

        if normalized is not None and not normalized.empty:
            file_id = target.external_activity_id or target.id
            points_path = write_points_parquet(
                normalized,
                target.athlete_profile_id,
                file_id,
                points_root,
                provider=target.provider or PROVIDER,
            )
            target.points_file_path = points_path
            summary = extract_lap_summary(lap_df) if lap_df is not None else {}
            if summary.get("distance_m"):
                target.distance_m = float(summary["distance_m"] or target.distance_m or 0)
            if summary.get("moving_time_s"):
                target.moving_time_s = int(summary["moving_time_s"] or target.moving_time_s or 0)
            if summary.get("average_heartrate") and not target.average_heartrate:
                target.average_heartrate = summary.get("average_heartrate")
            if summary.get("max_heartrate") and not target.max_heartrate:
                target.max_heartrate = summary.get("max_heartrate")

        if count_quota and connection is not None:
            _reset_daily_quota_if_needed(connection)
            connection.fit_downloads_today = int(connection.fit_downloads_today or 0) + 1

        db.commit()
        db.refresh(target)

        result: dict[str, Any] = {
            "ok": True,
            "activity_id": target.id,
            "coros_external_id": coros_external_id,
            "exercises_found": len(exercises),
        }
        if target.points_file_path:
            result["points_file_path"] = target.points_file_path
            result["point_rows"] = (
                int(len(normalized)) if normalized is not None and not normalized.empty else 0
            )
        elif not exercises:
            result["ok"] = False
            result["reason"] = "empty_points_and_no_exercises"
        return result
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

    def _has_exercises(act: Activity) -> bool:
        try:
            detail = json.loads(act.detail_json) if act.detail_json else {}
            return bool(detail.get("exercises"))
        except (json.JSONDecodeError, TypeError):
            return False

    # For strength-family activities, always download FIT even if points exist
    # because we need to extract exercise/set data that isn't in GPS points.
    is_strength = _is_strength_activity(activity)

    if activity.points_file_path and not force and not is_strength:
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_has_points",
            "activity_id": activity.id,
        }

    # Skip only if BOTH points and exercises already exist (and not forced).
    if activity.points_file_path and _has_exercises(activity) and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_has_points_and_exercises",
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

    if target.points_file_path and _has_exercises(target) and not force:
        # Only skip when streams already came from THIS COROS activity.
        expected_fit = f"coros_fit:{coros_external_id}"
        if (target.source_fit_file or "") == expected_fit or (
            activity.source_fit_file or ""
        ) == expected_fit:
            if activity.id != target.id and not activity.points_file_path:
                activity.points_file_path = target.points_file_path
                db.commit()
            return {
                "ok": True,
                "skipped": True,
                "reason": "target_already_has_points",
                "activity_id": target.id,
                "exercises_found": len(
                    (json.loads(target.detail_json or "{}") or {}).get("exercises") or []
                ),
            }
        # Wrong FIT attached to parent — fall through and re-fetch the correct one.

    if remaining_fit_quota(connection) <= 0:
        return {
            "ok": False,
            "reason": "quota_exhausted",
            "activity_id": activity.id,
            "quota": COROS_FIT_DAILY_LIMIT,
        }

    # Resolve sport type code from the COROS-sourced row when possible.
    coros_row = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == activity.athlete_profile_id,
            Activity.provider == PROVIDER,
            Activity.external_activity_id == str(coros_external_id),
        )
        .first()
    )
    sport_code = resolve_coros_sport_type_code(coros_row or activity)
    if sport_code is None:
        sport_code = resolve_coros_sport_type_code(target)

    fit_url = fetch_coros_fit_url(
        client, coros_external_id, sport_type_code=sport_code
    )
    if not fit_url:
        return {
            "ok": False,
            "reason": "no_fit_url",
            "activity_id": activity.id,
            "coros_external_id": coros_external_id,
            "sport_type_code": sport_code,
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

    # Persist resolved sport code for future FIT / detail calls.
    if sport_code is not None:
        for row in (coros_row, target, activity):
            if row is not None and not row.sport_type_code:
                row.sport_type_code = str(sport_code)

    def _mirror_exercises(from_act: Activity, to_act: Activity) -> None:
        if from_act is None or to_act is None or from_act.id == to_act.id:
            return
        if not from_act.detail_json:
            return
        try:
            from_detail = json.loads(from_act.detail_json)
        except (json.JSONDecodeError, TypeError):
            return
        if from_detail.get("exercises"):
            _merge_exercises_into_detail_json(to_act, from_detail["exercises"])

    if result.get("ok"):
        if activity.id != target.id:
            activity.points_file_path = target.points_file_path or activity.points_file_path
            activity.source_fit_file = f"coros_fit:{coros_external_id}"
            _mirror_exercises(target, activity)
        # Keep COROS twin in sync when target is the Strava canonical.
        if coros_row is not None and coros_row.id != target.id:
            coros_row.source_fit_file = f"coros_fit:{coros_external_id}"
            _mirror_exercises(target, coros_row)
        db.commit()
    elif sport_code is not None:
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

    # Also pick up strength activities that have no exercise data in detail_json.
    if len(candidates) < max_items:
        strength_keywords = [
            "%strength%", "%weight%", "%gym%", "%yoga%", "%pilates%",
            "%crossfit%", "%hiit%", "%functional%", "%training%",
        ]
        from sqlalchemy import or_
        strength_filter = or_(
            *[Activity.sport_type.ilike(kw) for kw in strength_keywords]
        )
        strength_no_exercises = (
            db.query(Activity)
            .filter(
                Activity.athlete_profile_id == athlete_profile_id,
                Activity.provider == PROVIDER,
                strength_filter,
                or_(
                    Activity.detail_json.is_(None),
                    Activity.detail_json == "",
                    ~Activity.detail_json.contains('"exercises"'),
                ),
            )
            .order_by(Activity.activity_date.desc())
            .limit((max_items - len(candidates)) * 2)
            .all()
        )
        for row in strength_no_exercises:
            target = row
            if row.canonical_activity_id:
                parent = (
                    db.query(Activity)
                    .filter(Activity.id == row.canonical_activity_id)
                    .first()
                )
                if parent is not None:
                    target = parent
            if target not in candidates:
                candidates.append(target)

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
