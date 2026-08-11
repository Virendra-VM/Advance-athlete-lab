"""Parse COROS MCP text-report tool responses into structured dicts."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


def _parse_date_token(token: str) -> date | None:
    token = (token or "").strip()
    if not token:
        return None
    if re.fullmatch(r"\d{8}", token):
        try:
            return datetime.strptime(token, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return datetime.strptime(token[:10], "%Y-%m-%d").date()
    except ValueError:
        compact = re.sub(r"\D", "", token)[:8]
        if len(compact) == 8:
            try:
                return datetime.strptime(compact, "%Y%m%d").date()
            except ValueError:
                return None
        return None


def _parse_duration_to_minutes(text: str) -> float | None:
    """Parse '7h 24min', '8h 19min', '45:48', '2:01:36', '20 min' to minutes."""
    text = text.strip().lower()
    if not text:
        return None
    hours = minutes = seconds = 0
    hm = re.search(r"(\d+)\s*h(?:ours?)?", text)
    mm = re.search(r"(\d+)\s*m(?:in(?:utes?)?)?", text)
    if hm or mm:
        if hm:
            hours = int(hm.group(1))
        if mm:
            minutes = int(mm.group(1))
        return float(hours * 60 + minutes)

    # clock style H:MM:SS or MM:SS
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = (int(p) for p in parts)
            return float(hours * 60 + minutes + seconds / 60)
        if len(parts) == 2:
            minutes, seconds = (int(p) for p in parts)
            return float(minutes + seconds / 60)
    except ValueError:
        return None
    return None


def _parse_distance_to_meters(text: str) -> float | None:
    text = text.strip().lower().replace(",", "")
    match = re.search(r"([\d.]+)\s*km", text)
    if match:
        return float(match.group(1)) * 1000.0
    match = re.search(r"([\d.]+)\s*m\b", text)
    if match:
        return float(match.group(1))
    return None


def parse_labeled_lines(text: str) -> dict[str, str]:
    """Extract 'Label: value' pairs from a text block."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            result[key] = value
    return result


