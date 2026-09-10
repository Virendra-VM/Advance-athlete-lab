"""Phase 4 — SWL compliance scoring and library prescription bridge."""

from __future__ import annotations

import sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_compliance import (  # noqa: E402
    build_template_prescription,
    grade_from_score,
    resolve_numeric_targets,
    score_planned_vs_executed,
)
from app.services.workout_library import get_template_by_id


def test_resolve_numeric_targets_lthr_and_ftp():
    targets = {
        "hr_pct_lthr": {"low": 0.95, "high": 1.02},
        "pct_ftp": {"low": 0.91, "high": 1.05},
    }
    resolved = resolve_numeric_targets(
        targets,
        {"ftp_watts": 250, "lthr_bpm": 170},
    )
    assert resolved["hr_bpm"]["low"] == 161.5
    assert resolved["power_w"]["high"] == 262.5


def test_build_template_prescription_from_threshold_template():
    template = get_template_by_id("run_threshold_2x10_lthr1")
    assert template is not None
    prescription = build_template_prescription(
        template,
        {"duration_min": 50},
        {"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
    )
    assert prescription["source"] == "library_template"
    assert prescription["template_id"] == "run_threshold_2x10_lthr1"
    assert prescription["step_count"] >= 4
    work_steps = [step for step in prescription["steps"] if step.get("role") == "work"]
    assert len(work_steps) == 2
    assert work_steps[0]["targets"]["hr_bpm"]["low"] > 160


def test_score_planned_vs_executed_run_threshold():
    template = get_template_by_id("run_threshold_2x10_lthr1")
    planned = {
        "library_template_id": template["id"],
        "duration_min": 50,
        "session_type": "threshold",
    }
    telemetry = {
        "minutes": 52,
        "heart_rate": {"avg_bpm": 168, "pct_lthr_avg": 99},
        "classification": "threshold",
    }
    report = score_planned_vs_executed(
        planned,
        telemetry,
        {"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
    )
    assert report["score"] >= 70
    assert report["grade"] in {"A", "B", "C"}
    assert report["prescription"]["template_id"] == "run_threshold_2x10_lthr1"
    assert report["prescribed_vs_executed"]["source"] == "library_template"


def test_score_interval_work_laps():
    template = get_template_by_id("bike_sweet_spot_2x20")
    assert template is not None
    planned = {"library_template_id": template["id"], "duration_min": 70}
    telemetry = {
        "minutes": 68,
        "power": {"np_w": 215, "pct_ftp_np": 88},
        "work_laps": [
            {"index": 1, "avg_power": 210, "role": "work"},
            {"index": 2, "avg_power": 212, "role": "work"},
        ],
    }
    report = score_planned_vs_executed(planned, telemetry, {"ftp_watts": 250})
    assert report["dimensions"]["intervals"] is not None
    assert report["score"] >= 55


def test_grade_from_score_buckets():
    assert grade_from_score(92) == "A"
    assert grade_from_score(81) == "B"
    assert grade_from_score(72) == "C"
    assert grade_from_score(60) == "D"
    assert grade_from_score(40) == "F"


def test_compliance_payload_shape():
    planned = {
        "library_template_id": "run_easy_z2",
        "duration_min": 45,
        "session_type": "easy",
    }
    telemetry = {
        "minutes": 44,
        "heart_rate": {"avg_bpm": 140, "pct_lthr_avg": 82},
    }
    report = score_planned_vs_executed(
        planned,
        telemetry,
        {"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
    )
    assert report["prescribed_vs_executed"]["duration"]["status"] == "scored"
    assert report["grade"] in {"A", "B", "C", "D", "F"}
