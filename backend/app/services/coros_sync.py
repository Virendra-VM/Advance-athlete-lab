"""COROS MCP sync: health, EvoLab, training load, schedule, activities."""

from __future__ import annotations

import json
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import (
    ACTIVITY_POINTS_DIR,
    COROS_ACTIVITY_LOOKBACK_DAYS,
    COROS_FIT_DAILY_LIMIT,
    COROS_FIT_RECENT_LIMIT,
    COROS_HEALTH_LOOKBACK_DAYS,
)
from app.models import (
    Activity,
    CorosScheduleItem,
    DailyHealthMetric,
    FitnessAssessment,
    ProviderConnection,
    TrainingLoadSnapshot,
)
from app.services.coros_mcp import CorosMcpClient, CorosMcpError, _load_persisted_client_id
from app.services.coros_text_parsers import (
    parse_daily_health_data,
    parse_fitness_assessment,
    parse_hrv_assessment,
    parse_recovery_status,
    parse_simple_daily_series,
    parse_sleep_data,
    parse_sport_records,
    parse_stress_series,
    parse_training_load,
    parse_training_schedule,
)
from app.services.activity_dedupe import (
    backfill_athlete_duplicates,
    choose_canonical,
    find_cross_provider_match,
    link_duplicate,
    link_new_activity_to_peer,
)
from app.services.schedule_completion import match_schedule_completions
from app.services.strava_import import write_points_parquet

PROVIDER = "coros"

# Per-athlete sync status (avoids global Strava lock collisions)
_sync_status: dict[int, dict[str, Any]] = {}
_status_lock = threading.Lock()


class CorosSyncAlreadyRunning(Exception):
    """Raised when a second COROS sync tries to claim an in-flight slot."""


def get_sync_status(athlete_profile_id: int | None = None) -> dict[str, Any]:
    if athlete_profile_id is None:
        running = any(s.get("running") for s in _sync_status.values())
        return {
            "running": running,
            "total": 0,
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [],
        }
    status = _sync_status.get(athlete_profile_id)
    if status is None:
        return {
            "running": False,
            "total": 0,
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [],
        }
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


def _claim_sync(athlete_profile_id: int, *, total: int = 5) -> bool:
    """Claim the per-athlete COROS sync slot. Returns False if already running."""
    with _status_lock:
        if get_sync_status(athlete_profile_id).get("running"):
            return False
        _set_status(
            athlete_profile_id,
            running=True,
            total=total,
            processed=0,
            imported=0,
            skipped=0,
            errors=[],
        )
        return True


def get_coros_connection(db: Session, athlete_profile_id: int) -> ProviderConnection | None:
    return (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.athlete_profile_id == athlete_profile_id,
            ProviderConnection.provider == PROVIDER,
        )
        .first()
    )


