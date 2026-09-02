"""Turn a chat week table into persistable planned workouts."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError

from app.ai_schemas import WeekPlanJSON

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
DAY_INDEX = {name: index for index, name in enumerate(WEEKDAYS)}
ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
DURATION_CHUNK_RE = re.compile(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?")


def parse_week_plan_from_text(
    text: str,
    *,
    week_start: date,
    title: str | None = None,
) -> dict[str, Any] | None:
    """Parse a markdown or copied coach week table into WeekPlan JSON."""
    if not text or not week_start:
        return None
    rows = _table_rows(text)
    workouts: list[dict[str, Any]] = []
    for row in rows:
        workouts.extend(_workouts_from_row(row, week_start))
    if not workouts:
        return None
    payload = {
        "title": title or f"Revised week of {week_start.isoformat()}",
        "summary": "Week revised from coach chat.",
        "focus": "athlete-proposed calendar",
        "week_start": week_start.isoformat(),
        "workouts": workouts,
        "coach_notes": None,
        "citations": [],
    }
    try:
        return WeekPlanJSON.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        return None


def coerce_week_plan(payload: Any, *, week_start: date) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        data = WeekPlanJSON.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        return None
    data["week_start"] = week_start.isoformat()
    return data


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        cells = _split_cells(line)
        if len(cells) < 4:
            continue
        if _is_header(cells) or _is_divider(cells):
            continue
        if not _looks_like_day_row(cells):
            continue
        rows.append(cells)
    return rows


def _split_cells(line: str) -> list[str]:
    trimmed = line.strip().strip("|")
    if "\t" in trimmed:
        parts = [part.strip() for part in trimmed.split("\t")]
    elif trimmed.count("|") >= 3:
        parts = [part.strip() for part in trimmed.split("|")]
    else:
        parts = [part.strip() for part in re.split(r"\s{2,}", trimmed)]
    return [part for part in parts if part]


def _is_header(cells: list[str]) -> bool:
    blob = " ".join(cells).lower()
    if "secret rule" in blob or "primary focus" in blob:
        return True
    return "day" in blob and "session" in blob


def _is_divider(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells)


def _looks_like_day_row(cells: list[str]) -> bool:
    first = cells[0].lower()
    if first in DAY_INDEX:
        return True
    return bool(ISO_DATE_RE.search(" ".join(cells[:3])))


def _workouts_from_row(cells: list[str], week_start: date) -> list[dict[str, Any]]:
    day_name, iso, session, sport, duration, intensity, notes = _normalize_row(cells)
    workout_date = _resolve_date(day_name, iso, week_start)
    if workout_date is None:
        return []
    titles = _split_combo(session)
    sports = _split_combo(sport, extra=r"/")
    durations = _split_durations(duration)
    intensities = _split_combo(intensity, extra=r"/")
    count = max(len(titles), 1)
    if count > 1:
        rows = []
        for index in range(count):
            title = titles[index] if index < len(titles) else session
            minutes = (
                durations[index]
                if index < len(durations)
                else (durations[0] if durations else None)
            )
            rows.append(
                _workout(
                    workout_date,
                    title,
                    sports[index] if index < len(sports) else (sports[-1] if sports else sport),
                    minutes,
                    intensities[index] if index < len(intensities) else (intensities[-1] if intensities else intensity),
                    notes,
                )
            )
        return rows
    minutes = durations[0] if durations else _first_duration(duration)
    return [_workout(workout_date, session, sport, minutes, intensity, notes)]


def _normalize_row(cells: list[str]) -> tuple[str, str, str, str, str, str, str]:
    """Support the 7-col director table and the 5-col Today's Call table."""
    cleaned = [_clean_cell(cell) for cell in cells]
    if len(cleaned) >= 6 and ISO_DATE_RE.search(cleaned[1] or ""):
        padded = cleaned + [""] * 7
        return (
            padded[0],
            padded[1],
            padded[2],
            padded[3],
            padded[4],
            padded[5],
            padded[6],
        )
    if len(cleaned) >= 7:
        padded = cleaned + [""] * 7
        return (
            padded[0],
            padded[1],
            padded[2],
            padded[3],
            padded[4],
            padded[5],
            padded[6],
        )
    padded = cleaned + [""] * 5
    return (
        padded[0],
        "",
        padded[1],
        padded[2],
        "",
        padded[3],
        padded[4],
    )


def _clean_cell(value: str) -> str:
    return re.sub(r"\*\*", "", value or "").replace("[S1]", "").replace("[S2]", "").replace("[S3]", "").replace("[S4]", "").replace("[S5]", "").strip()


def _resolve_date(day_name: str, iso: str, week_start: date) -> date | None:
    match = ISO_DATE_RE.search(iso) or ISO_DATE_RE.search(day_name)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            pass
    key = re.sub(r"[^a-z]", "", day_name.lower())
    if key in DAY_INDEX:
        return week_start + timedelta(days=DAY_INDEX[key])
    return None


def _split_combo(value: str, extra: str | None = None) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []
    pattern = r"\s+\+\s+"
    if extra:
        pattern = rf"{pattern}|{extra}"
    parts = [part.strip() for part in re.split(pattern, text) if part.strip()]
    return parts or [text]


def _split_durations(value: str) -> list[float]:
    text = value or ""
    if "+" in text:
        return [minutes for chunk in text.split("+") if (minutes := _first_duration(chunk))]
    minutes = _first_duration(text)
    return [minutes] if minutes else []


def _first_duration(value: str) -> float | None:
    match = DURATION_CHUNK_RE.search(value or "")
    if not match:
        return None
    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else None
    if high is not None:
        return round((low + high) / 2.0)
    return low


def _workout(
    workout_date: date,
    title: str,
    sport: str,
    duration: float | None,
    intensity: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "date": workout_date.isoformat(),
        "sport": (sport or "Training")[:64],
        "title": (title or "Session")[:200],
        "session_type": _infer_session_type(title, sport, intensity),
        "duration_min": duration,
        "distance_m": None,
        "intensity": (intensity or None),
        "description": notes or None,
        "structure": [],
    }


def _infer_session_type(title: str, sport: str, intensity: str) -> str:
    blob = f"{title} {sport} {intensity}".lower()
    if any(token in blob for token in ("football", "soccer", "11v11", "match")):
        return "cross-training"
    if any(token in blob for token in ("strength", "armor", "gym", "lift")):
        return "strength"
    if any(token in blob for token in ("yoga", "mobility", "decompress", "thoracic")):
        return "mobility"
    if "long" in blob:
        return "long"
    if any(token in blob for token in ("interval", "vo2", "threshold", "quality")):
        return "threshold"
    if any(token in blob for token in ("tempo", "moderate")):
        return "tempo"
    if "rest" in blob and "easy" not in blob:
        return "rest"
    return "easy"
