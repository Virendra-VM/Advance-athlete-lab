"""Unit tests for deterministic session telemetry — no database required."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.session_telemetry import (  # noqa: E402
    classify_session,
    detect_chat_intent,
    detect_laps_from_power_stream,
    hr_power_decoupling,
    intensity_factor,
    match_activity_for_message,
    normalized_power,
    parse_duration_minutes,
    time_in_zones,
    training_stress_score,
    coggan_power_zones,
    _is_over_under,
    _pct,
)


def _steady(watts: float, seconds: int, start: int = 0) -> tuple[list[float], list[float]]:
    elapsed = [float(start + index) for index in range(seconds)]
    power = [watts] * seconds
    return elapsed, power


def test_normalized_power_equals_steady_watts():
    elapsed, power = _steady(200, 600)
    np_watts = normalized_power(elapsed, power)
    assert np_watts is not None
    assert abs(np_watts - 200) <= 1


def test_normalized_power_higher_than_average_for_spikes():
    elapsed = [float(i) for i in range(600)]
    power = [150.0] * 300 + [300.0] * 300
    np_watts = normalized_power(elapsed, power)
    avg = 225.0
    assert np_watts is not None
    assert np_watts > avg


def test_tss_and_if_at_ftp():
    ftp = 231.0
    elapsed, power = _steady(231, 3600)
    np_watts = normalized_power(elapsed, power)
    iff = intensity_factor(np_watts, ftp)
    tss = training_stress_score(3600, np_watts, ftp)
    assert iff is not None and abs(iff - 1.0) < 0.02
    assert tss is not None and 95 <= tss <= 105


def test_over_under_classification_from_laps():
    ftp = 231.0
    laps = []
    index = 1
    for _block in range(3):
        laps.append({"avg_power": 202, "duration_s": 120, "index": index})
        index += 1
        laps.append({"avg_power": 262, "duration_s": 60, "index": index})
        index += 1
        laps.append({"avg_power": 203, "duration_s": 120, "index": index})
        index += 1
        laps.append({"avg_power": 261, "duration_s": 60, "index": index})
        index += 1
        laps.append({"avg_power": 204, "duration_s": 120, "index": index})
        index += 1
        laps.append({"avg_power": 280, "duration_s": 60, "index": index})
        index += 1
    assert _is_over_under(laps, ftp) is True
    label = classify_session(
        intensity_factor_value=0.92,
        power_zone_time=[],
        laps=laps,
        ftp=ftp,
    )
    assert label == "over-under"


def test_endurance_not_over_under():
    ftp = 231.0
    laps = [{"avg_power": 160, "duration_s": 600, "index": i} for i in range(1, 7)]
    assert _is_over_under(laps, ftp) is False
    label = classify_session(
        intensity_factor_value=0.68,
        power_zone_time=[{"name": "Z2 endurance", "pct": 80}],
        laps=laps,
        ftp=ftp,
    )
    assert label == "endurance"


def test_pct_ftp():
    assert _pct(202, 231, 0) == 87
    assert _pct(264, 231, 0) == 114


def test_hr_decoupling_detects_drift():
    elapsed = [float(i) for i in range(1200)]
    power = [200.0] * 1200
    hr = [150.0] * 600 + [170.0] * 600
    drift = hr_power_decoupling(elapsed, hr, power)
    assert drift is not None
    assert drift > 8


def test_time_in_power_zones_split():
    ftp = 200.0
    zones = coggan_power_zones(ftp)
    elapsed = [float(i) for i in range(200)]
    power = [100.0] * 100 + [200.0] * 100
    rows = time_in_zones(elapsed, power, zones, value_key_low="low_w", value_key_high="high_w")
    by_name = {row["name"]: row["seconds"] for row in rows}
    assert by_name["Z1 recovery"] >= 90
    assert by_name["Z4 threshold"] >= 90


def test_intent_routes_analysis_and_chat():
    assert detect_chat_intent("How was today's session?") == "WORKOUT_AUDIT"
    assert detect_chat_intent("analyse this ride") == "WORKOUT_AUDIT"
    paste = (
        "Tuesday 3x10 over-under. FTP 231W. Unders 201-204W. "
        "Overs 259-264W, surges 284W. Cadence 83-93 rpm. Peak HR 183 bpm."
    )
    assert detect_chat_intent(paste) == "WORKOUT_AUDIT"
    assert detect_chat_intent("How should I adjust this week?") == "SCHEDULE_UPDATE"
    assert detect_chat_intent("I missed two sessions — what now?") == "GENERAL_CHAT"


def test_parse_duration_minutes():
    assert parse_duration_minutes("120 min") == 120
    assert parse_duration_minutes("2 hours") == 120
    assert parse_duration_minutes("3h") == 180
    assert parse_duration_minutes(None) is None


def test_typical_session_is_not_weekly_cap():
    from app.services.coach_safety import compose_safety_profile

    safety = compose_safety_profile(
        days_per_week=6,
        session_minutes=60,
        weekly_minutes_budget=360,
        fitness_level="Advanced",
        injuries={"active": [], "past": [], "avoid_keywords": [], "avoid_session_types": [], "prefer": [], "has_severe_active": False},
        readiness_flags=[],
        load={"acute_minutes": 400, "chronic_minutes": 380, "minutes_acwr": 1.05},
        longest_recent_session="3 hours",
    )
    assert safety["typical_session_minutes"] == 60
    assert safety["max_session_minutes"] >= 180
    assert safety["max_weekly_minutes"] > 360


def _fake_activity(**kwargs):
    import json
    from types import SimpleNamespace

    laps = kwargs.pop("laps", [])
    summary = kwargs.pop("summary", {"avg_power": 180})
    return SimpleNamespace(
        id=kwargs.get("id"),
        name=kwargs.get("name"),
        sport_type=kwargs.get("sport_type", "VirtualRide"),
        moving_time_s=kwargs.get("moving_time_s", 3600),
        detail_json=json.dumps({"summary": summary, "laps": laps}),
    )


def test_match_prefers_newest_ride_not_longest():
    colombia = _fake_activity(
        id=3510,
        name="MyWhoosh - Colombia - Mompox City",
        moving_time_s=3668,
        laps=[{"index": i, "duration_s": 60, "avg_power": 260} for i in range(1, 14)],
    )
    hudayriyat = _fake_activity(
        id=3509,
        name="MyWhoosh - Hudayriyat Ascend",
        moving_time_s=3840,
        laps=[{"index": 1, "duration_s": 3814, "avg_power": 155}],
    )
    newest_first = [colombia, hudayriyat]
    picked = match_activity_for_message("How was today's session?", newest_first, today_ids=set())
    assert picked.id == 3510
    named = match_activity_for_message("analyse the Colombia ride", newest_first)
    assert named.id == 3510
    pinned = match_activity_for_message("how was this workout", newest_first, activity_id=3509)
    assert pinned.id == 3509


def test_detect_laps_from_repeating_over_unders():
    ftp = 220.0
    elapsed = []
    power = []
    t = 0
    # warmup
    for _ in range(600):
        elapsed.append(float(t))
        power.append(130.0)
        t += 1
    for _block in range(4):
        for _ in range(60):
            elapsed.append(float(t))
            power.append(262.0)
            t += 1
        for _ in range(120):
            elapsed.append(float(t))
            power.append(203.0)
            t += 1
    laps = detect_laps_from_power_stream(elapsed, power, ftp=ftp)
    assert len(laps) >= 8
    overs = [lap for lap in laps if (lap.get("avg_power") or 0) >= 240]
    unders = [lap for lap in laps if 180 <= (lap.get("avg_power") or 0) <= 220]
    assert len(overs) >= 3
    assert len(unders) >= 3


def test_steady_endurance_does_not_invent_interval_laps():
    elapsed = [float(i) for i in range(3600)]
    power = [155.0] * 3600
    laps = detect_laps_from_power_stream(elapsed, power, ftp=220.0)
    assert laps == []


def run() -> None:
    tests = [
        test_normalized_power_equals_steady_watts,
        test_normalized_power_higher_than_average_for_spikes,
        test_tss_and_if_at_ftp,
        test_over_under_classification_from_laps,
        test_endurance_not_over_under,
        test_pct_ftp,
        test_hr_decoupling_detects_drift,
        test_time_in_power_zones_split,
        test_intent_routes_analysis_and_chat,
        test_parse_duration_minutes,
        test_typical_session_is_not_weekly_cap,
        test_match_prefers_newest_ride_not_longest,
        test_detect_laps_from_repeating_over_unders,
        test_steady_endurance_does_not_invent_interval_laps,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()
