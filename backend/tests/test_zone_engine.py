"""Phase A + B — anchor model and zone engine tests."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.athlete_profile import apply_physiology_updates  # noqa: E402
from app.services.coach_ai import confirm_baseline  # noqa: E402
from app.services.session_telemetry import resolve_physiology  # noqa: E402
from app.services.workout_library import (  # noqa: E402
    anchors_from_physiology,
    parse_swim_pace_seconds,
    physiology_from_context,
    physiology_from_profile,
    resolve_target_band,
)
from app.services.zone_engine import (  # noqa: E402
    bike_power_zones,
    build_anchors,
    build_zone_tables,
    merge_coros_anchors,
    profile_anchor_fields,
    run_hr_zones,
    run_pace_zones,
    swim_css_zones,
)


def _profile(**kwargs):
    defaults = {
        "id": 1,
        "age": 35,
        "ftp_watts": 250.0,
        "lthr_bpm": 170.0,
        "max_hr_bpm": 190.0,
        "resting_hr_bpm": 50.0,
        "threshold_pace_sec_per_km": 270.0,
        "css_sec_per_100m": 95.0,
        "vo2max": 52.0,
        "zone_run_hr_method": "lthr",
        "zone_bike_power_method": "coggan",
        "zone_run_pace_method": "threshold",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_bike_power_zones_coggan():
    zones = bike_power_zones(250)
    assert len(zones) == 7
    assert zones[3]["name"] == "Z4 threshold"
    assert zones[3]["low_w"] == round(250 * 0.91)
    assert zones[3]["high_w"] == round(250 * 1.05)


def test_run_hr_zones_lthr():
    zones = run_hr_zones(lthr_bpm=170, method="lthr")
    assert len(zones) == 5
    assert zones[0]["relative_to"] == "lthr"
    assert zones[3]["low_bpm"] == round(170 * 0.94)


def test_run_hr_zones_hrr():
    zones = run_hr_zones(max_hr_bpm=190, resting_hr_bpm=50, method="hrr")
    assert len(zones) == 5
    assert zones[0]["relative_to"] == "hrr"
    reserve = 140
    assert zones[4]["high_bpm"] == round(50 + reserve * 1.0)


def test_run_pace_zones_from_threshold():
    zones = run_pace_zones(270)
    assert len(zones) == 6
    threshold = next(z for z in zones if z["name"] == "Threshold")
    assert "/km" in threshold["low_pace"]
    assert threshold["low_sec_per_km"] == pytest.approx(270 * 0.98, rel=0.01)


def test_swim_css_zones():
    zones = swim_css_zones(95)
    assert len(zones) == 4
    assert all("/100m" in z["low_pace"] for z in zones)


def test_profile_anchor_fields_and_coros_merge():
    profile = _profile(threshold_pace_sec_per_km=None, vo2max=None)
    anchors = profile_anchor_fields(profile)
    merged = merge_coros_anchors(anchors, {"threshold_pace": "4:30/km", "vo2max": 48})
    assert merged["threshold_pace_sec_per_km"] == 270
    assert merged["vo2max"] == 48


def test_build_zone_tables_full_stack():
    tables = build_zone_tables(profile_anchor_fields(_profile()))
    assert len(tables["power_zones"]) == 7
    assert len(tables["hr_zones"]) == 5
    assert len(tables["run_pace_zones"]) == 6
    assert len(tables["swim_pace_zones"]) == 4
    assert tables["methods"]["run_hr"] == "lthr"


def test_physiology_from_profile_includes_zones():
    physiology = physiology_from_profile(_profile())
    assert physiology["power_zones"]
    assert physiology["run_pace_zones"]
    assert physiology["anchors"]["threshold_pace_sec_per_km"] == 270


def test_resolve_physiology_merges_profile_anchors():
    profile = _profile()
    physiology = resolve_physiology(profile, [], resting_hr=52)
    assert physiology["threshold_pace_sec_per_km"] == 270
    assert physiology["run_pace_zones"]
    assert physiology["methods"]["run_hr"] == "lthr"


def test_anchors_from_physiology_uses_nested_anchors():
    physiology = physiology_from_profile(_profile())
    anchors = anchors_from_physiology(physiology)
    assert anchors["css_sec_per_100m"] == 95
    assert anchors["lthr_bpm"] == 170


def test_resolve_target_band_with_profile_physiology():
    physiology = physiology_from_profile(_profile())
    anchors = anchors_from_physiology(physiology)
    pace = resolve_target_band({"pace_pct_threshold": {"low": 0.98, "high": 1.02}}, anchors)
    assert "/km" in pace["pace"]


def test_physiology_from_context_coros_fallback():
    context = {
        "profile": {},
        "physiology": {"lthr_bpm": 172},
        "coros": {"fitness": {"threshold_pace": "4:40/km", "vo2max": 50}},
    }
    merged = physiology_from_context(context)
    assert merged["threshold_pace_sec_per_km"] == 280
    assert merged["vo2max"] == 50
    assert merged["run_pace_zones"]


def test_apply_physiology_updates_parses_pace_strings():
    profile = _profile(threshold_pace_sec_per_km=None, css_sec_per_100m=None)
    apply_physiology_updates(
        profile,
        {
            "threshold_pace": "4:30/km",
            "css_pace": "1:35/100m",
            "zone_run_hr_method": "hrr",
        },
    )
    assert profile.threshold_pace_sec_per_km == 270
    assert profile.css_sec_per_100m == parse_swim_pace_seconds("1:35/100m")
    assert profile.zone_run_hr_method == "hrr"


def test_confirm_baseline_copies_coros_fitness():
    profile = _profile(threshold_pace_sec_per_km=None, vo2max=None)
    fitness = SimpleNamespace(
        vo2max=51.0,
        threshold_pace="4:25/km",
        snapshot_at=datetime.utcnow(),
    )
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value.order_by.return_value.first.return_value = fitness
    db.query.return_value = query

    confirm_baseline(db, profile)
    assert profile.vo2max == 51.0
    assert profile.threshold_pace_sec_per_km == 265
    assert profile.baseline_confirmed_at is not None
    db.commit.assert_called_once()


def test_build_anchors_css_estimate_from_threshold():
    anchors = build_anchors({"threshold_pace_sec_per_km": 300})
    assert anchors["css_sec_per_100m"] == pytest.approx(54.0)
