"""B-race result calibration — Riegel projection toward A-race target."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteProfile, SeasonPlan

DISTANCE_METERS = {
    "5k": 5000.0,
    "10k": 10000.0,
    "half": 21097.5,
    "half_marathon": 21097.5,
    "marathon": 42195.0,
}

RIEGEL_EXPONENT = 1.06


def parse_duration_seconds(text: str | None) -> float | None:
    if not text:
        return None
    raw = str(text).strip().lower()
    if not raw:
        return None

    if raw.endswith("s") and raw[:-1].replace(".", "", 1).isdigit():
        return float(raw[:-1])

    match = re.match(r"^(\d+):(\d{2})(?::(\d{2}))?$", raw)
    if match:
        first = int(match.group(1))
        second = int(match.group(2))
        third = int(match.group(3) or 0)
        if match.group(3) is not None:
            return float(first * 3600 + second * 60 + third)
        if first >= 60:
            return float(first * 3600 + second * 60)
        return float(first * 60 + second)

    match = re.match(r"^(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s+(\d+)\s*m(?:in)?)?$", raw)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2) or 0)
        return hours * 3600 + minutes * 60

    match = re.match(r"^(\d+(?:\.\d+)?)\s*min(?:utes?)?$", raw)
    if match:
        return float(match.group(1)) * 60

    return None


def infer_race_distance_meters(event: AthleteEvent) -> float | None:
    haystack = " ".join(
        filter(
            None,
            [
                event.name or "",
                event.target_metric or "",
                event.result_metric or "",
                event.sport_type or "",
            ],
        )
    ).lower()

    if "marathon" in haystack and "half" not in haystack:
        return DISTANCE_METERS["marathon"]
    if "half" in haystack:
        return DISTANCE_METERS["half"]
    if re.search(r"\b10\s*k\b|\b10k\b", haystack):
        return DISTANCE_METERS["10k"]
    if re.search(r"\b5\s*k\b|\b5k\b", haystack):
        return DISTANCE_METERS["5k"]

    sport = (event.sport_type or "").lower()
    if sport in {"bike", "cycling", "ride"}:
        return None
    return DISTANCE_METERS["10k"]


def riegel_predict(time_seconds: float, distance_a: float, distance_b: float) -> float:
    if distance_a <= 0 or distance_b <= 0:
        return time_seconds
    return time_seconds * ((distance_b / distance_a) ** RIEGEL_EXPONENT)


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def assess_feasibility(
    predicted_seconds: float | None,
    target_seconds: float | None,
) -> str:
    if predicted_seconds is None or target_seconds is None:
        return "unknown"
    ratio = predicted_seconds / target_seconds
    if ratio <= 1.03:
        return "on_track"
    if ratio <= 1.08:
        return "stretch"
    return "unlikely"


def calibrate_from_b_race(
    b_event: AthleteEvent,
    a_event: AthleteEvent | None,
    *,
    result_metric: str | None = None,
) -> dict[str, Any]:
    result_text = result_metric or b_event.result_metric
    b_time = parse_duration_seconds(result_text)
    b_distance = infer_race_distance_meters(b_event)
    if b_time is None or b_distance is None:
        return {
            "available": False,
            "message": "Could not parse B-race time or distance for calibration.",
        }

    a_distance = infer_race_distance_meters(a_event) if a_event else DISTANCE_METERS["half"]
    predicted_a_seconds = riegel_predict(b_time, b_distance, a_distance)
    target_a_seconds = parse_duration_seconds(a_event.target_metric if a_event else None)
    feasibility = assess_feasibility(predicted_a_seconds, target_a_seconds)

    peak_note = {
        "on_track": "Peak phase can keep race-pace work — projection supports the A-race target.",
        "stretch": "Peak phase should stay controlled — B-race projection is slightly slower than A target.",
        "unlikely": "Peak phase should emphasize aerobic durability — A-race target looks aggressive vs B-race.",
        "unknown": "Peak phase pacing should stay conservative until an A-race target time is set.",
    }[feasibility]

    return {
        "available": True,
        "b_race": b_event.name,
        "b_distance_m": b_distance,
        "b_time_seconds": round(b_time, 1),
        "b_time_formatted": format_duration(b_time),
        "predicted_a_time_seconds": round(predicted_a_seconds, 1),
        "predicted_a_time_formatted": format_duration(predicted_a_seconds),
        "a_race_target_seconds": target_a_seconds,
        "a_race_feasibility": feasibility,
        "peak_pace_note": peak_note,
    }


def complete_b_race_event(
    db: Session,
    profile: AthleteProfile,
    event: AthleteEvent,
    *,
    result_metric: str | None = None,
) -> dict[str, Any]:
    if event.priority != "B":
        raise ValueError("Only B-priority events support pace calibration.")
    if event.athlete_profile_id != profile.id:
        raise ValueError("Event does not belong to this athlete.")

    event.status = "completed"
    event.result_metric = result_metric or event.result_metric
    event.updated_at = datetime.utcnow()

    a_event = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.athlete_profile_id == profile.id,
            AthleteEvent.priority == "A",
            AthleteEvent.status == "planned",
        )
        .order_by(AthleteEvent.event_date.asc())
        .first()
    )
    calibration = calibrate_from_b_race(event, a_event, result_metric=event.result_metric)

    plan = (
        db.query(SeasonPlan)
        .filter(
            SeasonPlan.athlete_profile_id == profile.id,
            SeasonPlan.status == "active",
        )
        .order_by(SeasonPlan.created_at.desc())
        .first()
    )
    if plan and calibration.get("available"):
        warnings: list[str] = []
        if plan.warnings_json:
            try:
                warnings = json.loads(plan.warnings_json)
            except json.JSONDecodeError:
                warnings = []
        warnings.append(
            "B-race calibration: "
            f"projected A-race {calibration['predicted_a_time_formatted']} "
            f"({calibration['a_race_feasibility']}). "
            f"{calibration['peak_pace_note']}"
        )
        plan.warnings_json = json.dumps(warnings)

    db.commit()
    return {
        "event_id": event.id,
        "status": event.status,
        "result_metric": event.result_metric,
        "calibration": calibration,
    }
