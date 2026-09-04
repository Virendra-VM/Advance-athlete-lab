"""Fetch and normalize sport-specific activity detail from COROS + Strava."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity
from app.services.activity_dedupe import sport_family as resolve_sport_family
from app.services.coros_mcp import CorosMcpClient, CorosMcpError

DETAIL_TTL = timedelta(hours=24)
DETAIL_JSON_MAX = 120_000
RAW_SNIPPET_MAX = 8_000
RECENT_ENRICH_LIMIT = 15


def activity_sport_family(sport_type: str | None) -> str:
    family = resolve_sport_family(sport_type)
    return family or "other"


def parse_activity_detail(activity: Activity) -> dict[str, Any] | None:
    if not activity.detail_json:
        return None
    try:
        data = json.loads(activity.detail_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


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


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    # Pace like 5:30 /km
    if ":" in text and "/" not in text[:3]:
        parts = text.split(":")
        try:
            if len(parts) == 2:
                return float(parts[0]) + float(parts[1]) / 60.0
            if len(parts) == 3:
                return float(parts[0]) * 60 + float(parts[1]) + float(parts[2]) / 60.0
        except ValueError:
            pass
    try:
        return float(text)
    except (TypeError, ValueError):
        import re

        match = re.search(r"-?[\d.]+", text)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _first(*values: Any) -> Any:
    for value in values:
        if value is None or value == "":
            continue
        return value
    return None


def _dig(payload: Any, *keys: str) -> Any:
    current = _parse_json_maybe(payload)
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_list(payload: Any) -> list[Any]:
    payload = _parse_json_maybe(payload)
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in (
            "data",
            "list",
            "records",
            "items",
            "laps",
            "segments",
            "exercises",
            "sets",
            "workoutSteps",
            "steps",
            "details",
        ):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


def _truncate_raw(value: Any) -> Any:
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= RAW_SNIPPET_MAX:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text[:RAW_SNIPPET_MAX] + "…"


def resolve_coros_detail_source(
    db: Session, activity: Activity
) -> tuple[Activity, str] | None:
    """Return (canonical activity to update, coros external id) or None."""
    if activity.provider == "coros":
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
                Activity.provider == "coros",
                Activity.canonical_activity_id == activity.id,
            )
            .order_by(Activity.id.desc())
            .first()
        )
        if twin is None:
            return None
        return activity, str(twin.external_activity_id)

    return None


def resolve_strava_activity_id(db: Session, activity: Activity) -> int | None:
    if activity.provider == "strava" and activity.strava_activity_id:
        return int(activity.strava_activity_id)
    if activity.provider == "strava" and activity.external_activity_id:
        try:
            return int(activity.external_activity_id)
        except (TypeError, ValueError):
            pass

    twin = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == activity.athlete_profile_id,
            Activity.provider == "strava",
            Activity.canonical_activity_id == activity.id,
        )
        .order_by(Activity.id.desc())
        .first()
    )
    if twin is not None:
        if twin.strava_activity_id:
            return int(twin.strava_activity_id)
        try:
            return int(twin.external_activity_id)
        except (TypeError, ValueError):
            return None

    if activity.canonical_activity_id:
        parent = (
            db.query(Activity)
            .filter(Activity.id == activity.canonical_activity_id)
            .first()
        )
        if parent is not None and parent.provider == "strava":
            if parent.strava_activity_id:
                return int(parent.strava_activity_id)
            try:
                return int(parent.external_activity_id)
            except (TypeError, ValueError):
                return None
    return None


def _normalize_lap(
    item: Any, index: int, *, speed_in_mps: bool = False
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    distance_m = _to_float(
        _first(
            item.get("distance_m"),
            item.get("distance"),
            item.get("distanceMeters"),
            item.get("total_distance"),
            item.get("lapDistance"),
        )
    )
    # COROS sometimes returns km for distance when value is small.
    if distance_m is not None and 0 < distance_m < 200 and item.get("distance_m") is None:
        unit = str(item.get("unit") or item.get("distanceUnit") or "").lower()
        if unit in {"km", "kilometer", "kilometers"} or (
            distance_m < 80 and not unit.startswith("m")
        ):
            # Prefer meters if integer-like large; else treat small floats as km.
            if distance_m != int(distance_m) or distance_m < 50:
                distance_m = distance_m * 1000.0

    duration_s = _to_int(
        _first(
            item.get("duration_s"),
            item.get("moving_time"),
            item.get("lap_time"),
            item.get("lapTime"),
            item.get("time"),
            item.get("duration"),
            item.get("total_timer_time"),
        )
    )
    total_time_s = _to_int(
        _first(
            item.get("total_time_s"),
            item.get("elapsed_time"),
            item.get("totalTime"),
            item.get("total_elapsed_time"),
            item.get("cumulative_time"),
            item.get("totalTimerTime"),
        )
    )
    if total_time_s is None:
        total_time_s = duration_s

    avg_hr = _to_float(
        _first(
            item.get("avg_hr"),
            item.get("average_heartrate"),
            item.get("avgHeartRate"),
            item.get("average_heart_rate"),
            item.get("avgHr"),
        )
    )
    max_hr = _to_float(
        _first(
            item.get("max_hr"),
            item.get("max_heartrate"),
            item.get("maxHeartRate"),
            item.get("maxHr"),
        )
    )
    avg_pace = _to_float(
        _first(
            item.get("avg_pace"),
            item.get("average_pace"),
            item.get("pace"),
            item.get("avgPace"),
            item.get("pace_min_per_km"),
        )
    )
    avg_speed = _to_float(
        _first(
            item.get("avg_speed"),
            item.get("average_speed"),
            item.get("avgSpeed"),
            item.get("speed"),
        )
    )
    if avg_speed is not None and speed_in_mps:
        avg_speed = avg_speed * 3.6
    elif avg_speed is not None and distance_m and duration_s and duration_s > 0:
        # If value looks like m/s vs implied km/h, prefer implied.
        implied_kmh = (distance_m / duration_s) * 3.6
        if avg_speed < 25 and abs(implied_kmh - avg_speed * 3.6) < abs(implied_kmh - avg_speed):
            avg_speed = avg_speed * 3.6

    avg_power = _to_float(
        _first(
            item.get("avg_power"),
            item.get("average_watts"),
            item.get("average_power"),
            item.get("avgPower"),
            item.get("power"),
        )
    )
    normalized_power = _to_float(
        _first(
            item.get("normalized_power"),
            item.get("normalizedPower"),
            item.get("np"),
            item.get("NP"),
            item.get("weighted_average_watts"),
        )
    )
    avg_cadence = _to_float(
        _first(
            item.get("avg_cadence"),
            item.get("average_cadence"),
            item.get("avgCadence"),
            item.get("cadence"),
        )
    )
    effort_accuracy = _first(
        item.get("effort_accuracy"),
        item.get("effortAccuracy"),
        item.get("effort"),
        item.get("accuracy"),
    )
    if effort_accuracy is not None and not isinstance(effort_accuracy, str):
        effort_accuracy = str(effort_accuracy)

    label = _first(
        item.get("label"),
        item.get("name"),
        item.get("lapName"),
        item.get("title"),
        f"Lap {index}",
    )
    return {
        "index": index,
        "label": str(label) if label is not None else f"Lap {index}",
        "distance_m": distance_m,
        "duration_s": duration_s,
        "total_time_s": total_time_s,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "avg_pace": avg_pace,
        "avg_speed": avg_speed,
        "avg_power": avg_power,
        "normalized_power": normalized_power,
        "avg_cadence": avg_cadence,
        "effort_accuracy": effort_accuracy,
        "calories": _to_float(_first(item.get("calories"), item.get("calorie"))),
        "stroke_count": _to_int(
            _first(item.get("stroke_count"), item.get("strokes"), item.get("strokeCount"))
        ),
        "swolf": _to_float(_first(item.get("swolf"), item.get("SWOLF"))),
    }


def _normalize_laps(payload: Any, *, speed_in_mps: bool = False) -> list[dict[str, Any]]:
    laps: list[dict[str, Any]] = []
    cumulative = 0
    for index, item in enumerate(_as_list(payload), start=1):
        row = _normalize_lap(item, index, speed_in_mps=speed_in_mps)
        if row is None:
            continue
        if row.get("total_time_s") is None and row.get("duration_s") is not None:
            cumulative += int(row["duration_s"])
            row["total_time_s"] = cumulative
        elif row.get("duration_s") is not None:
            cumulative = max(cumulative, int(row.get("total_time_s") or 0))
        laps.append(row)
    return laps


def _normalize_set(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        # Bare number → reps
        reps = _to_int(item)
        if reps is None:
            return None
        return {
            "index": index,
            "reps": reps,
            "weight_kg": None,
            "duration_s": None,
            "rest_s": None,
        }
    return {
        "index": index,
        "reps": _to_int(
            _first(item.get("reps"), item.get("rep"), item.get("target_value"), item.get("count"))
        ),
        "weight_kg": _to_float(
            _first(
                item.get("weight_kg"),
                item.get("weight"),
                item.get("load"),
                item.get("kg"),
            )
        ),
        "duration_s": _to_int(
            _first(
                item.get("duration_s"),
                item.get("duration"),
                item.get("time"),
                item.get("work_time"),
            )
        ),
        "rest_s": _to_int(
            _first(item.get("rest_s"), item.get("rest"), item.get("rest_seconds"), item.get("restTime"))
        ),
    }


def _normalize_exercise(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        if isinstance(item, str) and item.strip():
            return {"index": index, "name": item.strip(), "sets": []}
        return None

    name = _first(
        item.get("name"),
        item.get("exerciseName"),
        item.get("exercise_name"),
        item.get("title"),
        item.get("movement"),
        f"Exercise {index}",
    )
    sets_raw = _first(
        item.get("sets"),
        item.get("setList"),
        item.get("reps"),
        item.get("steps"),
    )
    sets: list[dict[str, Any]] = []
    if isinstance(sets_raw, list):
        for set_index, set_item in enumerate(sets_raw, start=1):
            normalized = _normalize_set(set_item, set_index)
            if normalized is not None:
                sets.append(normalized)
    elif sets_raw is not None and not isinstance(sets_raw, (dict, list)):
        # Single rep count on the exercise.
        normalized = _normalize_set({"reps": sets_raw}, 1)
        if normalized:
            sets.append(normalized)
    else:
        # Exercise itself may be a timed/rep set.
        single = _normalize_set(item, 1)
        if single and any(
            single.get(key) is not None for key in ("reps", "weight_kg", "duration_s")
        ):
            sets.append(single)

    return {
        "index": index,
        "name": str(name),
        "sets": sets,
    }


def _extract_exercises(payload: Any) -> list[dict[str, Any]]:
    payload = _parse_json_maybe(payload)
    candidates: list[Any] = []

    if isinstance(payload, dict):
        for key in (
            "exercises",
            "exerciseList",
            "workoutExercises",
            "strengthExercises",
            "workoutSteps",
            "steps",
            "sets",
            "structure",
            "workoutStructure",
        ):
            value = payload.get(key)
            if isinstance(value, list) and value:
                candidates = value
                break
        if not candidates:
            nested = _dig(payload, "data") or _dig(payload, "detail") or _dig(payload, "workout")
            if nested is not None and nested is not payload:
                return _extract_exercises(nested)
    elif isinstance(payload, list):
        candidates = payload

    exercises: list[dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        # Skip obvious lap-like rows when looking for strength.
        if isinstance(item, dict):
            keys = {str(k).lower() for k in item.keys()}
            if "distance" in keys and "exercise" not in keys and "reps" not in keys:
                continue
        row = _normalize_exercise(item, index)
        if row is not None:
            exercises.append(row)
    return exercises


def _extract_summary(payload: Any) -> dict[str, Any]:
    payload = _parse_json_maybe(payload)
    if not isinstance(payload, dict):
        return {}

    # Prefer nested summary/detail dicts when present.
    source = payload
    for key in ("summary", "detail", "data", "activity", "metrics"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            source = {**payload, **nested}
            break

    return {
        "calories": _to_float(
            _first(
                source.get("calories"),
                source.get("calorie"),
                source.get("totalCalories"),
                source.get("kilojoules"),
            )
        ),
        "elev_gain_m": _to_float(
            _first(
                source.get("elev_gain_m"),
                source.get("total_elevation_gain"),
                source.get("elevationGain"),
                source.get("elevGain"),
                source.get("ascent"),
            )
        ),
        "avg_pace": _to_float(
            _first(
                source.get("avg_pace"),
                source.get("average_pace"),
                source.get("pace"),
                source.get("avgPace"),
            )
        ),
        "avg_speed": _to_float(
            _first(
                source.get("avg_speed"),
                source.get("average_speed"),
                source.get("avgSpeed"),
                source.get("speed"),
            )
        ),
        "avg_cadence": _to_float(
            _first(
                source.get("avg_cadence"),
                source.get("average_cadence"),
                source.get("avgCadence"),
                source.get("cadence"),
            )
        ),
        "avg_power": _to_float(
            _first(
                source.get("avg_power"),
                source.get("average_watts"),
                source.get("weighted_average_watts"),
                source.get("avgPower"),
            )
        ),
        "max_power": _to_float(
            _first(source.get("max_power"), source.get("max_watts"), source.get("maxPower"))
        ),
        "avg_hr": _to_float(
            _first(
                source.get("avg_hr"),
                source.get("average_heartrate"),
                source.get("avgHeartRate"),
                source.get("avgHr"),
            )
        ),
        "max_hr": _to_float(
            _first(
                source.get("max_hr"),
                source.get("max_heartrate"),
                source.get("maxHeartRate"),
                source.get("maxHr"),
            )
        ),
        "pool_length_m": _to_float(
            _first(source.get("pool_length_m"), source.get("pool_length"), source.get("poolLength"))
        ),
        "stroke_count": _to_int(
            _first(source.get("stroke_count"), source.get("strokes"), source.get("totalStrokes"))
        ),
        "swolf": _to_float(_first(source.get("swolf"), source.get("SWOLF"))),
        "description": _first(source.get("description"), source.get("desc")),
    }


def _extract_zones(payload: Any) -> dict[str, list[Any]]:
    payload = _parse_json_maybe(payload)
    zones: dict[str, list[Any]] = {"hr": [], "power": []}
    if not isinstance(payload, dict):
        return zones

    hr = _first(
        payload.get("hr_zones"),
        payload.get("heartRateZones"),
        payload.get("hrZones"),
        _dig(payload, "zones", "hr"),
    )
    power = _first(
        payload.get("power_zones"),
        payload.get("powerZones"),
        _dig(payload, "zones", "power"),
    )
    if isinstance(hr, list):
        zones["hr"] = hr
    if isinstance(power, list):
        zones["power"] = power
    return zones


def _merge_summary(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    merged = dict(secondary or {})
    for key, value in (primary or {}).items():
        if value is not None and value != "":
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def build_normalized_detail(
    *,
    sport_type: str | None,
    coros_detail: Any = None,
    coros_laps: Any = None,
    strava_detail: Any = None,
    strava_laps: Any = None,
) -> dict[str, Any]:
    family = activity_sport_family(sport_type)
    sources: list[str] = []

    coros_summary = _extract_summary(coros_detail) if coros_detail is not None else {}
    strava_summary = _extract_summary(strava_detail) if strava_detail is not None else {}
    if coros_detail is not None:
        sources.append("coros")
    if strava_detail is not None or strava_laps:
        sources.append("strava")

    summary = _merge_summary(coros_summary, strava_summary)

    coros_lap_rows = _normalize_laps(coros_laps if coros_laps is not None else coros_detail)
    # If laps came from the same detail blob and look empty, try dedicated keys.
    if not coros_lap_rows and isinstance(coros_detail, dict):
        for key in ("laps", "lapList", "segments", "splits"):
            if coros_detail.get(key):
                coros_lap_rows = _normalize_laps(coros_detail.get(key))
                if coros_lap_rows:
                    break

    strava_lap_rows = _normalize_laps(strava_laps, speed_in_mps=True)
    laps = coros_lap_rows if coros_lap_rows else strava_lap_rows
    # Fill cumulative total_time when missing.
    running_total = 0
    for lap in laps:
        if lap.get("duration_s") is not None:
            running_total += int(lap["duration_s"])
            if lap.get("total_time_s") is None:
                lap["total_time_s"] = running_total

    exercises = _extract_exercises(coros_detail)
    if not exercises and family == "strength":
        # Sometimes structure lives under laps payload for strength.
        exercises = _extract_exercises(coros_laps)

    zones = _extract_zones(coros_detail)
    if not zones["hr"] and not zones["power"]:
        zones = _extract_zones(strava_detail)

    return {
        "family": family,
        "sources": sources,
        "summary": summary,
        "laps": laps,
        "exercises": exercises,
        "zones": zones,
        "raw": {
            "coros_detail": _truncate_raw(coros_detail) if coros_detail is not None else None,
            "coros_laps": _truncate_raw(coros_laps) if coros_laps is not None else None,
            "strava_detail": _truncate_raw(strava_detail) if strava_detail is not None else None,
        },
    }


def _call_coros_detail(
    client: CorosMcpClient,
    *,
    coros_external_id: str,
    sport_type: str | None,
    sport_type_code: str | None,
) -> tuple[Any | None, Any | None, list[str]]:
    errors: list[str] = []
    sport_arg = sport_type_code or sport_type
    id_sets = [
        {"activityId": coros_external_id},
        {"labelId": coros_external_id},
        {"activityIds": [coros_external_id]},
        {"id": coros_external_id},
    ]
    if sport_arg is not None:
        sport_sets = [
            {**base, "sportType": sport_arg, "sport_type": sport_arg}
            for base in id_sets
        ]
        argument_sets = sport_sets + id_sets
    else:
        argument_sets = id_sets

    detail = None
    laps = None
    for args in argument_sets:
        try:
            detail = client.call_tool("getActivityDetail", args)
            break
        except CorosMcpError as exc:
            errors.append(f"getActivityDetail: {exc}")
            continue

    for args in argument_sets:
        try:
            laps = client.call_tool("queryActivityLapData", args)
            break
        except CorosMcpError as exc:
            errors.append(f"queryActivityLapData: {exc}")
            continue

    return detail, laps, errors


def _fetch_strava_extras(
    db: Session, activity: Activity
) -> tuple[Any | None, list[Any], list[str]]:
    errors: list[str] = []
    strava_id = resolve_strava_activity_id(db, activity)
    if strava_id is None:
        return None, [], errors

    try:
        from app.services.strava_api import get_activity, get_activity_laps, get_valid_access_token
        from app.services.strava_sync import get_connection_for_athlete

        connection = get_connection_for_athlete(db, activity.athlete_profile_id)
        if connection is None:
            errors.append("strava: no connection")
            return None, [], errors
        token = get_valid_access_token(connection, db)
        detail = get_activity(token, strava_id)
        laps = get_activity_laps(token, strava_id)
        return detail, laps, errors
    except Exception as exc:  # noqa: BLE001
        errors.append(f"strava: {exc}")
        return None, [], errors


def enrich_activity_detail(
    db: Session,
    activity: Activity,
    *,
    client: CorosMcpClient | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch COROS/Strava detail, normalize, and store on the canonical activity."""
    if (
        not force
        and activity.detail_json
        and activity.detail_fetched_at
        and datetime.utcnow() - activity.detail_fetched_at < DETAIL_TTL
    ):
        return {
            "ok": True,
            "skipped": True,
            "reason": "fresh",
            "activity_id": activity.id,
            "detail": parse_activity_detail(activity),
        }

    target = activity
    if activity.canonical_activity_id:
        parent = (
            db.query(Activity)
            .filter(Activity.id == activity.canonical_activity_id)
            .first()
        )
        if parent is not None:
            target = parent

    errors: list[str] = []
    coros_detail = None
    coros_laps = None
    sources_tried: list[str] = []

    coros_resolved = resolve_coros_detail_source(db, activity)
    if coros_resolved is not None and client is not None:
        sources_tried.append("coros")
        _target_from_coros, coros_external_id = coros_resolved
        # Prefer writing onto the visible canonical row when we resolved a twin.
        if activity.provider == "strava":
            target = activity
        try:
            if not getattr(client, "_initialized", False):
                client.initialize()
            sport_code = getattr(activity, "sport_type_code", None) or getattr(
                target, "sport_type_code", None
            )
            coros_detail, coros_laps, coros_errors = _call_coros_detail(
                client,
                coros_external_id=coros_external_id,
                sport_type=activity.sport_type or target.sport_type,
                sport_type_code=sport_code,
            )
            errors.extend(coros_errors)
        except CorosMcpError as exc:
            errors.append(f"coros: {exc}")
    elif coros_resolved is not None and client is None:
        errors.append("coros: client unavailable")

    strava_detail, strava_laps, strava_errors = _fetch_strava_extras(db, activity)
    errors.extend(strava_errors)
    if strava_detail is not None or strava_laps:
        sources_tried.append("strava")

    if coros_detail is None and coros_laps is None and strava_detail is None and not strava_laps:
        return {
            "ok": False,
            "skipped": False,
            "reason": "no_detail_sources",
            "activity_id": activity.id,
            "errors": errors[-10:],
            "sources_tried": sources_tried,
        }

    detail = build_normalized_detail(
        sport_type=target.sport_type or activity.sport_type,
        coros_detail=coros_detail,
        coros_laps=coros_laps,
        strava_detail=strava_detail,
        strava_laps=strava_laps,
    )

    # Preserve FIT-extracted exercises when MCP detail has none.
    if not detail.get("exercises"):
        existing = parse_activity_detail(target) or {}
        if existing.get("exercises"):
            detail["exercises"] = existing["exercises"]

    # Backfill summary HR onto the activity row when missing.
    summary = detail.get("summary") or {}
    if summary.get("avg_hr") and not target.average_heartrate:
        target.average_heartrate = summary["avg_hr"]
    if summary.get("max_hr") and not target.max_heartrate:
        target.max_heartrate = summary["max_hr"]

    target.detail_json = json.dumps(detail, default=str)[:DETAIL_JSON_MAX]
    target.detail_fetched_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    return {
        "ok": True,
        "skipped": False,
        "activity_id": target.id,
        "detail": detail,
        "errors": errors[-10:],
        "sources": detail.get("sources") or [],
    }


def enrich_recent_activities_missing_detail(
    db: Session,
    athlete_profile_id: int,
    *,
    client: CorosMcpClient | None = None,
    limit: int = RECENT_ENRICH_LIMIT,
) -> dict[str, Any]:
    """Enrich recent visible activities that lack detail_json."""
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.canonical_activity_id.is_(None),
            Activity.detail_json.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(limit)
        .all()
    )
    enriched = 0
    skipped = 0
    failed = 0
    errors: list[str] = []
    for row in rows:
        try:
            result = enrich_activity_detail(db, row, client=client, force=False)
            if result.get("ok") and not result.get("skipped"):
                enriched += 1
            elif result.get("skipped"):
                skipped += 1
            else:
                failed += 1
                if result.get("reason"):
                    errors.append(f"{row.id}: {result.get('reason')}")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed += 1
            errors.append(f"{row.id}: {exc}")
    return {
        "scanned": len(rows),
        "enriched": enriched,
        "skipped": skipped,
        "failed": failed,
        "errors": errors[-20:],
    }
