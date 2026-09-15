"""Phase 4 — unified COROS-first session metric resolution and source tagging."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models import Activity
from app.services.activity_detail import activity_sport_family, parse_activity_detail
from app.services.activity_detail import _extract_summary  # noqa: PLC2701
from app.services.power_source import resolve_power_source


def _mean_positive(values: list[float | None], *, floor: float = 0) -> float | None:
    numbers = [float(v) for v in values if v is not None and float(v) > floor]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _round(value: float | None, places: int = 0) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _pace_min_per_km_from_activity(activity: Activity, duration_s: float) -> tuple[float | None, bool]:
    """Return (pace min/km, recalculated from distance+duration)."""
    if not activity.distance_m or not duration_s or activity.distance_m < 50:
        return None, False
    pace = (duration_s / 60.0) / (activity.distance_m / 1000.0)
    return _round(pace, 2), True


def _detail_layers(detail: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    coros_summary = _extract_summary(raw.get("coros_detail"))
    strava_summary = _extract_summary(raw.get("strava_detail"))
    merged = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    return coros_summary, strava_summary, merged


def _has_coros(detail: dict[str, Any]) -> bool:
    sources = detail.get("sources")
    if isinstance(sources, list) and "coros" in sources:
        return True
    raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    return raw.get("coros_detail") is not None or raw.get("coros_laps") is not None


def _has_strava(detail: dict[str, Any]) -> bool:
    sources = detail.get("sources")
    if isinstance(sources, list) and "strava" in sources:
        return True
    raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    return raw.get("strava_detail") is not None


def _laps_source(detail: dict[str, Any]) -> str:
    laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
    if not laps:
        return "none"
    raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    if raw.get("coros_laps") or _has_coros(detail):
        return "coros"
    if _has_strava(detail):
        return "strava"
    return "unknown"


def _hr_zones_source(
    detail: dict[str, Any],
    *,
    stream_hr: list[float | None],
    stream_hr_zones: list[dict[str, Any]] | None,
) -> str:
    zones = detail.get("zones") if isinstance(detail.get("zones"), dict) else {}
    if stream_hr_zones:
        return "streams"
    if isinstance(zones.get("hr"), list) and zones.get("hr"):
        return "coros" if _has_coros(detail) else "strava"
    if any(v and v > 30 for v in stream_hr):
        return "computed"
    return "none"


def resolve_session_metrics(
    activity: Activity,
    *,
    detail: dict[str, Any] | None = None,
    frame: pd.DataFrame | None = None,
    stream_power: list[float | None] | None = None,
    stream_hr: list[float | None] | None = None,
    stream_cadence: list[float | None] | None = None,
    duration_s: float | None = None,
) -> dict[str, Any]:
    """Resolve metric values with COROS-first policy and per-field source tags."""
    parsed = detail if detail is not None else (parse_activity_detail(activity) or {})
    coros_summary, strava_summary, merged_summary = _detail_layers(parsed)

    stream_power = stream_power or []
    stream_hr = stream_hr or []
    stream_cadence = stream_cadence or []
    has_streams = frame is not None and not frame.empty

    duration = float(duration_s if duration_s is not None else (activity.moving_time_s or 0))

    # --- Heart rate ---
    stream_avg_hr = _mean_positive(stream_hr, floor=30)
    stream_max_hr = max((float(v) for v in stream_hr if v and v > 30), default=None)

    if stream_avg_hr is not None:
        avg_hr = stream_avg_hr
        hr_source = "streams"
    elif coros_summary.get("avg_hr") is not None:
        avg_hr = _round(coros_summary.get("avg_hr"), 0)
        hr_source = "coros"
    elif activity.average_heartrate:
        avg_hr = _round(activity.average_heartrate, 0)
        hr_source = "coros" if _has_coros(parsed) and not _has_strava(parsed) else (
            "strava" if (activity.provider or "") == "strava" else "activity_row"
        )
    elif strava_summary.get("avg_hr") is not None:
        avg_hr = _round(strava_summary.get("avg_hr"), 0)
        hr_source = "strava"
    elif merged_summary.get("avg_hr") is not None:
        avg_hr = _round(merged_summary.get("avg_hr"), 0)
        hr_source = "coros" if coros_summary.get("avg_hr") is not None else "strava"
    else:
        avg_hr = None
        hr_source = "unknown"

    if stream_max_hr is not None:
        max_hr = _round(stream_max_hr, 0)
        max_hr_source = "streams"
    elif coros_summary.get("max_hr") is not None:
        max_hr = _round(coros_summary.get("max_hr"), 0)
        max_hr_source = "coros"
    elif activity.max_heartrate:
        max_hr = _round(activity.max_heartrate, 0)
        max_hr_source = "activity_row"
    elif strava_summary.get("max_hr") is not None:
        max_hr = _round(strava_summary.get("max_hr"), 0)
        max_hr_source = "strava"
    else:
        max_hr = _round(merged_summary.get("max_hr"), 0)
        max_hr_source = "unknown"

    # --- Pace (COROS first, then recalc, then Strava) ---
    pace_recalculated = False
    pace_min_km: float | None = None
    pace_source = "unknown"

    if coros_summary.get("avg_pace") is not None:
        pace_min_km = _round(coros_summary.get("avg_pace"), 2)
        pace_source = "coros"
    else:
        computed, recalc = _pace_min_per_km_from_activity(activity, duration)
        if computed is not None:
            pace_min_km = computed
            pace_recalculated = recalc
            pace_source = "recalculated"
        elif strava_summary.get("avg_pace") is not None:
            pace_min_km = _round(strava_summary.get("avg_pace"), 2)
            pace_source = "strava"
        elif merged_summary.get("avg_pace") is not None:
            pace_min_km = _round(merged_summary.get("avg_pace"), 2)
            pace_source = "strava" if strava_summary.get("avg_pace") is not None else "coros"

    # --- Cadence ---
    stream_cadence_avg = _mean_positive(stream_cadence, floor=20)
    if stream_cadence_avg is not None:
        cadence_avg = _round(stream_cadence_avg, 0)
        cadence_source = "streams"
    elif coros_summary.get("avg_cadence") is not None:
        cadence_avg = _round(coros_summary.get("avg_cadence"), 0)
        cadence_source = "coros"
    elif strava_summary.get("avg_cadence") is not None:
        cadence_avg = _round(strava_summary.get("avg_cadence"), 0)
        cadence_source = "strava"
    elif merged_summary.get("avg_cadence") is not None:
        cadence_avg = _round(merged_summary.get("avg_cadence"), 0)
        cadence_source = "coros" if coros_summary.get("avg_cadence") is not None else "strava"
    else:
        cadence_avg = None
        cadence_source = "none"

    # --- Power (streams > coros > strava; estimated never load-driving) ---
    power_stream_present = bool(any(v and v > 0 for v in stream_power))
    power_source_kind = resolve_power_source(
        activity,
        parsed,
        power_stream_present=power_stream_present,
    )

    if power_stream_present:
        power_metric_source = "streams"
        avg_power = _mean_positive(stream_power)
    elif coros_summary.get("avg_power") is not None and _has_coros(parsed):
        avg_power = _round(coros_summary.get("avg_power"), 0)
        power_metric_source = "coros"
    elif strava_summary.get("avg_power") is not None or merged_summary.get("avg_power") is not None:
        avg_power = _round(
            strava_summary.get("avg_power") or merged_summary.get("avg_power"),
            0,
        )
        if power_source_kind == "measured":
            power_metric_source = "strava_measured"
        elif power_source_kind == "estimated":
            power_metric_source = "strava_estimated"
        else:
            power_metric_source = "strava"
    else:
        avg_power = None
        power_metric_source = "absent" if power_source_kind == "absent" else "unknown"

    laps_source = _laps_source(parsed)

    detail_sources = parsed.get("sources") if isinstance(parsed.get("sources"), list) else []
    if not detail_sources:
        detail_sources = [name for name, flag in (("coros", _has_coros(parsed)), ("strava", _has_strava(parsed))) if flag]

    metrics_source = {
        "hr": hr_source,
        "max_hr": max_hr_source,
        "pace": pace_source,
        "power": power_metric_source,
        "power_load": power_source_kind if power_source_kind == "measured" else "absent",
        "laps": laps_source,
        "hr_zones": _hr_zones_source(parsed, stream_hr=stream_hr, stream_hr_zones=None),
        "duration": "activity_row",
        "distance": "activity_row",
        "cadence": cadence_source,
        "provider": activity.provider or "unknown",
        "detail_sources": detail_sources,
    }

    return {
        "metrics_source": metrics_source,
        "pace_recalculated": pace_recalculated,
        "has_streams": has_streams,
        "resolved": {
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "pace_min_per_km": pace_min_km,
            "avg_cadence": cadence_avg,
            "reference_avg_power": avg_power if power_source_kind != "measured" else None,
            "avg_power": avg_power if power_source_kind == "measured" else None,
        },
        "power_source": power_source_kind,
        "family": activity_sport_family(activity.sport_type),
    }
