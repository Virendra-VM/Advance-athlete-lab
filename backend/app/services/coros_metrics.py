"""Build metric series for charts and optional MCP history backfill."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    CorosCycleSnapshot,
    CorosDevice,
    DailyHealthMetric,
    FitnessAssessment,
    TrainingLoadSnapshot,
)
from app.services.coros_mcp import CorosMcpError
from app.services.coros_sync import (
    PROVIDER,
    _client_for_connection,
    get_coros_connection,
    sync_health_metrics,
)


RANGE_DAYS = {
    "7d": 7,
    "4w": 28,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    # MCP health tools accept days up to ~365; "all" means full cached history.
    "all": 365,
}


def _parse_race_preds(raw: str | None) -> dict[str, Any]:
    """Parse cached race-prediction JSON; never raise on corrupt rows."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def range_to_dates(range_key: str) -> tuple[date, date]:
    days = RANGE_DAYS.get(range_key, 28)
    end = date.today()
    start = end - timedelta(days=days)
    return start, end


def _clamp_series_to_data(series: dict[str, Any], *, range_key: str | None = None) -> dict[str, Any]:
    """For 1Y / All, start the chart at the first real sample (not empty lead-in before data)."""
    if range_key not in {"all", "1y"}:
        return series
    points = [p for p in (series.get("points") or []) if p.get("value") is not None and p.get("date")]
    if not points:
        return series
    try:
        earliest = min(date.fromisoformat(str(p["date"])[:10]) for p in points)
        latest = max(date.fromisoformat(str(p["date"])[:10]) for p in points)
    except ValueError:
        return series
    series["from_date"] = earliest
    # All can end on last sample day; 1Y keeps through today within the lookback window.
    if range_key == "all":
        series["to_date"] = max(latest, date.today())
    else:
        series["to_date"] = max(series.get("to_date") or date.today(), date.today())
    return series
