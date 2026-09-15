"""Autopsy template respects estimated/absent power source."""

from __future__ import annotations

from app.services.ai_coach import autopsy_task_for_packet, template_autopsy


def test_autopsy_task_includes_power_source_rules():
    task = autopsy_task_for_packet(
        "ride",
        {
            "power": {
                "source": "estimated",
                "coaching_note": "No power meter — use HR only.",
            }
        },
    )
    assert "POWER SOURCE RULES" in task
    assert "estimated" in task
    assert "IF, TSS" in task


def test_template_autopsy_estimated_ride_no_np_triplet():
    reply = template_autopsy(
        "How was Saturday's ride?",
        {"load": {"minutes_acwr": 1.0}},
        [],
        session_packet={
            "name": "Morning Ride",
            "when": "Saturday",
            "minutes": 277,
            "km": 60.05,
            "family": "ride",
            "sport": "Ride",
            "classification": "endurance",
            "power": {
                "source": "estimated",
                "coaching_note": "No power meter — Strava estimated watts are for reference only.",
                "reference_avg_w": 112,
                "np_w": None,
                "intensity_factor": None,
                "tss": None,
            },
            "heart_rate": {"avg_bpm": 138, "max_bpm": 173, "pct_lthr_avg": 82},
            "cadence": {"avg_rpm": 85},
            "laps": [],
            "work_laps": [],
        },
    )
    text = reply["reply"]
    assert "No power meter" in text
    assert "reference only" in text.lower()
    assert "Normalized power" not in text
    assert "· IF " not in text
    assert "sweet-spot" not in text.lower()
