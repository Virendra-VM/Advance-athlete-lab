"""Power source resolution — measured vs Strava-estimated vs absent."""

from __future__ import annotations

from typing import Any, Literal

import re

from app.models import Activity
from app.services.activity_detail import activity_sport_family, parse_activity_detail


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

PowerSource = Literal["measured", "estimated", "absent"]

COACHING_NOTE_ESTIMATED = (
    "No power meter — Strava estimated watts are for reference only. "
    "Analysis uses heart rate, duration, and pace."
)
COACHING_NOTE_ABSENT = (
    "No power data — analysis uses heart rate, duration, and pace only."
)


def _strava_device_watts(detail: dict[str, Any]) -> bool | None:
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    if summary.get("device_watts") is True:
        return True
    if summary.get("device_watts") is False:
        return False
    raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    strava = raw.get("strava_detail")
    if isinstance(strava, dict):
        if strava.get("device_watts") is True:
            return True
        if strava.get("device_watts") is False:
            return False
    if detail.get("device_watts") is True:
        return True
    if detail.get("device_watts") is False:
        return False
    return None


def _has_power_values(summary: dict[str, Any], power_stream: bool) -> bool:
    if power_stream:
        return True
    for key in ("avg_power", "normalized_power", "max_power"):
        value = summary.get(key)
        if value is not None and float(value) > 0:
            return True
    return False


def resolve_power_source(
    activity: Activity,
    detail: dict[str, Any] | None = None,
    *,
    power_stream_present: bool = False,
) -> PowerSource:
    """Classify session power: measured meter, Strava estimate, or absent."""
    parsed = detail if detail is not None else (parse_activity_detail(activity) or {})
    summary = parsed.get("summary") if isinstance(parsed.get("summary"), dict) else {}
    family = activity_sport_family(activity.sport_type)
    device_watts = _strava_device_watts(parsed)

    if device_watts is True:
        return "measured"

    has_power = _has_power_values(summary, power_stream_present)

    if family == "run":
        # Run power is rarely from a meter in this app; treat as absent unless flagged.
        if device_watts is True:
            return "measured"
        if has_power and device_watts is False:
            return "estimated"
        return "absent"

    if family == "ride" or _looks_like_ride(activity.sport_type):
        if device_watts is False:
            return "estimated"
        if device_watts is True:
            return "measured"
        if has_power and (activity.provider or "") == "strava":
            # Legacy rows without device_watts on outdoor Strava rides — assume estimated.
            return "estimated"
        if has_power:
            return "measured"
        return "absent"

    if not has_power:
        return "absent"
    if device_watts is False:
        return "estimated"
    if device_watts is True:
        return "measured"
    return "estimated" if (activity.provider or "") == "strava" else "measured"


def should_compute_power_load_metrics(power_source: PowerSource) -> bool:
    return power_source == "measured"


def power_coaching_note(power_source: PowerSource, family: str) -> str | None:
    if power_source == "estimated":
        return COACHING_NOTE_ESTIMATED
    if power_source == "absent":
        if family in {"run", "ride"}:
            return COACHING_NOTE_ABSENT
    return None


def seed_strava_summary_fields(activity_payload: dict[str, Any]) -> dict[str, Any]:
    """Build summary seed fields from a Strava activity API object."""
    summary: dict[str, Any] = {}
    if "device_watts" in activity_payload:
        summary["device_watts"] = bool(activity_payload.get("device_watts"))
    if activity_payload.get("average_watts") is not None:
        summary["avg_power"] = activity_payload.get("average_watts")
    if activity_payload.get("weighted_average_watts") is not None:
        summary["normalized_power"] = activity_payload.get("weighted_average_watts")
    if activity_payload.get("max_watts") is not None:
        summary["max_power"] = activity_payload.get("max_watts")
    return summary
