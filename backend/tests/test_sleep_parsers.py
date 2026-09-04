"""Tests for COROS sleep text parsing — score, stages, bedtime window."""

from app.services.coros_text_parsers import parse_daily_health_data, parse_sleep_data


SAMPLE_SLEEP = """Sleep Data
========================
Note: each record below is dated by its wake-up day.

2026-09-04
Sleep Score: 97
Main Sleep: 7h 6min
Deep Sleep Ratio: 20%
Light Sleep Ratio: 55%
REM Ratio: 22%
Awake Ratio: 3%
Awake Time: 15 min
Awake Count (>5 min): 0
Main Sleep Window: 2026-09-04 01:00 - 2026-09-04 08:21
Naps Total: 0 min

2026-08-30
Sleep Score: 85
Main Sleep: 8h 1min
Deep Sleep Ratio: 18%
Light Sleep Ratio: 46%
REM Ratio: 32%
Awake Ratio: 4%
Awake Time: 21 min
Awake Count (>5 min): 1
Main Sleep Window: 2026-08-29 23:56 - 2026-08-30 08:18
Naps Total: 47 min
Nap Window: 2026-08-30 15:38 - 2026-08-30 16:25
"""

SAMPLE_DAILY = """Daily Health Data — Last 7 days | Resting HR: 46 bpm | HRV Baseline: 42 ms
Note: sleep entries are dated by their wake-up day.

--- 20260830 ---
Steps: 3,632 | Calories: 548 kcal | Exercise: 0 min
Stress: Avg 27
Sleep Summary:
  Total: 8h 22min | Deep: 1h 32min | Light: 3h 48min | REM: 2h 41min | Awake: 21 min
  Sleep HR: Avg 50 bpm | Min 44 bpm | Max 66 bpm

--- 20260904 ---
Steps: 365 | Calories: 70 kcal | Exercise: 0 min
Stress: Avg 15
Sleep Summary:
  Total: 7h 21min | Deep: 1h 30min | Light: 3h 58min | REM: 1h 38min | Awake: 15 min
  Sleep HR: Avg 49 bpm | Min 45 bpm | Max 65 bpm
"""


def test_sleep_window_parses_iso_datetimes_not_date_fragments():
    rows = {r["metric_date"].isoformat(): r for r in parse_sleep_data(SAMPLE_SLEEP)}
    today = rows["2026-09-04"]
    assert today["bedtime"] == "01:00"
    assert today["wake_time"] == "08:21"
    assert today["sleep_score"] == 97.0
    assert today["sleep_duration_min"] == 426.0
    assert today["nap_duration_min"] == 0.0
    assert today["awake_count"] == 0.0
    assert today["main_sleep_min"] == 426.0

    prior = rows["2026-08-30"]
    assert prior["bedtime"] == "23:56"
    assert prior["wake_time"] == "08:18"
    assert prior["nap_duration_min"] == 47.0
    assert prior["awake_count"] == 1.0


def test_daily_keeps_absolute_stage_minutes():
    rows = {r["metric_date"].isoformat(): r for r in parse_daily_health_data(SAMPLE_DAILY)}
    day = rows["2026-08-30"]
    assert day["deep_sleep_min"] == 92.0  # 1h 32min
    assert day["light_sleep_min"] == 228.0  # 3h 48min
    assert day["rem_sleep_min"] == 161.0  # 2h 41min
    assert day["awake_min"] == 21.0
    # Asleep = deep+light+rem = 481 (= Main Sleep), not time-in-bed 502
    assert day["sleep_duration_min"] == 481.0
    assert abs(day["deep_sleep_pct"] - round(100.0 * 92 / 481, 1)) < 0.01
