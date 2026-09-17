"""Phase 3 — quick debrief vs full autopsy routing and templates."""

from __future__ import annotations

from app.services.ai_coach import (
    quick_debrief_task_for_packet,
    system_prompt_quick_debrief,
    template_autopsy,
    template_quick_debrief,
)
from app.services.debrief_mode import (
    DEBRIEF_FULL,
    DEBRIEF_QUICK,
    is_quick_debrief_compliant,
    quick_debrief_word_count,
    resolve_debrief_mode,
)
_PRESCRIPTION_PASTE = """
You got it wrong coach, I had planned that workout and it was
1) 10 mins warmup
2) 3 mins at 175 w
3) 2 mins Rest at 125 w
main set under and over
1) 2 mins at 200 w
2) 1 min at 260 w
repeat this set 3 times with no rest
and cool down of 10 mins
lap 12, 19, 26 are the VO2 max to finish the set
"""


def test_resolve_quick_for_how_was_session():
    assert resolve_debrief_mode("How was today's session?") == DEBRIEF_QUICK
    assert resolve_debrief_mode("How did I do today?") == DEBRIEF_QUICK
    assert (
        resolve_debrief_mode("How was Sunday's run — give me a quick debrief.")
        == DEBRIEF_QUICK
    )


def test_resolve_full_for_deep_dive_and_laps():
    assert resolve_debrief_mode("Deep dive into Saturday's ride") == DEBRIEF_FULL
    assert resolve_debrief_mode("Analyze laps from this workout") == DEBRIEF_FULL
    assert resolve_debrief_mode("Full breakdown of the main set") == DEBRIEF_FULL
    assert resolve_debrief_mode("Telemetry audit please") == DEBRIEF_FULL


def test_resolve_full_for_pasted_prescription():
    assert resolve_debrief_mode(_PRESCRIPTION_PASTE) == DEBRIEF_FULL


def test_resolve_full_for_interval_audit_packet():
    packet = {
        "prescribed_vs_executed": {
            "aligned": True,
            "hit_rate": 0.88,
            "key_laps": ["Lap 7 (over): planned 260 W → 262 W ✓"],
        }
    }
    assert resolve_debrief_mode("How was the ride?", session_packet=packet) == DEBRIEF_FULL


def test_quick_debrief_template_sunday_run():
    reply = template_quick_debrief(
        "Quick debrief Sunday run",
        {
            "load": {"minutes_acwr": 1.21},
            "injuries": {"active": []},
        },
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
            "power": {"source": "absent", "coaching_note": "Runs use pace and HR — no watt load."},
            "heart_rate": {"avg_bpm": 145, "pct_lthr_avg": 83},
            "run_intensity": {"pace_label": "easy", "hr_label": "steady"},
            "week_plan_session": {
                "title": "Easy long run",
                "duration_min": 60,
                "session_type": "easy",
                "intensity": "conversational",
            },
            "execution_headline": {
                "headline": (
                    "88 min / 13.0 km at 6.77 min/km — longer than your 60 min Easy long run — "
                    "not easy vs plan — HR 145 avg (83% LTHR)"
                ),
                "intensity_mismatch": True,
            },
        },
        context={"coros": {"latest_health": {"sleep_score": 72, "hrv": 48, "resting_heart_rate": 52}}},
    )
    text = reply["reply"]
    assert reply["debrief_mode"] == "quick"
    assert "⚡ BOTTOM LINE" in text
    assert "📋 VS PLAN" in text
    assert "🧠 RECOVERY" in text
    assert "🔬 MECHANICAL PRECISION" not in text
    assert "METRIC:" not in text
    assert "THE BIOLOGY:" not in text
    assert "💡 EXAMPLE:" not in text
    assert "88 min / 13" in text
    assert "ACWR" in text
    assert is_quick_debrief_compliant(text)
    words = quick_debrief_word_count(text)
    assert 55 <= words <= 160, words


def test_quick_debrief_estimated_ride_no_watt_story():
    reply = template_quick_debrief(
        "How was Saturday's ride?",
        {"load": {"minutes_acwr": 1.21}, "injuries": {"active": []}},
        [],
        session_packet={
            "name": "Morning Ride",
            "when": "Saturday",
            "minutes": 277,
            "km": 60.05,
            "family": "ride",
            "modality": "ride",
            "classification": "long",
            "power": {
                "source": "estimated",
                "coaching_note": "No power meter — Strava estimated watts are reference only.",
            },
            "heart_rate": {"avg_bpm": 138, "pct_lthr_avg": 82},
            "week_plan_session": {"title": "Easy ride", "duration_min": 90},
            "execution_headline": {
                "headline": "277 min / 60.05 km — longer than your 90 min Easy ride",
                "duration_longer": True,
            },
        },
        context={"coros": {"latest_health": {"hrv": 48}}},
    )
    text = reply["reply"]
    assert "reference only" in text.lower() or "No power meter" in text
    assert "Normalized power" not in text
    assert is_quick_debrief_compliant(text)


def test_full_autopsy_still_has_four_sections():
    reply = template_autopsy(
        "Deep dive into the ride",
        {"load": {"minutes_acwr": 1.0}, "injuries": {"active": []}},
        [],
        session_packet={
            "name": "Trainer Ride",
            "when": "Tuesday",
            "minutes": 61,
            "km": 30,
            "family": "ride",
            "modality": "ride",
            "classification": "endurance",
            "power": {"source": "measured", "np_w": 180, "intensity_factor": 0.78, "tss": 45, "pct_ftp_np": 78},
            "heart_rate": {"avg_bpm": 146, "max_bpm": 171},
            "laps": [],
            "work_laps": [],
        },
    )
    text = reply["reply"]
    assert reply["debrief_mode"] == "full"
    assert "🔬 MECHANICAL PRECISION" in text
    assert "🫀 CARDIOVASCULAR COST" in text


def test_quick_debrief_llm_prompts():
    task = quick_debrief_task_for_packet(
        "run",
        {"execution_headline": {"headline": "not easy vs plan"}},
    )
    assert "NOT a full autopsy" in task
    prompt = system_prompt_quick_debrief("run")
    assert "80-120 words" in prompt
    assert "METRIC/Biology/Example triplets" in prompt or "Metric/Biology/Example" in prompt
