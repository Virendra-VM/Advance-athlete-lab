"""Detect threshold tests and race efforts that can update physiology anchors."""

from __future__ import annotations

from typing import Any

from app.models import Activity
from app.services.activity_detail import activity_sport_family, parse_activity_detail
from app.services.session_telemetry import (
    _best_20min_from_laps,
    _column_values,
    _looks_like_ride,
    _to_1hz,
    best_rolling_mean,
    estimate_ftp_watts,
    load_stream_frame,
)


def _round(value: float | None, places: int = 0) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _test_name_hints(name: str | None) -> bool:
    blob = (name or "").lower()
    return any(
        hint in blob
        for hint in (
            "test",
            "threshold",
            "lthr",
            "ftp",
            "20 min",
            "20min",
            "30 min",
            "30min",
            "time trial",
            "tt ",
        )
    )


def _avg_power_from_activity(activity: Activity) -> float | None:
    detail = parse_activity_detail(activity) or {}
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else detail
    for key in ("avg_power", "average_power", "normalized_power"):
        value = summary.get(key) if isinstance(summary, dict) else None
        if value and float(value) > 50:
            return float(value)
    frame = load_stream_frame(activity)
    if frame is None:
        return None
    power = _column_values(frame, "power")
    values = [float(v) for v in power if v is not None and float(v) > 30]
    if len(values) < 300:
        return None
    return sum(values) / len(values)


def _best_hr_window(activity: Activity, window_s: int = 20 * 60) -> float | None:
    detail = parse_activity_detail(activity) or {}
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    rows: list[tuple[int, float]] = []
    for lap in laps:
        duration = lap.get("duration_s") or 0
        hr = lap.get("avg_hr") or lap.get("average_heartrate")
        if duration and hr:
            rows.append((int(duration), float(hr)))
    if rows:
        best: float | None = None
        for start in range(len(rows)):
            total_s = 0
            weighted = 0.0
            for duration, hr in rows[start:]:
                total_s += duration
                weighted += duration * hr
                if total_s >= int(window_s * 0.9):
                    mean = weighted / total_s
                    if best is None or mean > best:
                        best = mean
                    break
        if best:
            return _round(best)

    frame = load_stream_frame(activity)
    if frame is None:
        return None
    elapsed = [float(v) for v in frame["elapsed_s"].tolist()]
    hr = _column_values(frame, "heartrate")
    series = _to_1hz(elapsed, hr)
    return best_rolling_mean(series, window_s)


def detect_lthr_test(activity: Activity) -> dict[str, Any] | None:
    family = activity_sport_family(activity.sport_type)
    if family not in {"run", "trail"}:
        return None
    minutes = (activity.moving_time_s or 0) / 60.0
    hinted = _test_name_hints(activity.name)
    candidate_hr: float | None = None
    confidence = "medium"
    reason = ""

    if 18 <= minutes <= 26 and activity.average_heartrate and activity.average_heartrate >= 130:
        candidate_hr = float(activity.average_heartrate)
        confidence = "high" if 19 <= minutes <= 22 else "medium"
        reason = f"{minutes:.0f}-min steady run average HR"
    else:
        candidate_hr = _best_hr_window(activity)
        if candidate_hr and (hinted or 35 <= minutes <= 75):
            confidence = "high" if hinted else "medium"
            reason = "Best ~20-min HR block from laps/streams"

    if not candidate_hr or candidate_hr < 120 or candidate_hr > 210:
        return None
    if not hinted and minutes < 35:
        return None

    return {
        "id": f"lthr-{activity.id}",
        "kind": "lthr_test",
        "field": "lthr_bpm",
        "value": _round(candidate_hr),
        "confidence": confidence,
        "reason": reason,
        "activity_id": activity.id,
        "activity_name": activity.name,
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
    }