def _parse_json_maybe(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _as_list(payload: Any) -> list[Any]:
    payload = _parse_json_maybe(payload)
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "list", "records", "items", "activities", "workouts", "days"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


def _dig(payload: Any, *keys: str, default: Any = None) -> Any:
    current = _parse_json_maybe(payload)
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    compact = text[:8]
    if len(compact) == 8 and compact.isdigit():
        try:
            return datetime.strptime(compact, "%Y%m%d").date()
        except ValueError:
            pass
    normalized = text[:10].replace("/", "-")
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass
    d = _parse_date(text)
    if d:
        return datetime.combine(d, datetime.min.time())
    return None


def _client_for_connection(db: Session, connection: ProviderConnection) -> CorosMcpClient:
    client_id = _load_persisted_client_id()
    meta = {}
    if connection.meta_json:
        try:
            meta = json.loads(connection.meta_json)
        except json.JSONDecodeError:
            meta = {}

    def on_refresh(token_data: dict[str, Any]) -> None:
        connection.access_token = token_data["access_token"]
        if token_data.get("refresh_token"):
            connection.refresh_token = token_data["refresh_token"]
        expires_in = token_data.get("expires_in")
        if expires_in:
            connection.expires_at = int(datetime.now(timezone.utc).timestamp()) + int(expires_in)
        db.commit()

    return CorosMcpClient(
        access_token=connection.access_token,
        mcp_url=connection.mcp_resource_url or "https://mcpus.coros.com/mcp",
        client_id=client_id or meta.get("client_id"),
        refresh_token=connection.refresh_token,
        token_endpoint=meta.get("token_endpoint")
        or (
            f"{connection.authorization_server.rstrip('/')}/oauth2/token"
            if connection.authorization_server
            else None
        ),
        resource=connection.mcp_resource_url,
        on_token_refresh=on_refresh,
    )


def _date_range_args(days: int) -> dict[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    start_s = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    return {
        "startDate": start_s,
        "endDate": end_s,
        "start_date": start_s,
        "end_date": end_s,
        "from": start_s,
        "to": end_s,
    }


def _schedule_range_args(past_days: int = 7, future_days: int = 42) -> dict[str, str]:
    start = date.today() - timedelta(days=past_days)
    end = date.today() + timedelta(days=future_days)
    start_s = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    return {"startDate": start_s, "endDate": end_s}


def _days_args(days: int) -> dict[str, int]:
    """Argument shape for tools that only accept `days` (additionalProperties: false)."""
    return {"days": max(1, min(int(days), 365))}


def _call_with_fallbacks(client: CorosMcpClient, tool: str, argument_sets: list[dict[str, Any]]) -> Any:
    last_error: Exception | None = None
    for args in argument_sets:
        try:
            return client.call_tool(tool, args)
        except CorosMcpError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return None


def _upsert_health_row(
    db: Session,
    athlete_profile_id: int,
    metric_date: date,
    fields: dict[str, Any],
    raw: Any,
) -> None:
    row = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == athlete_profile_id,
            DailyHealthMetric.provider == PROVIDER,
            DailyHealthMetric.metric_date == metric_date,
        )
        .first()
    )
    if row is None:
        row = DailyHealthMetric(
            athlete_profile_id=athlete_profile_id,
            provider=PROVIDER,
            metric_date=metric_date,
        )
        db.add(row)

    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    row.raw_json = json.dumps(raw, default=str)[:20000]
    row.updated_at = datetime.utcnow()


def sync_health_metrics(
    client: CorosMcpClient,
    db: Session,
    athlete_profile_id: int,
    lookback_days: int | None = None,
) -> int:
    lookback = min(lookback_days or COROS_HEALTH_LOOKBACK_DAYS, 365)
    days_args = _days_args(lookback)
    range_args = _date_range_args(lookback)
    buckets: dict[date, dict[str, Any]] = {}
    raw_by_date: dict[date, dict[str, Any]] = {}

    def _merge(rows: list[dict[str, Any]], label: str, raw_payload: Any) -> None:
        for item in rows:
            metric_date = item.get("metric_date")
            if not isinstance(metric_date, date):
                continue
            bucket = buckets.setdefault(metric_date, {})
            raw_bucket = raw_by_date.setdefault(metric_date, {})
            raw_bucket[label] = item
            for key, value in item.items():
                if key == "metric_date" or value is None:
                    continue
                # Daily report header RHR/HRV are baselines, not per-day values.
                if label == "daily" and key in {"resting_heart_rate", "hrv"}:
                    continue
                bucket[key] = value
        # Keep a copy of the raw tool text for debugging on the latest day
        if isinstance(raw_payload, str) and buckets:
            latest = max(buckets.keys())
            raw_by_date.setdefault(latest, {})[f"{label}_raw"] = raw_payload[:4000]

    # Tools with additionalProperties:false only accept {days}. Passing startDate
    # makes the call fail and we previously fell back to {} (= last 7 days).
    parsers = [
        ("daily", "queryDailyHealthData", parse_daily_health_data, [days_args]),
        ("sleep", "querySleepData", parse_sleep_data, [days_args, range_args]),
        ("hrv", "querySleepHrv", parse_hrv_assessment, [days_args, range_args]),
        (
            "rhr",
            "queryRestingHeartRate",
            lambda t: parse_simple_daily_series(t, "resting_heart_rate"),
            [days_args],
        ),
        ("stress", "queryStressLevel", parse_stress_series, [days_args]),
        (
            "avg_hr",
            "queryAvgHeartRate",
            lambda t: parse_simple_daily_series(t, "avg_heart_rate"),
            [days_args, range_args],
        ),
    ]

    for label, tool, parser, arg_sets in parsers:
        try:
            payload = _call_with_fallbacks(client, tool, arg_sets)
        except CorosMcpError:
            continue
        if isinstance(payload, str) and "anomalies detected" in payload.lower():
            continue
        if isinstance(payload, str) and "must be in yyyymmdd" in payload.lower():
            continue
        rows = parser(payload) if isinstance(payload, str) else []
        # Also accept dict/list responses if COROS changes format later
        if not rows and isinstance(payload, (dict, list)):
            for item in _as_list(payload):
                if isinstance(item, dict):
                    metric_date = _parse_date(
                        item.get("date") or item.get("metricDate") or item.get("day")
                    )
                    if metric_date:
                        item = {**item, "metric_date": metric_date}
                        rows.append(item)
        _merge(rows, label, payload)

    imported = 0
    for metric_date, fields in buckets.items():
        _upsert_health_row(
            db,
            athlete_profile_id,
            metric_date,
            fields,
            raw_by_date.get(metric_date, {}),
        )
        imported += 1
    db.commit()
    return imported


