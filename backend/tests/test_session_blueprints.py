"""Named warmup / main / cooldown detail for planned sessions."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.session_blueprints import (  # noqa: E402
    downgrade_today_workout,
    enrich_workout,
)


def test_strength_names_lifts_and_bookends():
    workout = enrich_workout(
        {
            "sport": "Strength training",
            "title": "Full-body strength",
            "session_type": "strength",
            "duration_min": 45,
            "structure": [],
        }
    )
    segments = {item["segment"] for item in workout["structure"]}
    assert segments == {"Warm-up", "Main set", "Cool-down"}
    main = next(item for item in workout["structure"] if item["segment"] == "Main set")
    assert "Goblet squat" in main["detail"]
    cool = next(item for item in workout["structure"] if item["segment"] == "Cool-down")
    assert "Foam roll" in cool["detail"] or "foam roll" in cool["detail"].lower()


def test_spine_lock_strength_avoids_hinge():
    workout = enrich_workout(
        {
            "sport": "Strength training",
            "session_type": "strength",
            "duration_min": 40,
            "structure": [],
        },
        {"spine_lock": True},
    )
    main = next(item for item in workout["structure"] if item["segment"] == "Main set")
    assert "dead bug" in main["detail"].lower()
    assert "DO NOT" in main["detail"]
    assert "back squat" in main["detail"].lower()


def test_run_and_ride_quality_name_the_set():
    run = enrich_workout(
        {
            "sport": "Running",
            "session_type": "threshold",
            "duration_min": 50,
            "structure": [],
        }
    )
    ride = enrich_workout(
        {
            "sport": "Cycling",
            "session_type": "intervals",
            "duration_min": 60,
            "structure": [],
        }
    )
    run_main = next(item for item in run["structure"] if item["segment"] == "Main set")
    ride_main = next(item for item in ride["structure"] if item["segment"] == "Main set")
    assert "10 min" in run_main["detail"] or "threshold" in run_main["detail"].lower()
    assert "6 min" in ride_main["detail"] or "power" in ride_main["detail"].lower()


def test_yoga_and_swim_are_not_empty_labels():
    yoga = enrich_workout(
        {"sport": "Yoga / mobility", "session_type": "mobility", "duration_min": 30, "structure": []}
    )
    swim = enrich_workout(
        {"sport": "Swimming", "session_type": "easy", "duration_min": 40, "structure": []}
    )
    yoga_main = next(item for item in yoga["structure"] if item["segment"] == "Main set")
    swim_warm = next(item for item in swim["structure"] if item["segment"] == "Warm-up")
    assert "warrior" in yoga_main["detail"].lower() or "lunge" in yoga_main["detail"].lower()
    assert "drill" in swim_warm["detail"].lower() or "stroke" in swim_warm["detail"].lower()


def test_downgrade_converts_intervals_to_easy_same_duration():
    adjusted = downgrade_today_workout(
        {
            "date": "2026-09-09",
            "sport": "Cycling",
            "title": "Threshold",
            "session_type": "threshold",
            "duration_min": 61,
            "intensity": "Hard",
            "structure": [],
        },
        {"readiness": {"action": "downgrade_to_easy"}, "todays_call": {"call_level": "easy"}},
    )
    assert adjusted["session_type"] == "easy"
    assert adjusted["duration_min"] == 61
    assert any(item["segment"] == "Warm-up" for item in adjusted["structure"])