def build_metric_series(
    db: Session,
    athlete_profile_id: int,
    metric: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    end = to_date or date.today()
    start = from_date or (end - timedelta(days=28))
    metric = metric.lower()
    points: list[dict[str, Any]] = []
    latest: dict[str, Any] = {}

    if metric in {
        "sleep",
        "hrv",
        "stress",
        "rhr",
        "steps",
        "calories",
        "avg_hr",
        "daily",
    }:
        rows = (
            db.query(DailyHealthMetric)
            .filter(
                DailyHealthMetric.athlete_profile_id == athlete_profile_id,
                DailyHealthMetric.provider == PROVIDER,
                DailyHealthMetric.metric_date >= start,
                DailyHealthMetric.metric_date <= end,
            )
            .order_by(DailyHealthMetric.metric_date.asc())
            .all()
        )
        field_map = {
            "sleep": ("sleep_score", "sleep_duration_min"),
            "hrv": ("hrv", None),
            "stress": ("stress", None),
            "rhr": ("resting_heart_rate", None),
            "steps": ("steps", "calories"),
            "calories": ("calories", "steps"),
            "avg_hr": ("avg_heart_rate", None),
            "daily": ("steps", "calories"),
        }
        primary, secondary = field_map[metric]
        for row in rows:
            value = getattr(row, primary)
            sec = getattr(row, secondary) if secondary else None
            points.append(
                {
                    "date": row.metric_date.isoformat(),
                    "value": float(value) if value is not None else None,
                    "secondary": float(sec) if sec is not None else None,
                    "label": row.hrv_assessment if metric == "hrv" else None,
                    "meta": {
                        "deep_sleep_pct": row.deep_sleep_pct,
                        "light_sleep_pct": row.light_sleep_pct,
                        "rem_sleep_pct": row.rem_sleep_pct,
                        "deep_sleep_min": getattr(row, "deep_sleep_min", None),
                        "light_sleep_min": getattr(row, "light_sleep_min", None),
                        "rem_sleep_min": getattr(row, "rem_sleep_min", None),
                        "awake_min": row.awake_min,
                        "awake_count": getattr(row, "awake_count", None),
                        "main_sleep_min": getattr(row, "main_sleep_min", None),
                        "hrv": row.hrv,
                        "hrv_assessment": row.hrv_assessment,
                        "bedtime": row.bedtime,
                        "wake_time": row.wake_time,
                        "nap_duration_min": row.nap_duration_min,
                        "sleep_avg_hr": row.sleep_avg_hr,
                        "sleep_duration_min": row.sleep_duration_min,
                        "sleep_score": row.sleep_score,
                    },
                }
            )
        if rows:
            last = rows[-1]
            latest = {
                "date": last.metric_date.isoformat(),
                "sleep_score": last.sleep_score,
                "sleep_duration_min": last.sleep_duration_min,
                "deep_sleep_pct": last.deep_sleep_pct,
                "light_sleep_pct": last.light_sleep_pct,
                "rem_sleep_pct": last.rem_sleep_pct,
                "deep_sleep_min": getattr(last, "deep_sleep_min", None),
                "light_sleep_min": getattr(last, "light_sleep_min", None),
                "rem_sleep_min": getattr(last, "rem_sleep_min", None),
                "awake_min": last.awake_min,
                "bedtime": last.bedtime,
                "wake_time": last.wake_time,
                "nap_duration_min": last.nap_duration_min,
                "sleep_avg_hr": last.sleep_avg_hr,
                "hrv": last.hrv,
                "hrv_assessment": last.hrv_assessment,
                "stress": last.stress,
                "resting_heart_rate": last.resting_heart_rate,
                "steps": last.steps,
                "calories": last.calories,
                "avg_heart_rate": last.avg_heart_rate,
            }

    elif metric in {"recovery", "vo2max", "fitness"}:
        rows = (
            db.query(FitnessAssessment)
            .filter(
                FitnessAssessment.athlete_profile_id == athlete_profile_id,
                FitnessAssessment.provider == PROVIDER,
                FitnessAssessment.snapshot_at
                >= datetime.combine(start, datetime.min.time()),
                FitnessAssessment.snapshot_at
                <= datetime.combine(end, datetime.max.time().replace(microsecond=0)),
            )
            .order_by(FitnessAssessment.snapshot_at.asc())
            .all()
        )
        # One point per calendar day (COROS only returns the live snapshot, not a history API).
        by_day: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = row.recovery_pct if metric == "recovery" else row.vo2max
            day_key = row.snapshot_at.date().isoformat()
            by_day[day_key] = {
                "date": day_key,
                "value": float(value) if value is not None else None,
                "secondary": row.running_performance,
                "label": row.recovery_level if metric == "recovery" else row.threshold_pace,
                "meta": {
                    "threshold_pace": row.threshold_pace,
                    "recovery_pct": row.recovery_pct,
                    "recovery_level": row.recovery_level,
                    "race_preds": _parse_race_preds(row.race_preds_json),
                },
            }
        points = [by_day[k] for k in sorted(by_day.keys())]
        if rows:
            last = rows[-1]
            latest = {
                "vo2max": last.vo2max,
                "threshold_pace": last.threshold_pace,
                "running_performance": last.running_performance,
                "recovery_pct": last.recovery_pct,
                "recovery_level": last.recovery_level,
                "recovery_full_at": last.recovery_full_at,
                "race_predictions": _parse_race_preds(last.race_preds_json),
            }

    elif metric in {"load", "training_load"}:
        # Prefer the newest snapshot's daily comments (COROS returns ~7 days of load history).
        latest_row = (
            db.query(TrainingLoadSnapshot)
            .filter(
                TrainingLoadSnapshot.athlete_profile_id == athlete_profile_id,
                TrainingLoadSnapshot.provider == PROVIDER,
            )
            .order_by(TrainingLoadSnapshot.snapshot_at.desc())
            .first()
        )
        rows = [latest_row] if latest_row else []
        for row in rows:
            comments = []
            if row.daily_comments_json:
                try:
                    comments = json.loads(row.daily_comments_json)
                except json.JSONDecodeError:
                    comments = []
            if isinstance(comments, list) and comments:
                for comment in comments:
                    if not isinstance(comment, dict):
                        continue
                    day = comment.get("date")
                    if not day:
                        continue
                    try:
                        day_date = date.fromisoformat(str(day)[:10])
                    except ValueError:
                        continue
                    if day_date < start or day_date > end:
                        continue
                    points.append(
                        {
                            "date": day_date.isoformat(),
                            "value": comment.get("load_ratio"),
                            "secondary": comment.get("short_load"),
                            "label": comment.get("comment"),
                            "meta": {
                                "short_load": comment.get("short_load"),
                                "long_load": comment.get("long_load"),
                            },
                        }
                    )
            else:
                points.append(
                    {
                        "date": row.snapshot_at.date().isoformat(),
                        "value": row.load_ratio,
                        "secondary": row.short_load,
                        "label": None,
                        "meta": {
                            "short_load": row.short_load,
                            "long_load": row.long_load,
                        },
                    }
                )
        dedup: dict[str, dict] = {}
        for point in points:
            dedup[point["date"]] = point
        points = [dedup[k] for k in sorted(dedup.keys())]
        if latest_row:
            latest = {
                "short_load": latest_row.short_load,
                "long_load": latest_row.long_load,
                "load_ratio": latest_row.load_ratio,
            }

    else:
        raise ValueError(f"Unsupported metric: {metric}")

    return {
        "metric": metric,
        "from_date": start,
        "to_date": end,
        "points": points,
        "latest": latest,
        "source": "cache",
    }


HEALTH_METRICS = {
    "sleep",
    "hrv",
    "stress",
    "rhr",
    "steps",
    "calories",
    "avg_hr",
    "daily",
}
SNAPSHOT_METRICS = {"recovery", "vo2max", "fitness", "load", "training_load"}


def _series_coverage_gap_days(series: dict[str, Any], start: date) -> int | None:
    """Days between requested start and earliest cached point, or None if empty."""
    points = series.get("points") or []
    dated = [p.get("date") for p in points if p.get("date")]
    if not dated:
        return None
    try:
        earliest = min(date.fromisoformat(str(d)[:10]) for d in dated)
    except ValueError:
        return None
    return max((earliest - start).days, 0)


def cache_covers_range(series: dict[str, Any], start: date, *, slack_days: int = 3) -> bool:
    """True when cached points already reach near the requested window start."""
    points = series.get("points") or []
    if not points:
        return False
    gap = _series_coverage_gap_days(series, start)
    if gap is None:
        return False
    return gap <= slack_days


def ensure_metric_series(
    db: Session,
    athlete_profile_id: int,
    metric: str,
    range_key: str = "4w",
    from_date: date | None = None,
    to_date: date | None = None,
    *,
    force_backfill: bool = False,
) -> dict[str, Any]:
    """
    Return series for the selected window. When the Postgres cache does not cover
    the requested start (common after a 28-day default sync), pull a wider COROS
    MCP range for health metrics before responding.
    """
    metric = metric.lower()
    if from_date is None or to_date is None:
        start, end = range_to_dates(range_key)
        from_date = from_date or start
        to_date = to_date or end

    series = build_metric_series(db, athlete_profile_id, metric, from_date, to_date)
    needs_backfill = force_backfill or not cache_covers_range(series, from_date)

    # Snapshot metrics only accumulate on sync — still refresh current values when forced.
    if metric in SNAPSHOT_METRICS and not force_backfill:
        return _clamp_series_to_data(series, range_key=range_key)

    if not needs_backfill:
        return _clamp_series_to_data(series, range_key=range_key)

    connection = get_coros_connection(db, athlete_profile_id)
    if connection is None:
        return _clamp_series_to_data(series, range_key=range_key)

    try:
        client = _client_for_connection(db, connection)
        client.initialize()
        lookback = min(max((to_date - from_date).days, 7), 365)

        if metric in HEALTH_METRICS:
            sync_health_metrics(client, db, athlete_profile_id, lookback_days=lookback)
        elif metric in SNAPSHOT_METRICS:
            from app.services.coros_sync import sync_fitness_and_recovery, sync_training_load

            sync_fitness_and_recovery(client, db, athlete_profile_id)
            sync_training_load(client, db, athlete_profile_id)
        else:
            return _clamp_series_to_data(series, range_key=range_key)

        # After backfill, for "all" rebuild from earliest stored point.
        if range_key == "all":
            from_date = date.today() - timedelta(days=3650)
        series = build_metric_series(db, athlete_profile_id, metric, from_date, to_date)
        series["source"] = "backfill"
    except CorosMcpError:
        # Fall back to whatever is already cached for the window.
        series["source"] = series.get("source") or "cache"
    return _clamp_series_to_data(series, range_key=range_key)

def backfill_metric_history(
    db: Session,
    athlete_profile_id: int,
    metric: str,
    range_key: str = "3m",
) -> dict[str, Any]:
    connection = get_coros_connection(db, athlete_profile_id)
    if connection is None:
        raise CorosMcpError("COROS is not connected.")

    return ensure_metric_series(
        db,
        athlete_profile_id,
        metric,
        range_key=range_key,
        force_backfill=True,
    )


def sync_devices(client, db: Session, athlete_profile_id: int) -> int:
    try:
        payload = client.call_tool("queryDevices", {})
    except CorosMcpError:
        return 0

    text = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    imported = 0
    # Parse simple device blocks if text, else list
    devices: list[dict[str, Any]] = []
    if isinstance(payload, list):
        devices = [d for d in payload if isinstance(d, dict)]
    elif isinstance(payload, dict):
        data = payload.get("devices") or payload.get("data") or [payload]
        if isinstance(data, list):
            devices = [d for d in data if isinstance(d, dict)]
    else:
        blocks = re.split(r"\n(?=\d+\.\s+|Device)", text)
        for block in blocks:
            device_id = None
            m = re.search(r"(?:Device ID|deviceId|ID):\s*([A-Za-z0-9_-]+)", block, re.I)
            if m:
                device_id = m.group(1)
            name_m = re.search(r"(?:Name|Custom Name):\s*(.+)", block, re.I)
            fw_m = re.search(r"(?:Firmware|firmwareType):\s*(.+)", block, re.I)
            if device_id or name_m:
                devices.append(
                    {
                        "device_id": device_id or (name_m.group(1).strip() if name_m else "unknown"),
                        "name": name_m.group(1).strip() if name_m else None,
                        "firmware": fw_m.group(1).strip() if fw_m else None,
                        "raw": {"text": block[:2000]},
                    }
                )

    for device in devices:
        device_id = str(device.get("device_id") or device.get("id") or device.get("deviceId") or "")
        if not device_id:
            continue
        row = (
            db.query(CorosDevice)
            .filter(
                CorosDevice.athlete_profile_id == athlete_profile_id,
                CorosDevice.device_id == device_id,
            )
            .first()
        )
        if row is None:
            row = CorosDevice(
                athlete_profile_id=athlete_profile_id,
                device_id=device_id,
            )
            db.add(row)
        row.name = device.get("name") or device.get("customName") or row.name
        row.firmware = (
            device.get("firmware")
            or device.get("firmwareType")
            or device.get("firmware_type")
            or row.firmware
        )
        row.raw_json = json.dumps(device.get("raw") or device, default=str)[:20000]
        row.updated_at = datetime.utcnow()
        imported += 1
    db.commit()
    return imported


def sync_cycle_snapshot(client, db: Session, athlete_profile_id: int) -> bool:
    try:
        payload = client.call_tool("queryMenstruationCycles", {})
    except CorosMcpError:
        return False
    if isinstance(payload, str) and (
        "no data" in payload.lower() or "not found" in payload.lower()
    ):
        return False
    row = CorosCycleSnapshot(
        athlete_profile_id=athlete_profile_id,
        snapshot_at=datetime.utcnow(),
        raw_json=json.dumps(payload, default=str)[:20000]
        if not isinstance(payload, str)
        else payload[:20000],
    )
    db.add(row)
    db.commit()
    return True
