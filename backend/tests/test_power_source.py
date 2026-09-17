"""Phase 1 — measured vs estimated power source resolution."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.activity_detail import build_normalized_detail
from app.services.power_source import (
    resolve_power_source,
    seed_strava_summary_fields,
    should_compute_power_load_metrics,
)
from app.services.session_telemetry import analyze_activity
from app.services.strava_sync import api_activity_to_metadata


def _activity(
    *,
    sport_type: str = "Ride",
    provider: str = "strava",
    detail: dict | None = None,
    moving_time_s: int = 3600,
    distance_m: float = 60000,
    avg_hr: float = 138,
):
    return SimpleNamespace(
        id=1,
        athlete_profile_id=1,
        name="Morning Ride",
        sport_type=sport_type,
        provider=provider,
        external_activity_id="999",
        strava_activity_id=999,
        moving_time_s=moving_time_s,
        distance_m=distance_m,
        average_heartrate=avg_hr,
        max_heartrate=170,
        detail_json=json.dumps(detail or {}),
        points_file_path=None,
    )


def test_strava_api_metadata_captures_device_watts():
    meta = api_activity_to_metadata(
        {
            "id": 123,
            "name": "Outdoor Ride",
            "sport_type": "Ride",
            "distance": 50000,
            "moving_time": 7200,
            "device_watts": False,
            "average_watts": 112,
            "weighted_average_watts": 115,
        }
    )
    assert meta["device_watts"] is False
    assert meta["strava_summary_seed"]["device_watts"] is False
    assert meta["strava_summary_seed"]["avg_power"] == 112


def test_build_normalized_detail_preserves_device_watts():
    detail = build_normalized_detail(
        sport_type="Ride",
        strava_detail={"device_watts": False, "average_watts": 112},
    )
    assert detail["summary"]["device_watts"] is False
    assert detail["summary"]["avg_power"] == 112


def test_resolve_estimated_outdoor_strava_ride():
    activity = _activity(
        detail={
            "summary": {"device_watts": False, "avg_power": 112},
            "laps": [{"index": 1, "duration_s": 3600, "avg_power": 112}],
        }
    )
    assert resolve_power_source(activity, power_stream_present=True) == "estimated"


def test_resolve_measured_when_device_watts_true():
    activity = _activity(
        detail={"summary": {"device_watts": True, "avg_power": 220}},
    )
    assert resolve_power_source(activity, power_stream_present=True) == "measured"
    assert should_compute_power_load_metrics("measured") is True


def test_resolve_run_absent_without_power():
    activity = _activity(
        sport_type="Run",
        detail={"summary": {}, "laps": []},
    )
    assert resolve_power_source(activity, power_stream_present=False) == "absent"


def test_analyze_estimated_ride_skips_if_tss():
    activity = _activity(
        detail={
            "summary": {"device_watts": False, "avg_power": 112, "avg_hr": 138},
            "laps": [
                {"index": 1, "duration_s": 3600, "avg_power": 112, "avg_hr": 138},
            ],
        },
        moving_time_s=16620,
        distance_m=60050,
    )
    packet = analyze_activity(
        activity,
        {"ftp_watts": 232, "lthr_bpm": 168, "max_hr_bpm": 192, "ftp_source": "manual"},
    )
    assert packet["power"]["source"] == "estimated"
    assert packet["power"]["coaching_note"] is not None
    assert packet["power"]["intensity_factor"] is None
    assert packet["power"]["tss"] is None
    assert packet["power"]["np_w"] is None
    assert packet["power"]["reference_avg_w"] == 112
    assert packet["time_in_power_zones"] == []
    assert packet["work_lap_count"] == 0
    assert packet["classification"] in {"endurance", "aerobic", "moderate", "easy", "steady", "long"}


def test_analyze_measured_ride_keeps_if_tss():
    activity = _activity(
        detail={
            "summary": {"device_watts": True, "avg_power": 200},
            "laps": [{"index": 1, "duration_s": 3600, "avg_power": 200, "avg_hr": 150}],
        },
    )
    packet = analyze_activity(
        activity,
        {"ftp_watts": 232, "lthr_bpm": 168, "max_hr_bpm": 192, "ftp_source": "manual"},
    )
    assert packet["power"]["source"] == "measured"
    assert packet["power"]["intensity_factor"] is not None
    assert packet["power"]["tss"] is not None


def test_analyze_run_no_sweet_spot_from_estimated_power():
    activity = _activity(
        sport_type="Run",
        detail={
            "summary": {"avg_power": 204, "device_watts": False, "avg_hr": 145},
            "laps": [{"index": 1, "duration_s": 5280, "avg_power": 204, "avg_hr": 145}],
        },
        moving_time_s=5280,
        distance_m=13000,
        avg_hr=145,
    )
    packet = analyze_activity(
        activity,
        {"ftp_watts": 232, "lthr_bpm": 168, "max_hr_bpm": 192, "ftp_source": "manual"},
    )
    assert packet["power"]["source"] in {"absent", "estimated"}
    assert packet["power"]["tss"] is None
    assert packet["classification"] in {"easy", "steady", "tempo", "hard", "continuous"}
    assert packet["classification"] != "sweet-spot"
