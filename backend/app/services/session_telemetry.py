"""Deterministic session math for the coach.

The LLM must not invent watts, %FTP, or heart-rate peaks. This module computes
those from stored streams, laps, and physiology anchors, then the prompt only
asks the model to interpret the packet.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.models import Activity, ActivityNote, AthleteProfile
from app.services.activity_detail import activity_sport_family, parse_activity_detail
from app.services.activity_points import _resolve_parquet_path

# Coggan power zones as fractions of FTP.
POWER_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.0, 0.55),
    ("Z2 endurance", 0.56, 0.75),
    ("Z3 tempo", 0.76, 0.90),
    ("Z4 threshold", 0.91, 1.05),
    ("Z5 VO2max", 1.06, 1.20),
    ("Z6 anaerobic", 1.21, 1.50),
    ("Z7 neuromuscular", 1.51, 3.00),
)

# Friel-style HR zones relative to lactate threshold (LT2 / LTHR).
LTHR_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.0, 0.81),
    ("Z2 aerobic", 0.81, 0.89),
    ("Z3 tempo", 0.90, 0.93),
    ("Z4 threshold", 0.94, 0.99),
    ("Z5 super-threshold", 1.00, 1.06),
)

MAX_HR_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.50, 0.60),
    ("Z2 aerobic", 0.60, 0.70),
    ("Z3 tempo", 0.70, 0.80),
    ("Z4 threshold", 0.80, 0.90),
    ("Z5 VO2max", 0.90, 1.05),
)

ANALYSIS_HINTS = (
    "analy",
    "telemetry",
    "over-under",
    "over under",
    "overunder",
    "how was today",
    "how was this",
    "how did i do",
    "how did i perform",
    "this ride",
    "this workout",
    "this session",
    "today's ride",
    "todays ride",
    "today's session",
    "todays session",
    "today's workout",
    "today's run",
    "todays run",
    "today's swim",
    "how was the lift",
    "how was yoga",
    "sweet spot",
    "normalized power",
    "functional threshold",
    "lap by lap",
    "block 1",
    "block 2",
    "you got it wrong",
    "i had planned",
    "i planned",
    "main set",
    "repeat this set",
    "use your schedule",
)
INTERVAL_HINTS = (
    "interval",
    "over-under",
    "over under",
    "overunder",
    "laps",
    "splits",
    "this workout",
    "this ride",
    "this session",
    "structured",
)
NAME_STOPWORDS = {
    "mywhoosh",
    "whoosh",
    "virtual",
    "ride",
    "run",
    "walk",
    "yoga",
    "morning",
    "afternoon",
    "evening",
    "lunch",
    "night",
    "indoor",
    "city",
    "with",
    "part",
    "from",
    "test",
    "training",
    "weight",
    "session",
    "workout",
    "endurance",
    "climb",
    "circuit",
    "the",
    "and",
}
POWER_PASTE_RE = re.compile(
    r"\b(\d{2,4})\s*(w|watts|bpm|rpm|%?\s*ftp)\b",
    re.IGNORECASE,
)


def _round(value: float | None, digits: int = 1) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _mean(values: list[float]) -> float | None:
    return _round(sum(values) / len(values), 1) if values else None


def _peak(values: list[float]) -> float | None:
    return _round(max(values), 1) if values else None


def _pct(part: float | None, whole: float | None, digits: int = 1) -> float | None:
    if part is None or not whole:
        return None
    return _round(100.0 * float(part) / float(whole), digits)


def parse_duration_minutes(text: str | None) -> int | None:
    """Best-effort parse of '2 hours', '120 min', '3h 15m'."""
    if not text:
        return None
    raw = str(text).strip().lower()
    if not raw:
        return None
    try:
        return max(1, int(float(raw)))
    except ValueError:
        pass
    hours = 0.0
    minutes = 0.0
    matched = False
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*h(?:ours?)?", raw)
    if hour_match:
        hours = float(hour_match.group(1))
        matched = True
    min_match = re.search(r"(\d+(?:\.\d+)?)\s*m(?:in(?:utes?)?)?", raw)
    if min_match:
        minutes = float(min_match.group(1))
        matched = True
    if matched:
        total = int(round(hours * 60 + minutes))
        return total if total > 0 else None
    return None


def coggan_power_zones(ftp: float | None) -> list[dict[str, Any]]:
    if not ftp or ftp < 50:
        return []
    ftp = float(ftp)
    zones = []
    for name, low_frac, high_frac in POWER_ZONE_DEFS:
        zones.append(
            {
                "name": name,
                "low_w": round(ftp * low_frac),
                "high_w": round(ftp * high_frac),
                "low_frac": low_frac,
                "high_frac": high_frac,
            }
        )
    return zones


def heart_rate_zones(
    *, lthr_bpm: float | None = None, max_hr_bpm: float | None = None
) -> list[dict[str, Any]]:
    if lthr_bpm and lthr_bpm >= 90:
        anchor = float(lthr_bpm)
        defs = LTHR_ZONE_DEFS
        kind = "lthr"
    elif max_hr_bpm and max_hr_bpm >= 120:
        anchor = float(max_hr_bpm)
        defs = MAX_HR_ZONE_DEFS
        kind = "max_hr"
    else:
        return []
    zones = []
    for name, low_frac, high_frac in defs:
        zones.append(
            {
                "name": name,
                "low_bpm": round(anchor * low_frac),
                "high_bpm": round(anchor * high_frac),
                "low_frac": low_frac,
                "high_frac": high_frac,
                "relative_to": kind,
            }
        )
    return zones


def _to_1hz(elapsed_s: list[float], values: list[float | None]) -> list[float | None]:
    """Linear-interpolate a stream onto whole seconds. Gaps > 15s stay None."""
    pairs = [
        (float(t), float(v))
        for t, v in zip(elapsed_s, values)
        if t is not None
        and v is not None
        and math.isfinite(float(t))
        and math.isfinite(float(v))
    ]
    if len(pairs) < 3:
        return []
    pairs.sort(key=lambda item: item[0])
    times = np.array([item[0] for item in pairs], dtype=float)
    vals = np.array([item[1] for item in pairs], dtype=float)
    start = int(math.floor(times[0]))
    end = int(math.floor(times[-1]))
    if end <= start:
        return []
    grid = np.arange(start, end + 1, dtype=float)
    interpolated = np.interp(grid, times, vals)
    out: list[float | None] = interpolated.tolist()
    gaps = np.diff(times)
    for left, right, span in zip(times[:-1], times[1:], gaps):
        if span <= 15:
            continue
        for index, stamp in enumerate(grid):
            if left < stamp < right:
                out[index] = None
    return out


def normalized_power(elapsed_s: list[float], power: list[float | None]) -> float | None:
    series = _to_1hz(elapsed_s, power)
    watts = [value for value in series if value is not None and value >= 0]
    if len(watts) < 30:
        return _mean(watts)
    window = 30
    raised: list[float] = []
    rolling = 0.0
    for index, value in enumerate(watts):
        rolling += value
        if index >= window:
            rolling -= watts[index - window]
        if index >= window - 1:
            mean = rolling / window
            raised.append(mean**4)
    if not raised:
        return _mean(watts)
    return _round(math.pow(sum(raised) / len(raised), 0.25), 0)


def intensity_factor(np_watts: float | None, ftp: float | None) -> float | None:
    if not np_watts or not ftp:
        return None
    return _round(float(np_watts) / float(ftp), 3)


def training_stress_score(
    duration_s: float | None, np_watts: float | None, ftp: float | None
) -> float | None:
    if not duration_s or not np_watts or not ftp:
        return None
    iff = float(np_watts) / float(ftp)
    return _round((float(duration_s) * np_watts * iff) / (ftp * 3600.0) * 100.0, 0)


def time_in_zones(
    elapsed_s: list[float],
    values: list[float | None],
    zones: list[dict[str, Any]],
    *,
    value_key_low: str,
    value_key_high: str,
) -> list[dict[str, Any]]:
    series = _to_1hz(elapsed_s, values)
    if not series or not zones:
        return []
    counts = [0] * len(zones)
    for value in series:
        if value is None:
            continue
        for index, zone in enumerate(zones):
            low = zone[value_key_low]
            high = zone[value_key_high]
            if low <= value <= high:
                counts[index] += 1
                break
    total = sum(counts) or 1
    rows = []
    for zone, seconds in zip(zones, counts):
        rows.append(
            {
                "name": zone["name"],
                "seconds": seconds,
                "minutes": _round(seconds / 60.0, 1),
                "pct": _round(100.0 * seconds / total, 1),
            }
        )
    return rows


def hr_power_decoupling(
    elapsed_s: list[float],
    heart_rate: list[float | None],
    power: list[float | None],
) -> float | None:
    """Percent rise in HR:power from first half to second half. Positive = drift."""
    pairs = [
        (float(hr), float(watts))
        for hr, watts in zip(_to_1hz(elapsed_s, heart_rate), _to_1hz(elapsed_s, power))
        if hr and watts and watts > 40
    ]
    if len(pairs) < 120:
        return None
    mid = len(pairs) // 2
    first = pairs[:mid]
    second = pairs[mid:]
    def ratio(chunk: list[tuple[float, float]]) -> float | None:
        hr_mean = sum(item[0] for item in chunk) / len(chunk)
        p_mean = sum(item[1] for item in chunk) / len(chunk)
        if p_mean <= 0:
            return None
        return hr_mean / p_mean

    first_ratio = ratio(first)
    second_ratio = ratio(second)
    if not first_ratio or not second_ratio:
        return None
    return _round(100.0 * (second_ratio - first_ratio) / first_ratio, 1)


def best_rolling_mean(series_1hz: list[float | None], window_s: int) -> float | None:
    values = [value if value is not None and value >= 0 else None for value in series_1hz]
    if len(values) < window_s:
        return None
    best: float | None = None
    rolling = 0.0
    missing = 0
    for index, value in enumerate(values):
        if value is None:
            missing += 1
            value = 0.0
        rolling += value
        if index >= window_s:
            old = values[index - window_s]
            if old is None:
                missing -= 1
                old = 0.0
            rolling -= old
        if index >= window_s - 1 and missing <= window_s * 0.1:
            mean = rolling / window_s
            if best is None or mean > best:
                best = mean
    return _round(best, 0)


def classify_session(
    *,
    intensity_factor_value: float | None,
    power_zone_time: list[dict[str, Any]],
    laps: list[dict[str, Any]],
    ftp: float | None,
) -> str:
    if _is_over_under(laps, ftp):
        return "over-under"
    by_name = {row["name"]: row.get("pct") or 0 for row in power_zone_time}
    z5_plus = by_name.get("Z5 VO2max", 0) + by_name.get("Z6 anaerobic", 0) + by_name.get(
        "Z7 neuromuscular", 0
    )
    z4 = by_name.get("Z4 threshold", 0)
    z3 = by_name.get("Z3 tempo", 0)
    z2 = by_name.get("Z2 endurance", 0)
    if z5_plus >= 12:
        return "vo2-intervals"
    if intensity_factor_value and intensity_factor_value >= 1.05:
        return "threshold"
    if z4 >= 25 and z3 >= 15:
        return "sweet-spot"
    if z4 >= 30:
        return "threshold"
    if z3 >= 35:
        return "tempo"
    if intensity_factor_value and 0.84 <= intensity_factor_value <= 0.97:
        return "sweet-spot"
    if z2 >= 55 or (intensity_factor_value is not None and intensity_factor_value < 0.75):
        return "endurance"
    return "mixed"


def _is_over_under(laps: list[dict[str, Any]], ftp: float | None) -> bool:
    if not ftp or len(laps) < 4:
        return False
    flags: list[str] = []
    for lap in laps:
        power = lap.get("avg_power")
        duration = lap.get("duration_s") or 0
        if not power or duration < 40:
            continue
        pct = float(power) / float(ftp)
        if 0.80 <= pct <= 0.95:
            flags.append("under")
        elif 1.05 <= pct <= 1.28:
            flags.append("over")
        elif pct < 0.70:
            flags.append("rest")
    work = [flag for flag in flags if flag != "rest"]
    if "over" not in work or "under" not in work:
        return False
    flips = sum(1 for left, right in zip(work, work[1:]) if left != right)
    return flips >= 3


def load_stream_frame(activity: Activity) -> pd.DataFrame | None:
    path = _resolve_parquet_path(activity)
    if path is None:
        return None
    try:
        frame = pd.read_parquet(path)
    except Exception:  # noqa: BLE001 - a corrupt parquet must not break coaching
        return None
    if frame.empty or "timestamp" not in frame.columns:
        return None
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    start = frame["timestamp"].iloc[0]
    frame["elapsed_s"] = (frame["timestamp"] - start).dt.total_seconds()
    return frame


def _column_values(frame: pd.DataFrame, *names: str) -> list[float | None]:
    for name in names:
        if name in frame.columns:
            series = frame[name]
            return [float(value) if pd.notna(value) else None for value in series]
    return []


def _enrich_laps(
    laps: list[dict[str, Any]],
    physiology: dict[str, Any],
) -> list[dict[str, Any]]:
    ftp = physiology.get("ftp_watts")
    lthr = physiology.get("lthr_bpm")
    max_hr = physiology.get("max_hr_bpm")
    rows = []
    for lap in laps[:48]:
        avg_power = _round(lap.get("avg_power") or lap.get("normalized_power"), 0)
        avg_hr = _round(lap.get("avg_hr"), 0)
        row = {
            "index": lap.get("index"),
            "label": lap.get("label"),
            "duration_s": lap.get("duration_s"),
            "duration_min": _round((lap.get("duration_s") or 0) / 60.0, 1),
            "avg_power": avg_power,
            "np": _round(lap.get("normalized_power"), 0),
            "pct_ftp": _pct(avg_power, ftp, 0),
            "avg_hr": avg_hr,
            "max_hr": _round(lap.get("max_hr"), 0),
            "pct_lthr": _pct(avg_hr, lthr, 0),
            "pct_max_hr": _pct(avg_hr, max_hr, 0),
            "avg_cadence": _round(lap.get("avg_cadence"), 0),
        }
        rows.append(row)
    return _annotate_lap_roles(rows, ftp)


def _compact_exercises(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows = []
    for item in raw[:16]:
        if not isinstance(item, dict):
            continue
        sets = item.get("sets") if isinstance(item.get("sets"), list) else []
        rows.append(
            {
                "name": item.get("name") or item.get("exercise"),
                "sets": len(sets) or item.get("set_count"),
                "reps": [row.get("reps") for row in sets[:8] if isinstance(row, dict)] or None,
            }
        )
    return rows


def compact_activity_metrics(
    activity: Activity,
    *,
    physiology: dict[str, Any] | None = None,
    note: str | None = None,
    when: str | None = None,
    local_date: str | None = None,
) -> dict[str, Any]:
    physiology = physiology or {}
    detail = parse_activity_detail(activity) or {}
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    minutes = round((activity.moving_time_s or 0) / 60.0)
    avg_hr = _round(activity.average_heartrate or summary.get("avg_hr"), 0)
    max_hr = _round(activity.max_heartrate or summary.get("max_hr"), 0)
    avg_power = _round(summary.get("avg_power"), 0)
    max_power = _round(summary.get("max_power"), 0)
    np_watts = _round(summary.get("normalized_power") or summary.get("weighted_average_watts"), 0)
    if np_watts is None and laps:
        powered = [lap.get("normalized_power") or lap.get("avg_power") for lap in laps]
        powered = [float(value) for value in powered if value]
        np_watts = _round(sum(powered) / len(powered), 0) if powered else None
    ftp = physiology.get("ftp_watts")
    return {
        "id": activity.id,
        "date": local_date,
        "when": when,
        "sport": activity.sport_type,
        "family": activity_sport_family(activity.sport_type),
        "name": activity.name,
        "km": round((activity.distance_m or 0) / 1000.0, 2),
        "minutes": minutes,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "avg_power": avg_power,
        "np": np_watts,
        "max_power": max_power,
        "pct_ftp": _pct(np_watts or avg_power, ftp, 0),
        "avg_cadence": _round(summary.get("avg_cadence"), 0),
        "lap_count": len(laps),
        "note": (note or "").strip() or None,
    }


def analyze_activity(activity: Activity, physiology: dict[str, Any]) -> dict[str, Any]:
    """Full telemetry packet for one session. Safe to inject into a prompt."""
    detail = parse_activity_detail(activity) or {}
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    raw_laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    zones_blob = detail.get("zones") if isinstance(detail.get("zones"), dict) else {}

    frame = load_stream_frame(activity)
    elapsed: list[float] = []
    power: list[float | None] = []
    hr: list[float | None] = []
    cadence: list[float | None] = []
    if frame is not None:
        elapsed = [float(value) for value in frame["elapsed_s"].tolist()]
        power = _column_values(frame, "power")
        hr = _column_values(frame, "heart_rate", "heartrate", "hr")
        cadence = _column_values(frame, "cadence")

    duration_s = float(activity.moving_time_s or 0)
    if elapsed:
        duration_s = max(duration_s, elapsed[-1] - elapsed[0])

    avg_power = _mean([value for value in power if value and value > 0]) or _round(
        summary.get("avg_power"), 0
    )
    np_watts = normalized_power(elapsed, power) if power else _round(
        summary.get("normalized_power"), 0
    )
    max_power = _peak([value for value in power if value]) or _round(summary.get("max_power"), 0)
    avg_hr = _mean([value for value in hr if value and value > 30]) or _round(
        activity.average_heartrate or summary.get("avg_hr"), 0
    )
    max_hr = _peak([value for value in hr if value]) or _round(
        activity.max_heartrate or summary.get("max_hr"), 0
    )
    cad_values = [value for value in cadence if value and value > 20]
    ftp = physiology.get("ftp_watts")
    iff = intensity_factor(np_watts, ftp)
    laps = _enrich_laps(raw_laps, physiology)
    power_zones = coggan_power_zones(ftp)
    hr_zones = heart_rate_zones(
        lthr_bpm=physiology.get("lthr_bpm"), max_hr_bpm=physiology.get("max_hr_bpm")
    )
    power_time = time_in_zones(elapsed, power, power_zones, value_key_low="low_w", value_key_high="high_w")
    hr_time = time_in_zones(elapsed, hr, hr_zones, value_key_low="low_bpm", value_key_high="high_bpm")
    if not power_time and isinstance(zones_blob.get("power"), list):
        power_time = _coerce_provider_zones(zones_blob.get("power"), "power")
    if not hr_time and isinstance(zones_blob.get("hr"), list):
        hr_time = _coerce_provider_zones(zones_blob.get("hr"), "hr")

    lap_source = "stored"
    if laps_are_uninformative(raw_laps, duration_s) and power and ftp:
        detected = detect_laps_from_power_stream(
            elapsed, power, ftp=ftp, hr=hr, cadence=cadence
        )
        if detected:
            raw_laps = detected
            lap_source = "power_stream"
            laps = _enrich_laps(raw_laps, physiology)

    classification = classify_session(
        intensity_factor_value=iff,
        power_zone_time=power_time,
        laps=laps,
        ftp=ftp,
    )
    work_laps = [
        lap
        for lap in laps
        if lap.get("role") in {"over", "under", "work"}
        or (
            lap.get("role") not in {"warmup", "cooldown", "recovery"}
            and (lap.get("pct_ftp") or 0) >= 80
            and (lap.get("duration_s") or 0) < 12 * 60
        )
    ]
    peak_hr_by_block = [
        {"label": lap.get("label") or f"Lap {lap.get('index')}", "max_hr": lap.get("max_hr")}
        for lap in laps
        if lap.get("max_hr")
    ]
    pace_min_km = None
    if activity.distance_m and duration_s and activity.distance_m >= 50:
        pace_min_km = _round((duration_s / 60.0) / (activity.distance_m / 1000.0), 2)
    exercises = _compact_exercises(detail.get("exercises"))
    family = activity_sport_family(activity.sport_type)

    return {
        "id": activity.id,
        "name": activity.name,
        "sport": activity.sport_type,
        "family": family,
        "minutes": _round(duration_s / 60.0, 0),
        "km": round((activity.distance_m or 0) / 1000.0, 2),
        "pace_min_per_km": pace_min_km or _round(summary.get("avg_pace"), 2),
        "has_streams": bool(elapsed),
        "classification": classification,
        "power": {
            "avg_w": avg_power,
            "np_w": np_watts,
            "max_w": max_power,
            "pct_ftp_np": _pct(np_watts, ftp, 0),
            "intensity_factor": iff,
            "tss": training_stress_score(duration_s, np_watts, ftp),
        },
        "heart_rate": {
            "avg_bpm": avg_hr,
            "max_bpm": max_hr,
            "pct_lthr_avg": _pct(avg_hr, physiology.get("lthr_bpm"), 0),
            "pct_max_avg": _pct(avg_hr, physiology.get("max_hr_bpm"), 0),
            "pct_max_peak": _pct(max_hr, physiology.get("max_hr_bpm"), 0),
            "decoupling_pct": hr_power_decoupling(elapsed, hr, power) if elapsed else None,
            "peak_by_lap": peak_hr_by_block[:12],
        },
        "cadence": {
            "avg_rpm": _mean(cad_values),
            "avg_spm": _mean(cad_values) if family == "run" else None,
            "min_rpm": _round(min(cad_values), 0) if cad_values else None,
            "max_rpm": _round(max(cad_values), 0) if cad_values else None,
        },
        "swim": {
            "swolf": _round(summary.get("swolf"), 1),
            "stroke_count": summary.get("stroke_count"),
            "avg_pace": _round(summary.get("avg_pace"), 2),
        },
        "exercises": exercises,
        "time_in_power_zones": power_time,
        "time_in_hr_zones": hr_time,
        "lap_source": lap_source,
        "lap_count": len(laps),
        "work_lap_count": len(work_laps),
        "laps": laps,
        "work_laps": work_laps,
        "anchors_used": {
            "ftp_watts": ftp,
            "ftp_source": physiology.get("ftp_source"),
            "lthr_bpm": physiology.get("lthr_bpm"),
            "max_hr_bpm": physiology.get("max_hr_bpm"),
        },
        "missing": _missing_fields(elapsed, power, hr, ftp),
    }


def _coerce_provider_zones(rows: list[Any], kind: str) -> list[dict[str, Any]]:
    out = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        seconds = row.get("seconds") or row.get("time") or row.get("duration")
        try:
            seconds = int(float(seconds)) if seconds is not None else 0
        except (TypeError, ValueError):
            seconds = 0
        out.append(
            {
                "name": str(row.get("name") or row.get("zone") or f"Z{index}"),
                "seconds": seconds,
                "minutes": _round(seconds / 60.0, 1),
                "pct": _round(row.get("pct") or row.get("percent"), 1),
            }
        )
    total = sum(item["seconds"] for item in out) or 1
    for item in out:
        if item["pct"] is None:
            item["pct"] = _round(100.0 * item["seconds"] / total, 1)
    return out


def _missing_fields(
    elapsed: list[float],
    power: list[float | None],
    hr: list[float | None],
    ftp: float | None,
) -> list[str]:
    missing = []
    if not elapsed:
        missing.append("streams")
    if not any(value and value > 0 for value in power):
        missing.append("power")
    if not any(value and value > 30 for value in hr):
        missing.append("heart_rate")
    if not ftp:
        missing.append("ftp")
    return missing


def estimate_ftp_watts(activities: list[Activity], *, use_streams: bool = True) -> float | None:
    """0.95 × best 20-minute power from recent rides. None if not enough data."""
    best_20: float | None = None
    stream_budget = 4 if use_streams else 0
    for activity in activities:
        family = activity_sport_family(activity.sport_type)
        if family != "ride" and not _looks_like_ride(activity.sport_type):
            continue
        candidate = _best_20min_from_laps(activity)
        if candidate is None and stream_budget > 0:
            frame = load_stream_frame(activity)
            stream_budget -= 1
            if frame is not None:
                elapsed = [float(value) for value in frame["elapsed_s"].tolist()]
                power = _column_values(frame, "power")
                series = _to_1hz(elapsed, power)
                candidate = best_rolling_mean(series, 20 * 60)
        if candidate and (best_20 is None or candidate > best_20):
            best_20 = candidate
    if not best_20 or best_20 < 80 or best_20 > 500:
        return None
    return _round(best_20 * 0.95, 0)


def _looks_like_ride(sport_type: str | None) -> bool:
    key = re.sub(r"[^a-z0-9]", "", (sport_type or "").lower())
    return key in {
        "ride",
        "virtualride",
        "ebikeride",
        "gravelride",
        "mountainbikeride",
        "cycling",
        "bike",
        "indoorcycling",
    }


def _best_20min_from_laps(activity: Activity) -> float | None:
    detail = parse_activity_detail(activity) or {}
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    rows = []
    for lap in laps:
        duration = lap.get("duration_s") or 0
        power = lap.get("normalized_power") or lap.get("avg_power")
        if duration and power:
            rows.append((int(duration), float(power)))
    if not rows:
        return None
    best: float | None = None
    for start in range(len(rows)):
        total_s = 0
        weighted = 0.0
        for duration, power in rows[start:]:
            total_s += duration
            weighted += duration * power
            if total_s >= 18 * 60:
                mean = weighted / total_s
                if best is None or mean > best:
                    best = mean
                break
    return _round(best, 0)


def estimate_max_hr(activities: list[Activity], profile: AthleteProfile) -> float | None:
    peaks = [
        float(activity.max_heartrate)
        for activity in activities
        if activity.max_heartrate and activity.max_heartrate > 120
    ]
    if peaks:
        return _round(max(peaks), 0)
    if profile.age and 13 <= profile.age <= 90:
        return _round(220 - profile.age, 0)
    return None


def resolve_physiology(
    profile: AthleteProfile,
    activities: list[Activity],
    *,
    resting_hr: float | None = None,
) -> dict[str, Any]:
    stored_estimate = getattr(profile, "ftp_estimated_watts", None)
    stamped = getattr(profile, "ftp_estimated_at", None)
    fresh = isinstance(stamped, datetime) and datetime.utcnow() - stamped < timedelta(days=7)
    estimated_ftp = stored_estimate if fresh and stored_estimate else None
    if estimated_ftp is None:
        try:
            estimated_ftp = estimate_ftp_watts(
                activities[:12],
                use_streams=not bool(getattr(profile, "ftp_watts", None)),
            )
        except Exception:  # noqa: BLE001
            estimated_ftp = stored_estimate
    estimated_max = estimate_max_hr(activities, profile)
    ftp_manual = getattr(profile, "ftp_watts", None)
    lthr_manual = getattr(profile, "lthr_bpm", None)
    max_hr_manual = getattr(profile, "max_hr_bpm", None)
    ftp = ftp_manual or estimated_ftp
    max_hr = max_hr_manual or estimated_max
    lthr = lthr_manual
    if lthr is None and max_hr:
        # Conservative placeholder only when the athlete has not set LT2.
        lthr = _round(float(max_hr) * 0.90, 0)
        lthr_source = "estimated_from_max_hr"
    else:
        lthr_source = "manual" if lthr_manual else None
    return {
        "ftp_watts": _round(ftp, 0),
        "ftp_source": "manual" if ftp_manual else ("estimated" if estimated_ftp else None),
        "ftp_estimated_watts": _round(estimated_ftp, 0),
        "lthr_bpm": _round(lthr, 0),
        "lthr_source": lthr_source,
        "max_hr_bpm": _round(max_hr, 0),
        "max_hr_source": "manual" if max_hr_manual else ("estimated" if estimated_max else None),
        "resting_hr_bpm": _round(resting_hr, 0),
        "power_zones": coggan_power_zones(ftp),
        "hr_zones": heart_rate_zones(lthr_bpm=lthr, max_hr_bpm=max_hr),
    }


def persist_physiology_estimate(profile: AthleteProfile, physiology: dict[str, Any]) -> None:
    estimated = physiology.get("ftp_estimated_watts")
    if not estimated:
        return
    current = getattr(profile, "ftp_estimated_watts", None)
    stamped = getattr(profile, "ftp_estimated_at", None)
    stale = stamped is None or (
        isinstance(stamped, datetime) and datetime.utcnow() - stamped > timedelta(days=7)
    )
    if current != estimated or stale:
        profile.ftp_estimated_watts = estimated
        profile.ftp_estimated_at = datetime.utcnow()
        if not getattr(profile, "ftp_source", None) and not getattr(profile, "ftp_watts", None):
            profile.ftp_source = "estimated"


def notes_by_activity_id(notes: list[ActivityNote]) -> dict[int, str]:
    grouped: dict[int, list[str]] = {}
    for note in notes:
        body = (note.body or "").strip()
        if not body:
            continue
        grouped.setdefault(note.activity_id, []).append(body)
    return {key: " | ".join(values)[:500] for key, values in grouped.items()}


def detect_chat_intent(message: str) -> str:
    """Backward-compatible wrapper around the chat intent router."""
    from app.services.coach_intent import classify_chat_intent

    return classify_chat_intent(message, use_llm=False)


def match_activity_for_message(
    message: str,
    activities: list[Activity],
    *,
    today_ids: set[int] | None = None,
    activity_id: int | None = None,
) -> Activity | None:
    if not activities:
        return None
    if activity_id:
        for activity in activities:
            if activity.id == activity_id:
                return activity
    text = (message or "").lower()
    today_ids = today_ids or set()
    prefer_structured = any(hint in text for hint in INTERVAL_HINTS)

    for activity in activities:
        name = (activity.name or "").strip().lower()
        if name and len(name) >= 5 and name in text:
            return activity

    for activity in activities:
        for token in _name_tokens(activity.name):
            if token in text:
                return activity

    wanted_family = _family_hint_from_message(text)
    if wanted_family:
        for activity in activities:
            family = activity_sport_family(activity.sport_type)
            if family == wanted_family or (
                wanted_family == "ride" and _looks_like_ride(activity.sport_type)
            ):
                return activity

    if any(word in text for word in ("today", "this morning", "this afternoon", "just now")):
        today = [activity for activity in activities if activity.id in today_ids]
        if today:
            return _prefer_quality_session(today, prefer_structured=prefer_structured)

    if "yesterday" in text:
        rest = [activity for activity in activities if activity.id not in today_ids]
        if rest:
            return _prefer_quality_session(rest[:8], prefer_structured=prefer_structured)

    # Newest endurance session — not the longest ride in the recent window.
    return _prefer_quality_session(activities[:8], prefer_structured=prefer_structured)


def _family_hint_from_message(text: str) -> str | None:
    checks = (
        ("swim", ("swim", "swimming", "pool", "open water")),
        ("strength", ("lift", "lifting", "gym", "weights", "strength", "weight training")),
        ("yoga", ("yoga", "mobility", "pilates", "stretch")),
        ("run", ("run", "running", "jog", "tempo run")),
        ("ride", ("ride", "bike", "cycling", "whoosh", "zwift", "trainer")),
        ("walk", ("walk", "hike", "hiking")),
    )
    for family, words in checks:
        if any(word in text for word in words):
            return family
    return None


def _name_tokens(name: str | None) -> list[str]:
    tokens = re.findall(r"[a-z0-9']{5,}", (name or "").lower())
    return [token for token in tokens if token not in NAME_STOPWORDS]


def _stored_lap_count(activity: Activity) -> int:
    detail = parse_activity_detail(activity) or {}
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    return len(laps)


def _prefer_quality_session(
    activities: list[Activity],
    *,
    prefer_structured: bool = False,
) -> Activity:
    """Activities are newest-first. Prefer the most recent ride/run, not the longest."""
    pool = list(activities)
    if prefer_structured:
        structured = [activity for activity in pool if _stored_lap_count(activity) >= 4]
        if structured:
            return structured[0]
    return pool[0]


def laps_are_uninformative(laps: list[dict[str, Any]], duration_s: float) -> bool:
    if not laps:
        return True
    if len(laps) >= 4:
        return False
    if len(laps) == 1:
        lap_duration = float(laps[0].get("duration_s") or 0)
        return lap_duration >= 0.75 * max(float(duration_s or 1), 1.0)
    return False


def _annotate_lap_roles(
    laps: list[dict[str, Any]], ftp: float | None
) -> list[dict[str, Any]]:
    total = len(laps)
    for index, lap in enumerate(laps, start=1):
        duration = float(lap.get("duration_s") or 0)
        pct = float(lap.get("pct_ftp") or 0)
        power = lap.get("avg_power")
        role = "steady"
        if index == 1 and duration >= 240 and pct < 80:
            role = "warmup"
        elif index == total and duration >= 240 and pct < 80:
            role = "cooldown"
        elif ftp and power:
            frac = float(power) / float(ftp)
            if 1.05 <= frac <= 1.40 and 35 <= duration <= 360:
                role = "over"
            elif 0.78 <= frac <= 0.97 and 40 <= duration <= 600:
                role = "under"
            elif frac < 0.70:
                role = "recovery"
            elif frac >= 0.80:
                role = "work"
        lap["role"] = role
    return laps


def detect_laps_from_power_stream(
    elapsed: list[float],
    power: list[float | None],
    *,
    ftp: float,
    hr: list[float | None] | None = None,
    cadence: list[float | None] | None = None,
    min_seg_s: int = 30,
) -> list[dict[str, Any]]:
    """Recover interval laps when stored detail is a single session-length lap.

    Only returns laps when the stream shows a contiguous repeating over/under
    block. Long climbs and steady endurance files stay as one block.
    """
    series = _to_1hz(elapsed, power)
    if len(series) < 300 or not ftp:
        return []
    ftp = float(ftp)
    smooth = _rolling_mean_1hz(series, 12)

    def label_for(watts: float | None) -> str:
        if watts is None or watts < 40:
            return "gap"
        frac = watts / ftp
        if frac >= 1.08:
            return "over"
        if 0.80 <= frac <= 0.97:
            return "under"
        if frac < 0.65:
            return "rest"
        return "easy"

    labels = [label_for(value) for value in smooth]
    raw: list[tuple[int, int, str]] = []
    start = 0
    for index in range(1, len(labels) + 1):
        if index == len(labels) or labels[index] != labels[start]:
            raw.append((start, index, labels[start]))
            start = index

    segments: list[tuple[int, int, str]] = []
    for seg_start, seg_end, label in raw:
        if segments and (seg_end - seg_start) < min_seg_s:
            prev_start, _, prev_label = segments[-1]
            segments[-1] = (prev_start, seg_end, prev_label)
        else:
            segments.append((seg_start, seg_end, label))

    collapsed: list[tuple[int, int, str]] = []
    for seg_start, seg_end, label in segments:
        if collapsed and collapsed[-1][2] == label:
            collapsed[-1] = (collapsed[-1][0], seg_end, label)
        else:
            collapsed.append((seg_start, seg_end, label))
    segments = collapsed

    work_indexes = [
        i for i, (_s, _e, label) in enumerate(segments) if label in {"over", "under"}
    ]
    if len(work_indexes) < 6:
        return []

    best: tuple[int, int] | None = None
    run_start = 0
    while run_start < len(work_indexes):
        run_end = run_start
        while run_end + 1 < len(work_indexes):
            prev_end = segments[work_indexes[run_end]][1]
            next_start = segments[work_indexes[run_end + 1]][0]
            if next_start - prev_end > 12:
                break
            run_end += 1
        if best is None or (run_end - run_start) > (best[1] - best[0]):
            best = (run_start, run_end)
        run_start = run_end + 1

    if best is None:
        return []
    run = [work_indexes[i] for i in range(best[0], best[1] + 1)]
    run_labels = [segments[i][2] for i in run]
    overs = [segments[i][1] - segments[i][0] for i in run if segments[i][2] == "over"]
    unders = [segments[i][1] - segments[i][0] for i in run if segments[i][2] == "under"]
    flips = sum(1 for left, right in zip(run_labels, run_labels[1:]) if left != right)
    if len(overs) < 3 or len(unders) < 3 or flips < 5:
        return []
    if max(overs) > 3.2 * min(overs) or max(unders) > 3.2 * min(unders):
        return []
    if not (30 <= sorted(overs)[len(overs) // 2] <= 150):
        return []
    if not (45 <= sorted(unders)[len(unders) // 2] <= 240):
        return []

    cvs = []
    for index in run:
        seg_start, seg_end, _label = segments[index]
        values = [smooth[i] for i in range(seg_start, seg_end) if smooth[i]]
        mean = sum(values) / len(values) if values else 0
        if mean <= 0:
            continue
        var = sum((value - mean) ** 2 for value in values) / len(values)
        cvs.append((var ** 0.5) / mean)
    if not cvs or (sum(cvs) / len(cvs)) > 0.14:
        return []

    first_work = segments[run[0]][0]
    last_work = segments[run[-1]][1]
    kept: list[tuple[int, int, str]] = []
    if first_work >= 180:
        kept.append((0, first_work, "warmup"))
    kept.extend(segments[i] for i in run)
    if len(smooth) - last_work >= 180:
        kept.append((last_work, len(smooth), "cooldown"))

    hr_series = _to_1hz(elapsed, hr) if hr else []
    cad_series = _to_1hz(elapsed, cadence) if cadence else []
    rows: list[dict[str, Any]] = []
    for index, (seg_start, seg_end, _label) in enumerate(kept, start=1):
        watts = [smooth[i] for i in range(seg_start, seg_end) if smooth[i]]
        hrs = [
            hr_series[i]
            for i in range(seg_start, min(seg_end, len(hr_series)))
            if hr_series and hr_series[i]
        ]
        cads = [
            cad_series[i]
            for i in range(seg_start, min(seg_end, len(cad_series)))
            if cad_series and cad_series[i]
        ]
        rows.append(
            {
                "index": index,
                "label": f"Lap {index}",
                "duration_s": seg_end - seg_start,
                "avg_power": _mean(watts),
                "avg_hr": _mean(hrs),
                "max_hr": _peak(hrs),
                "avg_cadence": _mean(cads),
            }
        )
    return rows


def _rolling_mean_1hz(series: list[float | None], window: int) -> list[float | None]:
    out: list[float | None] = []
    acc = 0.0
    count = 0
    queue: list[float | None] = []
    for index, value in enumerate(series):
        queue.append(value)
        if value is not None:
            acc += value
            count += 1
        if index >= window:
            old = queue.pop(0)
            if old is not None:
                acc -= old
                count -= 1
        out.append(acc / count if count else None)
    return out


def retrieval_query_for_session(classification: str, message: str) -> str:
    parts = [classification, "cycling power zones sweet spot over-under cardiac drift"]
    if "ill" in message.lower() or "fever" in message.lower() or "temperature" in message.lower():
        parts.append("return to training after illness heart rate")
    parts.append(message[:180])
    return " ".join(parts)