def parse_fitness_assessment(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        return {}
    labels = parse_labeled_lines(text)
    return {
        "vo2max": _float_from(labels.get("VO2max") or labels.get("VO2Max")),
        "running_performance": _float_from(
            labels.get("Running Level") or labels.get("Running Performance")
        ),
        "threshold_pace": labels.get("Threshold Pace"),
        "race_predictions": {
            "5k": labels.get("5 km Prediction") or labels.get("5K Prediction"),
            "10k": labels.get("10 km Prediction") or labels.get("10K Prediction"),
            "half": labels.get("Half Marathon Prediction"),
            "marathon": labels.get("Marathon Prediction"),
        },
    }


def parse_recovery_status(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        return {}
    labels = parse_labeled_lines(text)
    recovery_raw = labels.get("Recovery") or labels.get("Recovery %") or ""
    pct_match = re.search(r"([\d.]+)\s*%?", recovery_raw)
    return {
        "recovery_pct": float(pct_match.group(1)) if pct_match else None,
        "recovery_level": labels.get("Level"),
        "recovery_full_at": labels.get("Estimated Full Recovery")
        or labels.get("Full Recovery"),
    }


def parse_training_load(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        return {}
    # Prefer the first dated block (most recent)
    blocks = re.split(r"\n(?=\d{4}-\d{2}-\d{2}\b)", text)
    comments: list[dict[str, Any]] = []
    latest: dict[str, Any] = {}
    for block in blocks:
        block = block.strip()
        if not re.match(r"\d{4}-\d{2}-\d{2}", block):
            continue
        lines = block.splitlines()
        day = lines[0].strip()
        labels = parse_labeled_lines(block)
        entry = {
            "date": day,
            "comment": labels.get("Comment"),
            "short_load": _float_from(labels.get("Short-Term Load")),
            "long_load": _float_from(labels.get("Long-Term Load")),
            "load_ratio": _float_from(labels.get("Load Ratio")),
        }
        comments.append(entry)
        if not latest:
            latest = entry
    return {
        "short_load": latest.get("short_load"),
        "long_load": latest.get("long_load"),
        "load_ratio": latest.get("load_ratio"),
        "daily_comments": comments,
    }


def _normalize_clock(value: str | None) -> str | None:
    """Normalize HH:MM / H:MM am/pm style times to 24h HH:MM."""
    if not value:
        return None
    text = value.strip()
    # Extract first time token from strings like "23:12 - 06:45" or "11:12 PM"
    match = re.search(
        r"(\d{1,2}):(\d{2})\s*(am|pm)?",
        text,
        re.I,
    )
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = (match.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_sleep_window(labels: dict[str, str], chunk: str) -> tuple[str | None, str | None]:
    bedtime = _normalize_clock(
        labels.get("Bedtime")
        or labels.get("Sleep Start")
        or labels.get("Fall Asleep")
        or labels.get("Sleep Time")
    )
    wake = _normalize_clock(
        labels.get("Wake Time")
        or labels.get("Wake")
        or labels.get("Get Up")
        or labels.get("Wake Up")
    )
    window = (
        labels.get("Sleep Window")
        or labels.get("Sleep Period")
        or labels.get("Main Sleep Window")
    )
    if window and (not bedtime or not wake):
        parts = re.split(r"\s*[-–—to]+\s*", window, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            bedtime = bedtime or _normalize_clock(parts[0])
            wake = wake or _normalize_clock(parts[1])
    if not bedtime or not wake:
        # Fallback: "23:12 - 06:45" anywhere in the chunk
        span = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm)?)\s*[-–—]\s*(\d{1,2}:\d{2}\s*(?:am|pm)?)",
            chunk,
            re.I,
        )
        if span:
            bedtime = bedtime or _normalize_clock(span.group(1))
            wake = wake or _normalize_clock(span.group(2))
    return bedtime, wake


def _parse_nap_minutes(labels: dict[str, str], chunk: str) -> float | None:
    for key in ("Nap", "Naps", "Nap Duration", "Total Nap", "Nap Time"):
        if key in labels:
            minutes = _parse_duration_to_minutes(labels[key])
            if minutes is not None:
                return minutes
    match = re.search(
        r"Nap(?:s| Duration| Time)?\s*[:：]\s*([^\n]+)",
        chunk,
        re.I,
    )
    if match:
        return _parse_duration_to_minutes(match.group(1))
    return None


def parse_sleep_data(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or "Sleep Score" not in text:
        return []
    chunks = re.split(r"\n(?=\d{4}-\d{2}-\d{2}\b)", text)
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not re.match(r"\d{4}-\d{2}-\d{2}", chunk):
            continue
        day = chunk.splitlines()[0].strip()
        metric_date = _parse_date_token(day)
        if metric_date is None:
            continue
        labels = parse_labeled_lines(chunk)
        main_sleep = labels.get("Main Sleep") or labels.get("Total") or labels.get("Total Sleep")
        bedtime, wake_time = _parse_sleep_window(labels, chunk)
        nap_duration_min = _parse_nap_minutes(labels, chunk)
        rows.append(
            {
                "metric_date": metric_date,
                "sleep_score": _float_from(labels.get("Sleep Score")),
                "sleep_duration_min": _parse_duration_to_minutes(main_sleep or ""),
                "deep_sleep_pct": _float_from(
                    (labels.get("Deep Sleep Ratio") or labels.get("Deep Sleep") or "").replace(
                        "%", ""
                    )
                ),
                "light_sleep_pct": _float_from(
                    (labels.get("Light Sleep Ratio") or labels.get("Light Sleep") or "").replace(
                        "%", ""
                    )
                ),
                "rem_sleep_pct": _float_from(
                    (labels.get("REM Ratio") or labels.get("REM Sleep") or labels.get("REM") or "")
                    .replace("%", "")
                ),
                "awake_min": _parse_duration_to_minutes(
                    labels.get("Awake Time") or labels.get("Wakefulness") or ""
                ),
                "bedtime": bedtime,
                "wake_time": wake_time,
                "nap_duration_min": nap_duration_min,
            }
        )
    return rows


def parse_daily_health_data(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    header_rhr = None
    header_hrv = None
    header_match = re.search(
        r"Resting HR:\s*([\d.]+)\s*bpm.*?HRV Baseline:\s*([\d.]+)\s*ms",
        text,
        re.I | re.S,
    )
    if header_match:
        header_rhr = float(header_match.group(1))
        header_hrv = float(header_match.group(2))

    chunks = re.split(r"\n---\s*(\d{8})\s*---\n", text)
    rows: list[dict[str, Any]] = []
    # chunks: [preamble, date1, body1, date2, body2, ...]
    i = 1
    while i + 1 < len(chunks):
        day_token = chunks[i]
        body = chunks[i + 1]
        metric_date = _parse_date_token(day_token)
        i += 2
        if metric_date is None:
            continue
        steps_m = re.search(r"Steps:\s*([\d,]+)", body)
        calories_m = re.search(r"Calories:\s*([\d,.]+)", body)
        stress_m = re.search(r"Stress:\s*Avg\s*([\d.]+)", body)
        steps = _float_from(steps_m.group(1) if steps_m else None)
        calories = _float_from(calories_m.group(1) if calories_m else None)
        stress = _float_from(stress_m.group(1) if stress_m else None)
        total = re.search(r"Total:\s*([^|]+)", body)
        deep = re.search(r"Deep:\s*([^|]+)", body)
        light = re.search(r"Light:\s*([^|]+)", body)
        rem = re.search(r"REM:\s*([^|]+)", body)
        awake = re.search(r"Awake:\s*([^|\n]+)", body)
        sleep_hr_m = re.search(r"Sleep HR:\s*Avg\s*([\d.]+)", body)
        sleep_hr = _float_from(sleep_hr_m.group(1) if sleep_hr_m else None)

        total_min = _parse_duration_to_minutes(total.group(1)) if total else None
        deep_min = _parse_duration_to_minutes(deep.group(1)) if deep else None
        light_min = _parse_duration_to_minutes(light.group(1)) if light else None
        rem_min = _parse_duration_to_minutes(rem.group(1)) if rem else None
        awake_min = _parse_duration_to_minutes(awake.group(1)) if awake else None

        deep_pct = light_pct = rem_pct = None
        if total_min and total_min > 0:
            if deep_min is not None:
                deep_pct = round(100.0 * deep_min / total_min, 1)
            if light_min is not None:
                light_pct = round(100.0 * light_min / total_min, 1)
            if rem_min is not None:
                rem_pct = round(100.0 * rem_min / total_min, 1)

        rows.append(
            {
                "metric_date": metric_date,
                "steps": int(steps) if steps is not None else None,
                "calories": calories,
                "stress": stress,
                "sleep_duration_min": total_min,
                "deep_sleep_pct": deep_pct,
                "light_sleep_pct": light_pct,
                "rem_sleep_pct": rem_pct,
                "awake_min": awake_min,
                # Keep overnight HR separate so daily avg HR sync does not overwrite it.
                "sleep_avg_hr": sleep_hr,
                "resting_heart_rate": header_rhr,
                "hrv": header_hrv,
            }
        )
    return rows


def parse_simple_daily_series(text: str, value_key: str) -> list[dict[str, Any]]:
    """Parse lines like '2026-08-10: 54 bpm' or '2026-08-10: 60 bpm (Min: ...)'."""
    if not isinstance(text, str):
        return []
    rows: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(\d{4}-\d{2}-\d{2}|\d{8}):\s*([\d.]+)",
        text,
    ):
        metric_date = _parse_date_token(match.group(1))
        if metric_date is None:
            continue
        rows.append({"metric_date": metric_date, value_key: float(match.group(2))})
    return rows


def parse_stress_series(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    rows: list[dict[str, Any]] = []
    # Multiline or single-line "Average Stress" / "Avg Stress"
    for match in re.finditer(
        r"(\d{4}-\d{2}-\d{2}|\d{8}):\s*(?:\n\s*)?(?:Average|Avg)\s*Stress:\s*([\d.]+)",
        text,
        re.I,
    ):
        metric_date = _parse_date_token(match.group(1))
        if metric_date is None:
            continue
        rows.append({"metric_date": metric_date, "stress": float(match.group(2))})
    return rows


def parse_training_schedule(text: str) -> list[dict[str, Any]]:
    """Parse COROS MCP Training Schedule text reports into structured items."""
    if not isinstance(text, str) or "Training Schedule" not in text:
        return []

    body = text.split("Use Plan ID", 1)[0]
    chunks = re.split(r"\n(?=\d{4}-\d{2}-\d{2}\b)", body)
    items: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        date_m = re.match(r"(\d{4}-\d{2}-\d{2})\s*\n(.+)", chunk, re.S)
        if not date_m:
            continue
        schedule_date = _parse_date_token(date_m.group(1))
        if schedule_date is None:
            continue
        rest = date_m.group(2).strip()
        lines = [line.strip() for line in rest.splitlines() if line.strip()]
        if not lines:
            continue
        title = lines[0]
        plan_id = None
        id_in_plan = None
        duration_min = None
        load_tl = None
        for line in lines[1:]:
            plan_m = re.match(r"Plan ID:\s*(.+)", line, re.I)
            if plan_m:
                plan_id = plan_m.group(1).strip()
                continue
            id_m = re.match(r"idInPlan:\s*(.+)", line, re.I)
            if id_m:
                id_in_plan = id_m.group(1).strip()
                continue
            time_m = re.match(r"Estimated Time:\s*(.+)", line, re.I)
            if time_m:
                duration_min = _parse_duration_to_minutes(time_m.group(1))
                continue
            load_m = re.match(r"Load:\s*([\d.]+)", line, re.I)
            if load_m:
                load_tl = float(load_m.group(1))
        external_id = (
            f"{plan_id or 'plan'}-{id_in_plan}"
            if id_in_plan
            else f"{schedule_date.isoformat()}-{title}"
        )
        items.append(
            {
                "date": schedule_date.isoformat(),
                "scheduleDate": schedule_date.isoformat(),
                "title": title,
                "name": title,
                "id": external_id,
                "idInPlan": id_in_plan,
                "planId": plan_id,
                "durationMin": duration_min,
                "load": load_tl,
            }
        )
    return items


def parse_hrv_assessment(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    rows: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(\d{4}-\d{2}-\d{2}):\s*\n\s*HRV Avg:\s*([\d.]+)\s*ms\s*—\s*([^\n]+)",
        text,
    ):
        metric_date = _parse_date_token(match.group(1))
        if metric_date is None:
            continue
        rows.append(
            {
                "metric_date": metric_date,
                "hrv": float(match.group(2)),
                "hrv_assessment": match.group(3).strip(),
            }
        )
    return rows


def parse_sport_records(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or "LabelId" not in text:
        return []
    chunks = re.split(r"\n(?=\d+\.\s+)", text)
    records: list[dict[str, Any]] = []
    for chunk in chunks:
        if "LabelId:" not in chunk:
            continue
        header = re.search(
            r"\d+\.\s+(.+?)\s+—\s+(\d{4}-\d{2}-\d{2})",
            chunk,
        )
        label_match = re.search(r"LabelId:\s*(\d+)", chunk)
        if not label_match:
            continue
        label_id = label_match.group(1)
        labels = parse_labeled_lines(chunk)
        duration_match = re.search(r"Duration:\s*([^|\n]+)", chunk)
        distance_match = re.search(r"Distance:\s*([^|\n]+)", chunk)
        duration_part = duration_match.group(1).strip() if duration_match else ""
        distance_part = distance_match.group(1).strip() if distance_match else None
        avg_hr = None
        hr_match = re.search(r"Avg HR:\s*([\d.]+)", chunk)
        if hr_match:
            avg_hr = float(hr_match.group(1))
        start_ts = None
        ts_match = re.search(r"startTimestamp=(\d+)", chunk)
        if ts_match:
            start_ts = int(ts_match.group(1))
        activity_date = None
        if start_ts:
            activity_date = datetime.utcfromtimestamp(start_ts)
        elif header:
            parsed_day = _parse_date_token(header.group(2))
            activity_date = datetime.combine(
                parsed_day or date.today(),
                datetime.min.time(),
            )
        sport_type = header.group(1).strip() if header else labels.get("SportType")
        location = labels.get("Location")
        if location and "|" in location:
            location = location.split("|", 1)[0].strip()
        name = location or sport_type or f"COROS {label_id}"
        records.append(
            {
                "external_id": label_id,
                "name": name,
                "sport_type": sport_type,
                "activity_date": activity_date or datetime.utcnow(),
                "distance_m": _parse_distance_to_meters(distance_part or "") or 0.0,
                "moving_time_s": int((_parse_duration_to_minutes(duration_part) or 0) * 60),
                "average_heartrate": avg_hr,
            }
        )
    return records


def _float_from(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    match = re.search(r"-?[\d.]+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
