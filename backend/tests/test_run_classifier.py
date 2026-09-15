"""Phase 2 — sport-correct run classification and plan-vs-executed headlines."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.ai_coach import autopsy_task_for_packet, template_quick_debrief
from app.services.session_plan import build_execution_headline
from app.services.session_telemetry import (
    analyze_activity,
    classify_run_session,
    classify_ride_without_measured_power,
)


def test_classify_run_easy_when_pace_and_hr_easy():
    label = classify_run_session(
        pace_sec_per_km=360,
        threshold_pace_sec_per_km=300,
        avg_hr=130,
        lthr=168,
    )
    assert label == "easy"


def test_classify_run_sunday_scenario_steady_not_easy():
    """User Sunday run: slow pace but HR ~83% LTHR — must not call easy."""
    # 13 km in 88 min → 406 sec/km; threshold ~340 sec/km (5:40/km)
    label = classify_run_session(
        pace_sec_per_km=406,
        threshold_pace_sec_per_km=340,
        avg_hr=145,
        lthr=174,
    )
    assert label == "steady"
    assert label != "easy"


def test_classify_run_tempo_when_fast_pace():
    # ~99% of threshold pace → tempo/threshold band
    label = classify_run_session(
        pace_sec_per_km=336,
        threshold_pace_sec_per_km=340,
        avg_hr=135,
        lthr=174,
    )
    assert label == "tempo"


def test_classify_run_hard_when_hr_high():
    label = classify_run_session(
        pace_sec_per_km=400,
        threshold_pace_sec_per_km=340,
        avg_hr=168,
        lthr=174,
    )
    assert label == "hard"


def test_ride_without_meter_never_sweet_spot():
    label = classify_ride_without_measured_power(
        avg_hr=150,
        lthr=168,
        hr_time=[{"name": "Z3 tempo", "pct": 30}],
        duration_min=90,
    )
    assert label in {"moderate", "endurance", "aerobic", "easy", "long"}
    assert label != "sweet-spot"


def test_analyze_sunday_run_packet():
    activity = SimpleNamespace(
        id=2,
        athlete_profile_id=1,
        name="Sunday Long Run",
        sport_type="Run",
        provider="strava",
        external_activity_id="1001",
        strava_activity_id=1001,
        moving_time_s=5280,
        distance_m=13000,
        average_heartrate=145,
        max_heartrate=165,
        detail_json=json.dumps(
            {
                "summary": {"avg_hr": 145},
                "laps": [{"index": 1, "duration_s": 5280, "avg_hr": 145}],
            }
        ),
        points_file_path=None,
    )
    packet = analyze_activity(
        activity,
        {
            "ftp_watts": 232,
            "lthr_bpm": 174,
            "max_hr_bpm": 192,
            "threshold_pace_sec_per_km": 340,
            "ftp_source": "manual",
        },
    )
    assert packet["family"] == "run"
    assert packet["classification"] in {"steady", "tempo"}
    assert packet["classification"] != "easy"
    assert packet["classification"] != "sweet-spot"
    assert packet["power"]["tss"] is None
    assert packet["run_intensity"]["pace_label"] == "easy"
    assert packet["run_intensity"]["hr_label"] == "steady"
    assert packet["run_intensity"]["signals"] == ["pace", "hr"]


def test_execution_headline_easy_run_mismatch():
    telemetry = {
        "minutes": 88,
        "km": 13.0,
        "pace_min_per_km": 6.77,
        "family": "run",
        "classification": "steady",
        "heart_rate": {"avg_bpm": 145, "pct_lthr_avg": 83},
        "run_intensity": {
            "pace_sec_per_km": 406,
            "threshold_pace_sec_per_km": 340,
            "pct_threshold_pace": 119.4,
            "pace_label": "easy",
            "hr_label": "steady",
        },
    }
    week = {
        "title": "Easy long run",
        "session_type": "easy",
        "duration_min": 60,
        "intensity": "conversational",
    }
    headline = build_execution_headline(week, telemetry)
    assert headline is not None
    assert headline["intensity_mismatch"] is True
    assert headline["duration_longer"] is True
    assert "not easy" in (headline["headline"] or "").lower()
    assert "83% LTHR" in (headline["headline"] or "")


def test_template_quick_debrief_run_uses_pace_hr_not_watts():
    reply = template_quick_debrief(
        "Quick debrief Sunday run",
        {"load": {"minutes_acwr": 1.1}},
        [],
        session_packet={
            "name": "Sunday Long Run",
            "when": "Sunday",
            "minutes": 88,
            "km": 13.0,
            "pace_min_per_km": 6.77,
            "family": "run",
            "sport": "Run",
            "modality": "run",
            "classification": "steady",
            "power": {
                "source": "absent",
                "coaching_note": "Runs use pace and HR — no watt load.",
            },
            "heart_rate": {"avg_bpm": 145, "max_bpm": 165, "pct_lthr_avg": 83},
            "run_intensity": {
                "pct_threshold_pace": 119,
                "pace_label": "easy",
                "hr_label": "steady",
            },
            "execution_headline": {
                "headline": (
                    "88 min / 13.0 km at 6.77 min/km — longer than your 60 min Easy long run — "
                    "not easy vs plan — HR 145 avg (83% LTHR)"
                ),
                "intensity_mismatch": True,
            },
            "laps": [],
            "work_laps": [],
        },
    )
    text = reply["reply"]
    assert "88 min / 13" in text
    assert "📋 VS PLAN" in text
    assert reply.get("debrief_mode") == "quick"
    assert "sweet-spot" not in text.lower()
    assert "IF " not in text


def test_autopsy_task_includes_execution_headline():
    task = autopsy_task_for_packet(
        "run",
        {
            "execution_headline": {
                "headline": "88 min / 13 km — not easy vs plan",
            },
            "power": {"source": "absent"},
        },
    )
    assert "execution_headline" in task
    assert "88 min / 13 km" in task
