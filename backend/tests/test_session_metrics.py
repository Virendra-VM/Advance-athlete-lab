"""Phase 4 — unified COROS-first metric resolution and source tagging."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.activity_detail import build_normalized_detail
from app.services.session_metrics import resolve_session_metrics
from app.services.session_telemetry import analyze_activity


def _activity(**kwargs):
    detail = kwargs.pop("detail", {})
    defaults = {
        "id": 1,
        "athlete_profile_id": 1,
        "name": "Session",
        "sport_type": kwargs.pop("sport_type", "Run"),
        "provider": kwargs.pop("provider", "strava"),
        "external_activity_id": "100",
        "strava_activity_id": 100,
        "moving_time_s": kwargs.pop("moving_time_s", 3600),
        "distance_m": kwargs.pop("distance_m", 10000),
        "average_heartrate": kwargs.pop("average_heartrate", None),
        "max_heartrate": kwargs.pop("max_heartrate", None),
        "detail_json": json.dumps(detail),
        "points_file_path": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_coros_hr_and_pace_preferred_over_strava():
    detail = build_normalized_detail(
        sport_type="Run",
        coros_detail={"avgHeartRate": 142, "avgPace": 5.5, "avgCadence": 172},
        strava_detail={"average_heartrate": 150, "average_watts": 204, "device_watts": False},
    )
    activity = _activity(detail=detail, provider="strava", average_heartrate=150)
    resolution = resolve_session_metrics(activity, detail=detail)
    src = resolution["metrics_source"]
    assert src["hr"] == "coros"
    assert src["pace"] == "coros"
    assert src["power"] == "strava_estimated"
    assert src["power_load"] == "absent"
    assert resolution["resolved"]["avg_hr"] == 142
    assert resolution["resolved"]["pace_min_per_km"] == 5.5


def test_pace_recalculated_when_no_summary_pace():
    detail = build_normalized_detail(
        sport_type="Run",
        strava_detail={"device_watts": False},
    )
    activity = _activity(
        detail=detail,
        moving_time_s=5280,
        distance_m=13000,
        average_heartrate=145,
    )
    resolution = resolve_session_metrics(activity, detail=detail, duration_s=5280)
    assert resolution["metrics_source"]["pace"] == "recalculated"
    assert resolution["pace_recalculated"] is True
    assert resolution["resolved"]["pace_min_per_km"] == 6.77


def test_streams_override_summary_hr():
    detail = build_normalized_detail(
        sport_type="Ride",
        coros_detail={"avgHeartRate": 140},
        strava_detail={"average_watts": 200, "device_watts": True},
    )
    activity = _activity(
        sport_type="Ride",
        detail=detail,
        provider="strava",
    )
    resolution = resolve_session_metrics(
        activity,
        detail=detail,
        stream_hr=[150.0] * 100,
        stream_power=[210.0] * 100,
    )
    assert resolution["metrics_source"]["hr"] == "streams"
    assert resolution["metrics_source"]["power"] == "streams"
    assert resolution["metrics_source"]["power_load"] == "measured"
    assert resolution["resolved"]["avg_hr"] == 150.0


def test_laps_source_coros_when_coros_laps_present():
    detail = build_normalized_detail(
        sport_type="Run",
        coros_detail={"avgHeartRate": 140},
        coros_laps=[{"duration": 600, "avgHeartRate": 138}],
        strava_laps=[{"elapsed_time": 600, "average_heartrate": 145}],
    )
    assert detail["laps"]
    resolution = resolve_session_metrics(_activity(detail=detail), detail=detail)
    assert resolution["metrics_source"]["laps"] == "coros"
    assert "coros" in resolution["metrics_source"]["detail_sources"]


def test_analyze_activity_includes_metrics_source():
    detail = build_normalized_detail(
        sport_type="Run",
        coros_detail={"avgHeartRate": 145, "avgPace": 6.77},
        strava_detail={"average_watts": 204, "device_watts": False},
    )
    activity = _activity(
        detail=detail,
        moving_time_s=5280,
        distance_m=13000,
        sport_type="Run",
    )
    packet = analyze_activity(
        activity,
        {
            "ftp_watts": 232,
            "lthr_bpm": 174,
            "max_hr_bpm": 192,
            "threshold_pace_sec_per_km": 340,
        },
    )
    assert packet["metrics_source"]["hr"] == "coros"
    assert packet["metrics_source"]["power"] == "strava_estimated"
    assert packet["power"]["source"] == "estimated"
    assert packet["power"]["tss"] is None
    assert packet["heart_rate"]["avg_bpm"] == 145


def test_measured_strava_ride_power_source():
    detail = build_normalized_detail(
        sport_type="Ride",
        strava_detail={"average_watts": 200, "device_watts": True},
    )
    activity = _activity(sport_type="Ride", detail=detail)
    resolution = resolve_session_metrics(activity, detail=detail)
    assert resolution["metrics_source"]["power"] == "strava_measured"
    assert resolution["power_source"] == "measured"
