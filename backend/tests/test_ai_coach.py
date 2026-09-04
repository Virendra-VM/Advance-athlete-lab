"""Sport-routing and autopsy templates for the AI coach."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai_coach import (  # noqa: E402
    athlete_state_block,
    autopsy_task_for_modality,
    autopsy_task_for_packet,
    chat_system_prompt,
    chat_task,
    coach_modality,
    retrieval_query_for_modality,
    schedule_system_prompt,
    schedule_task,
    system_prompt_for_modality,
    template_autopsy,
    template_general_chat,
    today_call_status,
    readiness_score,
)
from app.services.session_telemetry import detect_chat_intent, match_activity_for_message  # noqa: E402


def test_modality_routing():
    assert coach_modality("VirtualRide") == "ride"
    assert coach_modality("Run") == "run"
    assert coach_modality("Swim") == "swim"
    assert coach_modality("WeightTraining") == "strength"
    assert coach_modality("Yoga") == "yoga"
    assert coach_modality("Hike") == "other"


def test_system_prompts_are_sport_specific():
    run = system_prompt_for_modality("run")
    bike = system_prompt_for_modality("ride")
    swim = system_prompt_for_modality("swim")
    lift = system_prompt_for_modality("strength")
    yoga = system_prompt_for_modality("yoga")
    assert "ground reaction" in run.lower()
    assert "eccentric" in run.lower()
    assert "ftp" in bike.lower()
    assert "lactate" in bike.lower()
    assert "swolf" in swim.lower()
    assert "critical swim speed" in swim.lower()
    assert "motor unit" in lift.lower()
    assert "vagal" in yoga.lower()
    assert "parasympathetic" in yoga.lower()
    assert "not a clinician" in run.lower()
    assert "no essays" in run.lower() or "ban essays" in run.lower()
    assert "two consecutive sentences" in run.lower()
    assert "the biology" in run.lower()
    assert "⚡" in run or "BOTTOM LINE" in run
    for prompt in (run, bike, swim, lift, yoga):
        assert "two consecutive sentences" in prompt.lower()
        assert "ban essays" in prompt.lower() or "no essays" in prompt.lower()


def test_autopsy_tasks_keep_acwr_and_checkins():
    for modality in ("run", "ride", "swim", "strength", "yoga"):
        task = autopsy_task_for_modality(modality)
        assert "ACWR" in task or "acwr" in task.lower()
        assert "3 actions" in task
        assert "cohesive story" not in task.lower()


def test_athlete_state_flags_acwr_and_back():
    block = athlete_state_block(
        {
            "readiness_flags": ["sleep_low"],
            "coros": {
                "latest_health": {
                    "sleep_score": 54,
                    "hrv": 32,
                    "hrv_assessment": "unbalanced",
                    "resting_heart_rate": 58,
                }
            },
        },
        {
            "load": {"acute_minutes": 420, "chronic_minutes": 280, "minutes_acwr": 1.5},
            "readiness": {"action": "downgrade_to_easy", "reason": "Sleep is down."},
            "injuries": {"active": ["lower back"], "past": [], "avoid_keywords": ["deadlift"]},
        },
    )
    assert "1.5" in block
    assert "high" in block
    assert "lower back" in block
    assert "true" in block.lower() or "back" in block


def test_template_autopsy_run_is_not_a_bike_file():
    reply = template_autopsy(
        "How was today's run?",
        {
            "load": {"acute_minutes": 300, "chronic_minutes": 280, "minutes_acwr": 1.07},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": []},
        },
        [],
        session_packet={
            "modality": "run",
            "family": "run",
            "sport": "Run",
            "name": "Morning Run",
            "when": "today",
            "minutes": 59,
            "classification": "endurance",
            "cadence": {"avg_rpm": 172},
            "heart_rate": {"avg_bpm": 148, "max_bpm": 171, "pct_max_peak": 90, "decoupling_pct": 4.2},
            "power": {},
        },
        context={"coros": {"latest_health": {"sleep_score": 78, "hrv": 61, "resting_heart_rate": 52}}},
    )
    text = reply["reply"]
    lower = text.lower()
    assert "⚡ THE BOTTOM LINE" in text
    assert "🔬 MECHANICAL PRECISION" in text
    assert "🫀 CARDIOVASCULAR COST" in text
    assert "🧠 COACH'S VERDICT" in text
    assert "THE BIOLOGY" in text
    assert "💡 EXAMPLE" in text
    assert "running" in lower or "impact" in lower
    assert "ftp" not in lower
    assert "acwr" in lower or "acute" in lower
    assert "cohesive story" not in lower


def test_autopsy_task_for_packet_forces_correction_audit():
    task = autopsy_task_for_packet(
        "ride",
        {
            "prescription": {"repeats": 3},
            "prescribed_vs_executed": {
                "aligned": True,
                "vo2_caps": [{"lap": 12}, {"lap": 19}, {"lap": 26}],
            },
            "week_plan_session": {
                "date": "2026-09-01",
                "title": "Cycling quality session",
            },
        },
    )
    lower = task.lower()
    assert "planned-vs-executed" in lower
    assert "vo2" in lower
    assert "lap 7" in lower
    assert "week_plan" in lower or "week-plan" in lower or "tuesday" in lower
    assert "previous assistant" in lower


def test_template_autopsy_uses_prescribed_overlay():
    reply = template_autopsy(
        "analyse the workout",
        {
            "load": {"acute_minutes": 300, "chronic_minutes": 280, "minutes_acwr": 1.02},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": []},
        },
        [],
        session_packet={
            "modality": "ride",
            "family": "ride",
            "sport": "VirtualRide",
            "name": "MyWhoosh – Colombia – Mompox City",
            "when": "yesterday",
            "minutes": 61,
            "classification": "over-under-vo2",
            "power": {"np_w": 203, "pct_ftp_np": 88, "intensity_factor": 0.875, "tss": 78},
            "heart_rate": {"avg_bpm": 147, "max_bpm": 184, "pct_max_peak": 94, "decoupling_pct": 7.4},
            "week_plan_session": {
                "date": "2026-09-01",
                "title": "Cycling quality session",
            },
            "prescribed_vs_executed": {
                "aligned": True,
                "hit_rate": 0.96,
                "blocks": [
                    {
                        "block": 1,
                        "under_w": 202.0,
                        "over_w": 262.0,
                        "vo2_cap": {"lap": 12, "executed_w": 281},
                    }
                ],
                "vo2_caps": [
                    {"lap": 12, "planned_w": 280, "executed_w": 281},
                    {"lap": 19, "planned_w": 280, "executed_w": 283},
                    {"lap": 26, "planned_w": 280, "executed_w": 284},
                ],
                "key_laps": ["Lap 7 (over): planned 260 W → 262 W (+2 W)"],
            },
        },
        context={"coros": {"latest_health": {"sleep_score": 73, "hrv": 48, "resting_heart_rate": 52}}},
    )
    text = reply["reply"]
    assert "VO2 cap" in text or "vo2" in text.lower()
    assert "Lap 12" in text
    assert "Block 1" in text
    assert "hit-rate" in text.lower() or "0.96" in text
    assert "Cycling quality session" in text
    assert "Lap 7 (over)" in text


def test_today_call_bands():
    assert today_call_status(90) == ("green", "🟢 PRIMED / ACCUMULATE")
    assert today_call_status(73) == ("amber", "🟡 CAUTION / ABSORB")
    assert today_call_status(50) == ("red", "🔴 REST / RESTORE")
    assert today_call_status(None)[0] == "amber"
    score, source = readiness_score({"sleep_score": 73}, {})
    assert score == 73 and source == "sleep_score"


def test_chat_and_schedule_prompts_skip_autopsy_sections():
    chat = chat_system_prompt()
    schedule = schedule_system_prompt()
    task = chat_task()
    assert "THE BOTTOM LINE" in chat
    assert "skip" in chat.lower()
    assert "MECHANICAL PRECISION" in chat
    assert "CARDIOVASCULAR COST" in chat
    assert "two consecutive sentences" in chat.lower()
    assert "REFRAME" in chat
    assert "THE BOTTOM LINE" in schedule
    assert "skip" in schedule.lower()
    assert "two consecutive sentences" in schedule.lower()
    assert "last synced" in task.lower() or "telemetry" in task.lower()
    assert "BOTTOM LINE" in task


def test_template_general_chat_is_bullets_not_an_autopsy():
    calm = template_general_chat(
        "What is ACWR?",
        {"readiness": {"reason": "Sleep is adequate."}},
        [],
    )
    text = calm["reply"]
    assert "🧠 THE CALL" in text
    assert "📌 ANSWER" in text
    assert "THE BOTTOM LINE" not in text
    assert "MECHANICAL PRECISION" not in text
    assert "NP" not in text
    emotional = template_general_chat(
        "I failed. I cut the workout short and I feel guilty.",
        {"readiness": {"reason": "Hold easy."}},
        [],
    )
    reframe = emotional["reply"]
    assert "💬 REFRAME" in reframe
    assert "**" in reframe
    assert "THE BOTTOM LINE" not in reframe


def test_schedule_prompt_bypasses_autopsy():
    system = schedule_system_prompt()
    task = schedule_task()
    assert "Olympic Coach" in system or "Athletic Director" in system
    assert "do not autopsy" in system.lower() or "Do NOT autopsy" in system
    assert "TODAY'S CALL" in system
    assert "LOCKER ROOM DIRECTIVE" in system
    assert "Coach's Secret Rule" in system
    assert "PRIMED" in system and "CAUTION" in system and "REST / RESTORE" in system
    assert "THE SCIENCE" in system
    assert "LOCKER ROOM LINGO" in system
    assert "DO NOT" in system
    assert "ACWR" in task
    assert "autopsy" in task.lower()
    assert "Secret Rule" in task
    assert "BOTTOM LINE" in task or "skip" in system.lower()


def test_context_digest_strips_session_file_unless_audit():
    from app.services.coach_ai import _context_digest, resolve_clock

    clock = resolve_clock("UTC")
    context = {
        "profile": {},
        "physiology": {},
        "recent_activities": [
            {
                "name": "Colombia",
                "sport": "VirtualRide",
                "date": "2026-09-01",
                "np": 203,
                "pct_ftp": 88,
                "avg_power": 180,
                "laps": [{"index": 7, "avg_power": 262}],
            }
        ],
        "focal_sessions": [
            {
                "name": "Colombia",
                "date": "2026-09-01",
                "laps": [{"index": 7, "avg_power": 262}],
            }
        ],
        "coros": {},
    }
    chat_digest = _context_digest(context, clock, include_session_audit=False)
    assert '"laps"' not in chat_digest
    assert '"np"' not in chat_digest
    assert "recent_key_sessions" not in chat_digest
    audit_digest = _context_digest(context, clock, include_session_audit=True)
    assert '"laps"' not in audit_digest
    assert '"np"' in audit_digest


def test_retrieval_query_tracks_modality():
    run_q = retrieval_query_for_modality("run", "endurance", "how was the run")
    bike_q = retrieval_query_for_modality("ride", "over-under", "how was the ride")
    assert "ground reaction" in run_q
    assert "ftp" in bike_q or "power" in bike_q


def test_intent_covers_non_bike_sessions():
    assert detect_chat_intent("How was today's swim?") == "WORKOUT_AUDIT"
    assert detect_chat_intent("analyse this lift") == "WORKOUT_AUDIT"
    assert detect_chat_intent("How was yoga?") == "WORKOUT_AUDIT"


def test_match_picks_named_sport_family():
    from types import SimpleNamespace
    import json

    run = SimpleNamespace(
        id=1,
        name="Morning Run",
        sport_type="Run",
        moving_time_s=3600,
        detail_json=json.dumps({"summary": {}, "laps": []}),
    )
    ride = SimpleNamespace(
        id=2,
        name="Lunch Ride",
        sport_type="VirtualRide",
        moving_time_s=3600,
        detail_json=json.dumps({"summary": {"avg_power": 180}, "laps": []}),
    )
    newest_first = [ride, run]
    picked = match_activity_for_message("how was the run", newest_first)
    assert picked.id == 1


def run() -> None:
    tests = [
        test_modality_routing,
        test_system_prompts_are_sport_specific,
        test_autopsy_tasks_keep_acwr_and_checkins,
        test_autopsy_task_for_packet_forces_correction_audit,
        test_athlete_state_flags_acwr_and_back,
        test_template_autopsy_run_is_not_a_bike_file,
        test_template_autopsy_uses_prescribed_overlay,
        test_today_call_bands,
        test_chat_and_schedule_prompts_skip_autopsy_sections,
        test_template_general_chat_is_bullets_not_an_autopsy,
        test_schedule_prompt_bypasses_autopsy,
        test_context_digest_strips_session_file_unless_audit,
        test_retrieval_query_tracks_modality,
        test_intent_covers_non_bike_sessions,
        test_match_picks_named_sport_family,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()
