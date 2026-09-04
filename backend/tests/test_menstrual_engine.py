"""Tests for menstrual cycle engine."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.menstrual_engine import (  # noqa: E402
    average_cycle_length,
    build_cycle_context,
    detect_cycle_starts,
    map_cycle_phase,
    menstrual_downgrade_steps,
    parse_period_starts_from_coros,
)


class Profile:
    cycle_tracking_enabled = True
    cycle_length_manual = None


def test_parse_coros_period_starts_from_json_list():
    payload = [{"startDate": "2026-08-01"}, {"period_start": "2026-07-04"}]
    starts = parse_period_starts_from_coros(payload)
    assert date(2026, 7, 4) in starts
    assert date(2026, 8, 1) in starts


def test_detect_cycle_starts_gap():
    starts = [date(2026, 1, 1), date(2026, 1, 3), date(2026, 2, 1)]
    cycles = detect_cycle_starts(starts)
    assert cycles == [date(2026, 1, 1), date(2026, 2, 1)]


def test_map_cycle_phase_boundaries():
    assert map_cycle_phase(3, 28) == "menstrual"
    assert map_cycle_phase(10, 28) == "follicular"
    assert map_cycle_phase(15, 28) == "ovulatory"
    assert map_cycle_phase(26, 28) == "late_luteal"


def test_menstrual_downgrade_on_day_3():
    ctx = {
        "enabled": True,
        "available": True,
        "phase": "menstrual",
        "day_in_cycle": 3,
        "days_to_next_period": 25,
    }
    steps, reasons, _warnings = menstrual_downgrade_steps(ctx)
    assert steps >= 1
    assert any("Menstrual" in reason for reason in reasons)


def test_build_cycle_context_day_in_cycle():
    profile = Profile()
    starts = [date(2026, 8, 1), date(2026, 9, 1)]
    ctx = build_cycle_context(profile, starts, on_date=date(2026, 9, 4))
    assert ctx["available"] is True
    assert ctx["day_in_cycle"] == 4
    assert ctx["phase"] == "menstrual"


def test_average_cycle_length():
    starts = [date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)]
    assert average_cycle_length(starts) in (30, 31)
