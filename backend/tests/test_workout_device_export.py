"""Phase 5 — device export (FIT / ZWO / JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_device_export import (  # noqa: E402
    build_device_export,
    encode_fit_workout,
    encode_zwo_workout,
    template_to_device_steps,
    validate_fit_bytes,
)
from app.services.workout_library import get_template_by_id


def test_template_to_device_steps_threshold_repeat():
    template = get_template_by_id("run_threshold_2x10_lthr1")
    assert template is not None
    steps = template_to_device_steps(
        template,
        {"duration_min": 50, "sport": "Running"},
        {"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
    )
    assert steps[0]["role"] == "warmup"
    assert steps[-1]["role"] == "cooldown"
    work_steps = [step for step in steps if step["role"] == "interval"]
    assert len(work_steps) == 2
    assert work_steps[0]["target"]["type"] == "heart_rate"


def test_encode_fit_running_workout():
    template = get_template_by_id("run_easy_z2")
    steps = template_to_device_steps(
        template,
        {"duration_min": 45, "sport": "Running"},
        {"lthr_bpm": 170},
    )
    fit_bytes = encode_fit_workout(steps, sport="running", title="Easy Z2")
    report = validate_fit_bytes(fit_bytes)
    assert report["valid"]
    assert report["step_count"] == len(steps)
    assert report["sport"] == "running"


def test_encode_fit_cycling_power_targets():
    template = get_template_by_id("bike_sweet_spot_2x20")
    assert template is not None
    steps = template_to_device_steps(
        template,
        {"duration_min": 70, "sport": "Cycling"},
        {"ftp_watts": 250},
    )
    fit_bytes = encode_fit_workout(steps, sport="cycling", title="Sweet spot")
    report = validate_fit_bytes(fit_bytes)
    assert report["valid"]
    assert report["sport"] == "cycling"
    power_steps = [step for step in steps if step.get("target", {}).get("type") == "power"]
    assert power_steps


def test_encode_zwo_cycling():
    template = get_template_by_id("bike_sweet_spot_2x20")
    steps = template_to_device_steps(
        template,
        {"duration_min": 70, "sport": "Cycling"},
        {"ftp_watts": 250},
    )
    zwo = encode_zwo_workout(steps, title="Sweet spot", physiology={"ftp_watts": 250})
    assert "<workout_file>" in zwo
    assert "sportType>bike" in zwo
    assert "SteadyState" in zwo or "IntervalsT" in zwo


def test_build_device_export_package():
    package = build_device_export(
        {
            "library_template_id": "run_threshold_2x10_lthr1",
            "duration_min": 50,
            "sport": "Running",
            "title": "Threshold repeats",
        },
        physiology={"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
    )
    assert package["export_version"] == "1.0.0"
    assert package["template_id"] == "run_threshold_2x10_lthr1"
    assert "fit" in package["formats"]
    assert "json" in package["formats"]
    assert validate_fit_bytes(package["formats"]["fit"]["bytes"])["valid"]
    json_payload = package["formats"]["json"]["payload"]
    assert len(json_payload["steps"]) >= 4


def test_build_device_export_cycling_includes_zwo():
    package = build_device_export(
        {
            "library_template_id": "bike_sweet_spot_2x20",
            "duration_min": 70,
            "sport": "Cycling",
            "title": "Sweet spot",
        },
        physiology={"ftp_watts": 250},
    )
    assert "zwo" in package["formats"]
    assert ".zwo" in package["formats"]["zwo"]["filename"]


def test_fit_roundtrip_step_count_matches():
    template = get_template_by_id("run_tempo_steady")
    steps = template_to_device_steps(
        template,
        {"duration_min": 55, "sport": "Running"},
        {"lthr_bpm": 168},
    )
    fit_bytes = encode_fit_workout(steps, sport="running", title="Tempo")
    report = validate_fit_bytes(fit_bytes)
    assert report["step_count"] == len(steps)
