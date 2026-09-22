"""Step 3: periodization ratios, EWMA load, cycle prescriptions, spine lock, run decoupling."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.autoregulation import resolve_todays_call  # noqa: E402
from app.services.coach_safety import (  # noqa: E402
    MCGILL_BIG3_PRESCRIPTION,
    infer_injury_region,
    spine_forbidden_hit,
    validate_plan,
)
from app.services.menstrual_engine import (  # noqa: E402
    build_cycle_context,
    menstrual_downgrade_steps,
    phase_prescription,
)
from app.services.periodization import distribute_macro_weeks  # noqa: E402
from app.services.session_telemetry import (  # noqa: E402
    aerobic_base_cleared,
    hr_pace_decoupling,
    hr_power_decoupling,
)
from app.services.training_load import ewma_acwr, ewma_lambda  # noqa: E402


class _Profile:
    cycle_tracking_enabled = True
    cycle_length_manual = 28
    basal_body_temp_c = None


def test_ewma_lambdas_match_the_blueprint():
    assert ewma_lambda(7) == 0.25
    assert abs(ewma_lambda(28) - (2.0 / 29.0)) < 1e-12


def test_flat_load_ewma_acwr_is_one_and_a_spike_rises():
    assert ewma_acwr([100.0] * 28) == 1.0
    spiked = ewma_acwr([40.0] * 21 + [160.0] * 7)
    assert spiked is not None
    assert spiked > 1.3


def test_cycle_prescriptions_cover_four_phases_and_keep_late_luteal():
    assert phase_prescription("menstrual")["intensity"] == "easy"
    assert phase_prescription("follicular")["intensity"] == "high"
    assert "VO2" in phase_prescription("follicular")["note"]
    assert phase_prescription("ovulatory")["warmup_extra_min"] == 10
    assert phase_prescription("luteal")["intensity"] == "zone2"
    assert "carbohydrate" in phase_prescription("luteal")["note"]
    assert phase_prescription("late_luteal")["intensity"] == "zone2"


def test_basal_temperature_shifts_the_prescription_without_rewriting_the_phase():
    profile = _Profile()
    profile.basal_body_temp_c = 37.1
    ctx = build_cycle_context(profile, [date(2026, 9, 1)], on_date=date(2026, 9, 10))
    assert ctx["phase"] == "follicular"
    assert ctx["temperature_adjusted"] is True
    assert ctx["prescription"]["intensity"] == "zone2"
    steps, reasons, _warnings = menstrual_downgrade_steps(ctx)
    assert steps >= 1
    assert any("Luteal" in reason for reason in reasons)


def test_luteal_day_downgrades_and_ovulatory_day_does_not():
    profile = _Profile()
    start = date(2026, 9, 1)
    luteal = build_cycle_context(profile, [start], on_date=start + timedelta(days=19))
    assert luteal["phase"] == "luteal"
    assert luteal["prescription"]["intensity"] == "zone2"
    assert menstrual_downgrade_steps(luteal)[0] >= 1

    ovulatory = build_cycle_context(profile, [start], on_date=start + timedelta(days=14))
    assert ovulatory["phase"] == "ovulatory"
    assert menstrual_downgrade_steps(ovulatory)[0] == 0


def test_spine_plan_prescribes_the_mcgill_big_three_inside_fourteen_days():
    today = date.today()
    safety = {
        "max_session_minutes": 90,
        "max_hard_sessions": 2,
        "max_weekly_minutes": 600,
        "max_days_per_week": 6,
        "require_rest_day": False,
        "no_consecutive_hard_days": False,
        "spine_lock": True,
        "injuries": {
            "active": ["lower back"],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        "readiness": {"action": "proceed", "reason": "ok"},
        "load": {"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.0},
    }
    later = today + timedelta(days=20)
    plan = {
        "workouts": [
            {
                "date": today.isoformat(),
                "title": "Overhead day",
                "session_type": "strength",
                "description": "Overhead press and plyometrics",
                "duration_min": 40,
            },
            {
                "date": later.isoformat(),
                "title": "Far hinge",
                "session_type": "strength",
                "description": "5 x 5 deadlift",
                "duration_min": 40,
            },
        ]
    }
    result = validate_plan(plan, safety)
    near = result["plan"]["workouts"][0]
    far = result["plan"]["workouts"][1]
    assert "Modified Curl-Up" in (near.get("description") or "")
    assert "Side Plank" in (near.get("description") or "")
    assert "Bird Dog" in (near.get("description") or "")
    assert MCGILL_BIG3_PRESCRIPTION in (near.get("description") or "")
    assert "deadlift" not in (near.get("description") or "").lower()
    assert "deadlift" in (far.get("description") or "").lower()
    assert spine_forbidden_hit("overhead press") == "overhead press"
    assert infer_injury_region("I tweaked my back and have lumbar stiffness") == "lower back"
    assert infer_injury_region("shooting pain down my leg") == "lower back"


def test_run_decoupling_clears_aerobic_base_under_five_percent():
    elapsed = [float(second) for second in range(3600)]
    speed = [3.0] * 3600
    steady_hr = [140.0] * 1800 + [143.0] * 1800
    drifted_hr = [140.0] * 1800 + [160.0] * 1800
    steady = hr_pace_decoupling(elapsed, steady_hr, speed)
    drifted = hr_pace_decoupling(elapsed, drifted_hr, speed)
    assert steady is not None and steady < 5
    assert drifted is not None and drifted > 5
    assert aerobic_base_cleared(steady, 3600) is True
    assert aerobic_base_cleared(drifted, 3600) is False
    assert aerobic_base_cleared(steady, 50 * 60) is False
    assert aerobic_base_cleared(steady, 100 * 60) is False
    # Power decoupling stays the cycling path.
    power = hr_power_decoupling(elapsed[:1200], [150.0] * 600 + [170.0] * 600, [200.0] * 1200)
    assert power is not None and power > 8


def test_good_sleep_and_low_rpe_soften_an_acwr_spike():
    softened = resolve_todays_call(
        readiness_score=90,
        hrv=55,
        hrv_baseline=50,
        sleep_hours=8,
        acwr=1.7,
        session_rpe=4,
    )
    assert softened["call_level"] == "moderate"
    confirmed = resolve_todays_call(
        readiness_score=90,
        hrv=55,
        hrv_baseline=50,
        sleep_hours=6.2,
        acwr=1.7,
        session_rpe=4,
    )
    assert confirmed["call_level"] == "rest"


def test_macro_weeks_stay_on_the_ratio_for_the_lengths_we_already_trust():
    assert distribute_macro_weeks(52) == {"base": 21, "build": 16, "peak": 10, "taper": 5}
    assert distribute_macro_weeks(8)["taper"] == 1
    assert distribute_macro_weeks(16)["taper"] == 2
    assert distribute_macro_weeks(32)["taper"] == 3