def detect_ftp_test(activity: Activity) -> dict[str, Any] | None:
    if not _looks_like_ride(activity.sport_type):
        return None
    minutes = (activity.moving_time_s or 0) / 60.0
    hinted = _test_name_hints(activity.name)
    candidate: float | None = None
    confidence = "medium"
    reason = ""

    if 28 <= minutes <= 38:
        avg_power = _avg_power_from_activity(activity)
        if avg_power and avg_power >= 80:
            candidate = _round(avg_power * 0.95 if minutes >= 29 else avg_power)
            confidence = "high" if 29 <= minutes <= 32 else "medium"
            reason = f"{minutes:.0f}-min ride average power × 0.95"
    if candidate is None:
        candidate = estimate_ftp_watts([activity], use_streams=True)
        if candidate:
            confidence = "medium" if hinted else "low"
            reason = "Best 20-min power × 0.95 from ride streams/laps"

    lap_candidate = _best_20min_from_laps(activity)
    if lap_candidate and (candidate is None or lap_candidate * 0.95 > candidate):
        candidate = _round(lap_candidate * 0.95)
        confidence = "high" if hinted else "medium"
        reason = "Best 20-min lap power × 0.95"

    if not candidate or candidate < 80 or candidate > 500:
        return None
    if confidence == "low" and not hinted:
        return None

    return {
        "id": f"ftp-{activity.id}",
        "kind": "ftp_test",
        "field": "ftp_watts",
        "value": candidate,
        "confidence": confidence,
        "reason": reason,
        "activity_id": activity.id,
        "activity_name": activity.name,
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
    }


def threshold_pace_from_race(distance_m: float, time_seconds: float) -> float | None:
    """Convert race time to an approximate threshold pace (sec/km)."""
    if distance_m <= 0 or time_seconds <= 0:
        return None
    km = distance_m / 1000.0
    race_pace = time_seconds / km
    if distance_m >= 40000:
        multiplier = 0.92
    elif distance_m >= 20000:
        multiplier = 0.94
    elif distance_m >= 9000:
        multiplier = 1.03
    elif distance_m >= 4500:
        multiplier = 1.08
    else:
        multiplier = 1.02
    return _round(race_pace * multiplier, 1)


def detect_race_threshold_pace(activity: Activity) -> dict[str, Any] | None:
    family = activity_sport_family(activity.sport_type)
    if family not in {"run", "trail"}:
        return None
    distance_m = float(activity.distance_m or 0)
    if distance_m < 4500:
        return None
    time_s = float(activity.moving_time_s or 0)
    if time_s <= 0:
        return None
    pace = threshold_pace_from_race(distance_m, time_s)
    if not pace:
        return None
    name = (activity.name or "").lower()
    hinted = any(h in name for h in ("race", "10k", "5k", "half", "marathon", "trials"))
    confidence = "medium" if hinted or distance_m >= 9000 else "low"
    if confidence == "low":
        return None
    return {
        "id": f"pace-{activity.id}",
        "kind": "race_pace",
        "field": "threshold_pace_sec_per_km",
        "value": pace,
        "confidence": confidence,
        "reason": f"Race effort {distance_m / 1000:.1f} km → estimated threshold pace",
        "activity_id": activity.id,
        "activity_name": activity.name,
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
    }


def detect_test_suggestions(activities: list[Activity]) -> list[dict[str, Any]]:
    """Scan recent activities for threshold tests and race-pace anchors."""
    suggestions: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    rank = {"high": 3, "medium": 2, "low": 1}

    for activity in activities:
        for detector in (detect_lthr_test, detect_ftp_test, detect_race_threshold_pace):
            hit = detector(activity)
            if not hit:
                continue
            field = hit["field"]
            existing = next((row for row in suggestions if row["field"] == field), None)
            if existing is None:
                suggestions.append(hit)
                seen_fields.add(field)
                continue
            if rank.get(hit["confidence"], 0) > rank.get(existing["confidence"], 0):
                suggestions = [row for row in suggestions if row["field"] != field]
                suggestions.append(hit)

    suggestions.sort(
        key=lambda row: (
            rank.get(row.get("confidence"), 0),
            row.get("activity_date") or "",
        ),
        reverse=True,
    )
    return suggestions


def threshold_pace_from_event_result(event, result_metric: str | None) -> float | None:
    """Derive threshold pace from a completed race event result."""
    from app.services.b_race_calibration import infer_race_distance_meters, parse_duration_seconds

    result_text = result_metric or getattr(event, "result_metric", None)
    time_s = parse_duration_seconds(result_text)
    if time_s is None:
        return None
    distance_m = infer_race_distance_meters(event)
    if distance_m is None and getattr(event, "distance_m", None):
        distance_m = float(event.distance_m)
    if not distance_m:
        return None
    return threshold_pace_from_race(distance_m, time_s)
