"""Apply-advisory follow-up — patch discussed days, not full week rebuild."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.coach_advisory import (
    build_advisory_workouts_from_thread,
    is_apply_advisory_followup,
    recent_advisory_thread,
    template_apply_advisory_plan,
)
from app.services.coach_intent import GENERAL_CHAT, SCHEDULE_UPDATE, classify_chat_intent
from app.services.coach_skills import SKILL_APPLY_PLAN, resolve_coach_skill
from scripts.ai_eval.coach_golden_bank import WEEKEND_BASE_WEEK_MESSAGE

APPLY_MESSAGE = "so change my plan as per this new updates"
APPLY_MESSAGE_REMAINING_WEEK = (
    "So update my remaining week as per new plan that we just discuused right now."
)

PRIOR_ADVICE = (
    "Friday (today): 60 min endurance at 130–174 W, then upper + core after rest.\n"
    "**Coach's Rule:** Keep the lift at RPE 6–7.\n"
    "Saturday: Long ride + mobility.\n"
    "Sunday: Long easy run.\n"
    "**The Bottom Line:** Finish the base block cleanly before rest week."
)


def _history_with_advice():
    return [
        {"role": "user", "content": WEEKEND_BASE_WEEK_MESSAGE},
        {"role": "assistant", "content": PRIOR_ADVICE},
        {"role": "user", "content": APPLY_MESSAGE},
    ]


def test_apply_followup_detected_with_prior_advice():
    history = _history_with_advice()
    assert is_apply_advisory_followup(APPLY_MESSAGE, history) is True
    assert recent_advisory_thread(history) is not None


def test_apply_followup_remaining_week_phrase():
    history = [
        {"role": "user", "content": WEEKEND_BASE_WEEK_MESSAGE},
        {"role": "assistant", "content": PRIOR_ADVICE},
        {"role": "user", "content": APPLY_MESSAGE_REMAINING_WEEK},
    ]
    assert is_apply_advisory_followup(APPLY_MESSAGE_REMAINING_WEEK, history) is True


def test_apply_followup_without_prior_advice_is_not_apply_mode():
    assert is_apply_advisory_followup(APPLY_MESSAGE, []) is False
    assert (
        classify_chat_intent("change my plan as per this new updates", use_llm=False)
        == SCHEDULE_UPDATE
    )


def test_apply_followup_routes_to_apply_plan_skill():
    resolution = resolve_coach_skill(
        GENERAL_CHAT,
        APPLY_MESSAGE,
        apply_advisory_mode=True,
    )
    assert resolution.skill == SKILL_APPLY_PLAN


def test_apply_followup_does_not_route_to_rebuild_week():
    history = _history_with_advice()
    # Structural classifier alone would pick SCHEDULE_UPDATE — coach_chat overrides with history.
    assert classify_chat_intent(APPLY_MESSAGE, use_llm=False) == SCHEDULE_UPDATE
    assert is_apply_advisory_followup(APPLY_MESSAGE, history) is True


def test_build_advisory_workouts_from_weekend_thread():
    thread = {
        "plan_message": WEEKEND_BASE_WEEK_MESSAGE,
        "advice_reply": PRIOR_ADVICE,
    }
    today = date(2026, 9, 11)  # Friday
    clock = {
        "today": today,
        "week_start": today - timedelta(days=today.weekday()),
    }
    workouts = build_advisory_workouts_from_thread(thread, clock, context={"physiology": {"ftp_watts": 232}})
    titles = [w["title"] for w in workouts]
    assert "Endurance ride (Z2)" in titles
    assert "Upper body + core" in titles
    assert "Long easy ride" in titles
    assert "Long easy run" in titles
    assert not any("Threshold" in t for t in titles)


def test_template_apply_advisory_no_schedule_dump():
    thread = {
        "plan_message": WEEKEND_BASE_WEEK_MESSAGE,
        "advice_reply": PRIOR_ADVICE,
    }
    today = date(2026, 9, 11)
    clock = {"today": today, "week_start": today - timedelta(days=today.weekday())}
    patched = build_advisory_workouts_from_thread(thread, clock)
    reply = template_apply_advisory_plan(
        APPLY_MESSAGE,
        {"load": {"minutes_acwr": 0.95}},
        thread=thread,
        clock=clock,
        patched_workouts=patched,
    )
    text = reply["reply"]
    assert "REVISED WEEK" not in text
    assert "PRIMED" not in text
    assert "TODAY'S CALL" not in text
    assert "WHAT CHANGED" in text
    assert "Threshold" not in text
    assert "bike fit" not in text.lower()
    assert "kolhapur" not in text.lower()