def sync_fitness_and_recovery(
    client: CorosMcpClient, db: Session, athlete_profile_id: int
) -> FitnessAssessment | None:
    fitness_payload = None
    recovery_payload = None
    try:
        fitness_payload = client.call_tool("queryFitnessAssessmentOverview", {})
    except CorosMcpError:
        fitness_payload = None
    try:
        recovery_payload = client.call_tool("queryRecoveryStatus", {})
    except CorosMcpError:
        recovery_payload = None

    if fitness_payload is None and recovery_payload is None:
        return None

    if isinstance(fitness_payload, str):
        fitness = parse_fitness_assessment(fitness_payload)
    elif isinstance(fitness_payload, dict):
        fitness = {
            "vo2max": _to_float(
                fitness_payload.get("vo2max")
                or fitness_payload.get("vo2Max")
                or fitness_payload.get("VO2max")
            ),
            "running_performance": _to_float(
                fitness_payload.get("runningPerformance")
                or fitness_payload.get("runningLevel")
            ),
            "threshold_pace": fitness_payload.get("thresholdPace")
            or fitness_payload.get("threshold_pace"),
            "race_predictions": {
                "5k": fitness_payload.get("predict5k")
                or _dig(fitness_payload, "racePredictions", "5k"),
                "10k": fitness_payload.get("predict10k")
                or _dig(fitness_payload, "racePredictions", "10k"),
                "half": fitness_payload.get("predictHalf")
                or _dig(fitness_payload, "racePredictions", "half"),
                "marathon": fitness_payload.get("predictMarathon")
                or _dig(fitness_payload, "racePredictions", "marathon"),
            },
        }
    else:
        fitness = {}

    if isinstance(recovery_payload, str):
        recovery = parse_recovery_status(recovery_payload)
    elif isinstance(recovery_payload, dict):
        recovery = {
            "recovery_pct": _to_float(
                recovery_payload.get("recoveryPct")
                or recovery_payload.get("recovery")
                or recovery_payload.get("percent")
            ),
            "recovery_level": recovery_payload.get("recoveryLevel")
            or recovery_payload.get("level"),
            "recovery_full_at": recovery_payload.get("fullRecoveryTime")
            or recovery_payload.get("estimatedFullRecoveryTime"),
        }
    else:
        recovery = {}

    race_preds = fitness.get("race_predictions") or {}

    # Upsert one fitness/recovery snapshot per calendar day so charts can build history.
    day_start = datetime.combine(date.today(), datetime.min.time())
    day_end = datetime.combine(date.today(), datetime.max.time().replace(microsecond=0))
    row = (
        db.query(FitnessAssessment)
        .filter(
            FitnessAssessment.athlete_profile_id == athlete_profile_id,
            FitnessAssessment.provider == PROVIDER,
            FitnessAssessment.snapshot_at >= day_start,
            FitnessAssessment.snapshot_at <= day_end,
        )
        .order_by(FitnessAssessment.snapshot_at.desc())
        .first()
    )
    if row is None:
        row = FitnessAssessment(
            athlete_profile_id=athlete_profile_id,
            provider=PROVIDER,
            snapshot_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.snapshot_at = datetime.utcnow()

    row.vo2max = fitness.get("vo2max")
    row.running_performance = fitness.get("running_performance")
    row.threshold_pace = str(fitness.get("threshold_pace") or "") or None
    row.race_preds_json = json.dumps(race_preds, default=str)
    row.recovery_pct = recovery.get("recovery_pct")
    row.recovery_level = str(recovery.get("recovery_level") or "") or None
    row.recovery_full_at = str(recovery.get("recovery_full_at") or "") or None
    row.raw_json = json.dumps(
        {"fitness": fitness_payload, "recovery": recovery_payload}, default=str
    )[:20000]
    db.commit()
    db.refresh(row)
    return row


def sync_training_load(
    client: CorosMcpClient, db: Session, athlete_profile_id: int
) -> TrainingLoadSnapshot | None:
    try:
        payload = client.call_tool("queryTrainingLoadAssessment", {})
    except CorosMcpError:
        return None

    if isinstance(payload, str):
        parsed = parse_training_load(payload)
        comments = parsed.get("daily_comments") or []
        short_load = parsed.get("short_load")
        long_load = parsed.get("long_load")
        load_ratio = parsed.get("load_ratio")
    elif isinstance(payload, dict):
        comments = (
            payload.get("dailyComments")
            or payload.get("comments")
            or payload.get("recentDailyComments")
            or []
        )
        short_load = _to_float(
            payload.get("shortTermLoad") or payload.get("short_load") or payload.get("acuteLoad")
        )
        long_load = _to_float(
            payload.get("longTermLoad") or payload.get("long_load") or payload.get("chronicLoad")
        )
        load_ratio = _to_float(payload.get("loadRatio") or payload.get("ratio"))
    else:
        return None

    day_start = datetime.combine(date.today(), datetime.min.time())
    day_end = datetime.combine(date.today(), datetime.max.time().replace(microsecond=0))
    row = (
        db.query(TrainingLoadSnapshot)
        .filter(
            TrainingLoadSnapshot.athlete_profile_id == athlete_profile_id,
            TrainingLoadSnapshot.provider == PROVIDER,
            TrainingLoadSnapshot.snapshot_at >= day_start,
            TrainingLoadSnapshot.snapshot_at <= day_end,
        )
        .order_by(TrainingLoadSnapshot.snapshot_at.desc())
        .first()
    )
    if row is None:
        row = TrainingLoadSnapshot(
            athlete_profile_id=athlete_profile_id,
            provider=PROVIDER,
            snapshot_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.snapshot_at = datetime.utcnow()

    row.short_load = short_load
    row.long_load = long_load
    row.load_ratio = load_ratio
    row.daily_comments_json = json.dumps(comments, default=str)
    row.raw_json = json.dumps(payload, default=str)[:20000]
    db.commit()
    db.refresh(row)
    return row


def sync_schedule(client: CorosMcpClient, db: Session, athlete_profile_id: int) -> int:
    # Schema requires startDate/endDate; pull a wide past+future window.
    range_args = _schedule_range_args(past_days=120, future_days=90)
    try:
        payload = _call_with_fallbacks(
            client,
            "queryTrainingSchedule",
            [range_args],
        )
    except CorosMcpError:
        return 0

    items: list[Any] = []
    if isinstance(payload, str):
        items = parse_training_schedule(payload)
    else:
        items = _as_list(payload)

    imported = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        schedule_date = _parse_date(
            item.get("date")
            or item.get("scheduleDate")
            or item.get("day")
            or item.get("planDate")
        )
        if schedule_date is None:
            continue
        external_id = str(
            item.get("id")
            or item.get("idInPlan")
            or item.get("workoutId")
            or f"{schedule_date.isoformat()}-{item.get('dayNo') or item.get('title') or imported}"
        )
        row = (
            db.query(CorosScheduleItem)
            .filter(
                CorosScheduleItem.athlete_profile_id == athlete_profile_id,
                CorosScheduleItem.external_id == external_id,
            )
            .first()
        )
        if row is None:
            row = CorosScheduleItem(
                athlete_profile_id=athlete_profile_id,
                external_id=external_id,
                schedule_date=schedule_date,
            )
            db.add(row)
        row.schedule_date = schedule_date
        row.title = item.get("title") or item.get("name") or item.get("workoutName")
        row.sport_type = item.get("sportType") or item.get("sport") or item.get("type")
        row.duration_min = _to_float(
            item.get("durationMin") or item.get("duration") or item.get("estimateDuration")
        )
        row.distance_m = _to_float(
            item.get("distanceM") or item.get("distance") or item.get("estimateDistance")
        )
        row.day_no = _to_int(item.get("dayNo") or item.get("day_no"))
        row.id_in_plan = str(item.get("idInPlan") or "") or None
        row.raw_json = json.dumps(item, default=str)[:20000]
        row.updated_at = datetime.utcnow()
        imported += 1
    db.commit()
    # Link completed activities to planned workouts for this window.
    match_schedule_completions(db, athlete_profile_id)
    return imported


def _activity_exists(db: Session, athlete_profile_id: int, external_id: str) -> bool:
    return (
        db.query(Activity.id)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.provider == PROVIDER,
            Activity.external_activity_id == external_id,
        )
        .first()
        is not None
    )


def sync_activities(
    client: CorosMcpClient,
    db: Session,
    athlete_profile_id: int,
    connection: ProviderConnection,
) -> tuple[int, int]:
    range_args = _date_range_args(COROS_ACTIVITY_LOOKBACK_DAYS)
    try:
        payload = _call_with_fallbacks(
            client,
            "querySportRecords",
            [range_args, {}],
        )
    except CorosMcpError as exc:
        raise CorosMcpError(f"querySportRecords failed: {exc}") from exc

    if isinstance(payload, str):
        if "anomalies detected" in payload.lower():
            return 0, 0
        records = parse_sport_records(payload)
    else:
        records = []
        for item in _as_list(payload):
            if isinstance(item, dict):
                records.append(
                    {
                        "external_id": str(
                            item.get("activityId")
                            or item.get("id")
                            or item.get("labelId")
                            or ""
                        ),
                        "name": item.get("name") or item.get("title") or item.get("location"),
                        "sport_type": item.get("sportTypeName") or item.get("sportType"),
                        "sport_type_code": (
                            str(item.get("sportType"))
                            if item.get("sportType") is not None
                            and str(item.get("sportType")).isdigit()
                            else (
                                str(item.get("sportTypeCode"))
                                if item.get("sportTypeCode") is not None
                                else None
                            )
                        ),
                        "activity_date": _parse_datetime(
                            item.get("startTime") or item.get("date")
                        )
                        or datetime.utcnow(),
                        "distance_m": _to_float(item.get("distance") or item.get("distanceM"))
                        or 0.0,
                        "moving_time_s": _to_int(
                            item.get("movingTime") or item.get("duration") or item.get("totalTime")
                        )
                        or 0,
                        "average_heartrate": _to_float(
                            item.get("avgHr") or item.get("averageHeartRate")
                        ),
                    }
                )

    imported = 0
    skipped = 0
    recent_for_fit: list[tuple[str, Activity]] = []

    for item in records:
        external_id = str(item.get("external_id") or "")
        if not external_id:
            skipped += 1
            continue
        activity_date = item.get("activity_date") or datetime.utcnow()
        if isinstance(activity_date, date) and not isinstance(activity_date, datetime):
            activity_date = datetime.combine(activity_date, datetime.min.time())
        distance_m = float(item.get("distance_m") or 0.0)
        moving_time_s = int(item.get("moving_time_s") or 0)
        name = item.get("name") or f"COROS activity {external_id}"
        sport_type = item.get("sport_type")
        sport_type_code = item.get("sport_type_code")
        avg_hr = item.get("average_heartrate")

        if _activity_exists(db, athlete_profile_id, external_id):
            # Still try to link existing COROS row to a Strava peer.
            existing = (
                db.query(Activity)
                .filter(
                    Activity.athlete_profile_id == athlete_profile_id,
                    Activity.provider == PROVIDER,
                    Activity.external_activity_id == external_id,
                )
                .first()
            )
            if existing is not None:
                if sport_type_code and not existing.sport_type_code:
                    existing.sport_type_code = str(sport_type_code)
                    db.commit()
                if existing.canonical_activity_id is None:
                    peer = find_cross_provider_match(
                        db,
                        athlete_profile_id=athlete_profile_id,
                        activity_date=existing.activity_date or activity_date,
                        distance_m=float(existing.distance_m or distance_m),
                        moving_time_s=int(existing.moving_time_s or moving_time_s),
                        other_provider="strava",
                        exclude_id=existing.id,
                    )
                    if peer is not None:
                        canonical, duplicate = choose_canonical(existing, peer)
                        if link_duplicate(db, canonical, duplicate):
                            db.commit()
            skipped += 1
            continue

        record = Activity(
            athlete_profile_id=athlete_profile_id,
            provider=PROVIDER,
            external_activity_id=external_id,
            strava_activity_id=None,
            canonical_activity_id=None,
            name=str(name),
            activity_date=activity_date,
            distance_m=float(distance_m),
            moving_time_s=int(moving_time_s),
            average_heartrate=avg_hr,
            max_heartrate=None,
            sport_type=str(sport_type) if sport_type is not None else None,
            sport_type_code=str(sport_type_code) if sport_type_code else None,
            points_file_path=None,
            source_fit_file=f"coros_api:{external_id}",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        link_new_activity_to_peer(db, record)
        db.refresh(record)
        imported += 1
        recent_for_fit.append((external_id, record))

    # Selective FIT download for most recent activities within daily quota
    from app.services.coros_fit import attach_coros_fit_to_activity, remaining_fit_quota

    remaining = remaining_fit_quota(connection)
    fit_targets = recent_for_fit[-COROS_FIT_RECENT_LIMIT:]
    for external_id, activity in fit_targets:
        if remaining <= 0:
            break
        if activity.points_file_path:
            continue
        try:
            result = attach_coros_fit_to_activity(client, db, connection, activity)
            if result.get("ok") and not result.get("skipped"):
                remaining = remaining_fit_quota(connection)
            elif not result.get("ok"):
                status = get_sync_status(athlete_profile_id)
                errors = list(status.get("errors") or [])
                errors.append(f"FIT {external_id}: {result.get('reason')}")
                _set_status(athlete_profile_id, errors=errors[-20:])
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            status = get_sync_status(athlete_profile_id)
            errors = list(status.get("errors") or [])
            errors.append(f"FIT {external_id}: {exc}")
            _set_status(athlete_profile_id, errors=errors[-20:])

    # Sport-specific detail (laps / workout structure) for recent activities.
    try:
        from app.services.activity_detail import enrich_recent_activities_missing_detail

        detail_result = enrich_recent_activities_missing_detail(
            db,
            athlete_profile_id,
            client=client,
            limit=15,
        )
        if detail_result.get("errors"):
            status = get_sync_status(athlete_profile_id)
            errors = list(status.get("errors") or [])
            errors.extend(
                f"detail: {err}" for err in detail_result["errors"]
            )
            _set_status(athlete_profile_id, errors=errors[-20:])
    except Exception as exc:  # noqa: BLE001
        status = get_sync_status(athlete_profile_id)
        errors = list(status.get("errors") or [])
        errors.append(f"detail enrich: {exc}")
        _set_status(athlete_profile_id, errors=errors[-20:])

    return imported, skipped


def _fit_backfill_step(
    client: CorosMcpClient,
    db: Session,
    athlete_profile_id: int,
    connection: ProviderConnection,
) -> int:
    from app.services.coros_fit import backfill_coros_fit_for_athlete

    result = backfill_coros_fit_for_athlete(
        db,
        athlete_profile_id,
        client=client,
        connection=connection,
    )
    if result.get("errors"):
        status = get_sync_status(athlete_profile_id)
        errors = list(status.get("errors") or [])
        errors.extend(result["errors"])
        _set_status(athlete_profile_id, errors=errors[-20:])
    return int(result.get("filled") or 0)


def sync_all_for_athlete(db: Session, athlete_profile_id: int) -> dict[str, Any]:
    connection = get_coros_connection(db, athlete_profile_id)
    if connection is None:
        raise CorosMcpError("No COROS connection found for this athlete.")

    # Do not reset progress / clear another in-flight sync's lock.
    if not _claim_sync(athlete_profile_id, total=5):
        raise CorosSyncAlreadyRunning(
            "A COROS sync is already running for this athlete."
        )

    client = _client_for_connection(db, connection)
    imported_total = 0
    skipped_total = 0
    errors: list[str] = []

    try:
        client.initialize()
        try:
            user_info = client.call_tool("queryUserInfo", {})
            if isinstance(user_info, dict):
                external_id = (
                    user_info.get("userId")
                    or user_info.get("id")
                    or user_info.get("openId")
                )
                if external_id:
                    connection.external_user_id = str(external_id)
                connection.meta_json = json.dumps(
                    {
                        **(json.loads(connection.meta_json) if connection.meta_json else {}),
                        "user_info": user_info,
                    },
                    default=str,
                )[:20000]
                db.commit()
        except CorosMcpError as exc:
            errors.append(f"queryUserInfo: {exc}")

        steps = [
            ("health", lambda: sync_health_metrics(client, db, athlete_profile_id)),
            ("fitness", lambda: sync_fitness_and_recovery(client, db, athlete_profile_id)),
            ("load", lambda: sync_training_load(client, db, athlete_profile_id)),
            ("schedule", lambda: sync_schedule(client, db, athlete_profile_id)),
            (
                "activities",
                lambda: sync_activities(client, db, athlete_profile_id, connection),
            ),
            ("devices", lambda: _sync_devices_step(client, db, athlete_profile_id)),
            ("cycle", lambda: _sync_cycle_step(client, db, athlete_profile_id)),
            ("dedupe", lambda: backfill_athlete_duplicates(db, athlete_profile_id)["linked"]),
            (
                "schedule_complete",
                lambda: match_schedule_completions(db, athlete_profile_id)["linked"],
            ),
            ("fit_backfill", lambda: _fit_backfill_step(client, db, athlete_profile_id, connection)),
        ]
        _set_status(athlete_profile_id, total=len(steps))
        for index, (label, fn) in enumerate(steps, start=1):
            try:
                result = fn()
                if isinstance(result, tuple):
                    imported_total += result[0]
                    skipped_total += result[1]
                elif isinstance(result, int):
                    imported_total += result
                elif result is not None:
                    imported_total += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: {exc}")
            _set_status(
                athlete_profile_id,
                processed=index,
                imported=imported_total,
                skipped=skipped_total,
                errors=errors[-20:],
            )

        connection.last_synced_at = datetime.utcnow()
        db.commit()
    finally:
        _set_status(
            athlete_profile_id,
            running=False,
            imported=imported_total,
            skipped=skipped_total,
            errors=errors[-20:],
        )

    return get_sync_status(athlete_profile_id)


def sync_in_background(athlete_profile_id: int) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        sync_all_for_athlete(db, athlete_profile_id)
        # COROS often lands before Strava for the same workout. Pull Strava next
        # so the twin activity (with streams) is imported and deduped.
        try:
            from app.services.strava_sync import try_start_strava_sync

            outcome = try_start_strava_sync(db, athlete_profile_id, inline=True)
            if outcome.get("skipped") and outcome.get("reason") == "already_running":
                errors = list(get_sync_status(athlete_profile_id).get("errors") or [])
                errors.append(
                    "post-coros strava sync: skipped because a Strava sync is already running."
                )
                _set_status(athlete_profile_id, errors=errors[-20:])
        except Exception as strava_exc:  # noqa: BLE001
            errors = list(get_sync_status(athlete_profile_id).get("errors") or [])
            errors.append(f"post-coros strava sync: {strava_exc}")
            _set_status(athlete_profile_id, errors=errors[-20:])
    except CorosSyncAlreadyRunning:
        # Another job owns the slot — never clear running=True for that athlete.
        status = get_sync_status(athlete_profile_id)
        errors = list(status.get("errors") or [])
        errors.append("COROS sync skipped: already running for this athlete.")
        _set_status(athlete_profile_id, errors=errors[-20:])
    except Exception as exc:  # noqa: BLE001
        _set_status(
            athlete_profile_id,
            running=False,
            errors=[str(exc)],
        )
    finally:
        db.close()


def _sync_devices_step(client: CorosMcpClient, db: Session, athlete_profile_id: int) -> int:
    from app.services.coros_metrics import sync_devices

    return sync_devices(client, db, athlete_profile_id)


def _sync_cycle_step(client: CorosMcpClient, db: Session, athlete_profile_id: int) -> int:
    from app.services.coros_metrics import sync_cycle_snapshot

    return 1 if sync_cycle_snapshot(client, db, athlete_profile_id) else 0
