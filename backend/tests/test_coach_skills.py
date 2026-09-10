"""Phase A — skill-based routing tests."""

from __future__ import annotations

from app.services.coach_intent import (
    DAY_ADJUST,
    GENERAL_CHAT,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
    classify_chat_intent,
)
from app.services.coach_skills import (
    SKILL_ADJUST_DAY,
    SKILL_EXPLAIN_METRIC,
    SKILL_GENERAL_CHAT,
    SKILL_GO_DEEPER,
    SKILL_REBUILD_WEEK,
    SKILL_REVIEW_SESSION,
    SKILL_SUPPORT_CHAT,
    SKILL_VALIDATE_PLAN,
    SKILL_WEEK_DEBRIEF,
    is_personal_metric_question,
    is_support_chat_message,
    resolve_coach_skill,
    skill_prompt_block,
)
from app.services.ai_coach import (
    support_chat_system_prompt,
    template_general_chat,
    template_support_chat,
)

USER_PLAN_ADVICE = (
    "Today was not so good day I missed both of the workouts as i was busy in bike fit "
    "and I finally did the Bike fit so i was thinking tomorrow I'll do the endurance Bike "
    "in afternoon and Strength in morning and on saturday I'll do Long easy ride and on "
    "Sunday I'll do Long easy run as i am traveling by train so it will be confutable and "
    "good for recovery. so tell me should i use this plan now?"
)

GO_DEEPER = (
    "Quick follow-up only: in max 4 bullets, why is one hard day enough this week? "
    "One watch number. No week table or schedule rebuild."
)


def test_intent_to_skill_mapping():
    assert resolve_coach_skill(WORKOUT_AUDIT, "How was today's ride?").skill == SKILL_REVIEW_SESSION
    assert resolve_coach_skill(SCHEDULE_UPDATE, "Plan my week").skill == SKILL_REBUILD_WEEK
    assert resolve_coach_skill(WEEK_REVIEW, "How did I do this week?").skill == SKILL_WEEK_DEBRIEF
    assert resolve_coach_skill(DAY_ADJUST, "Skip today — HRV is low").skill == SKILL_ADJUST_DAY
    assert resolve_coach_skill(SCIENCE_LOOKUP, "What is ACWR?").skill == SKILL_EXPLAIN_METRIC


def test_plan_advice_resolves_to_validate_plan():
    resolution = resolve_coach_skill(
        SCHEDULE_UPDATE,
        USER_PLAN_ADVICE,
        plan_advice_mode=True,
    )
    assert resolution.skill == SKILL_VALIDATE_PLAN
    assert resolution.uses_elite_coach is True
    assert resolution.uses_advisory_polish is True


def test_go_deeper_skill():
    resolution = resolve_coach_skill(
        GENERAL_CHAT,
        GO_DEEPER,
        go_deeper_mode=True,
    )
    assert resolution.skill == SKILL_GO_DEEPER


def test_support_chat_detection():
    assert is_support_chat_message("I missed two sessions — what now?") is True
    assert is_support_chat_message("I feel guilty I cut the workout short") is True
    assert is_support_chat_message("Rough day, missed training because of bike fit") is True
    assert is_support_chat_message(USER_PLAN_ADVICE) is False
    assert is_support_chat_message("What is ACWR?") is False


def test_support_chat_skill_resolution():
    resolution = resolve_coach_skill(
        GENERAL_CHAT,
        "I missed two sessions — what now?",
    )
    assert resolution.skill == SKILL_SUPPORT_CHAT
    assert resolution.uses_elite_coach is True


def test_general_chat_skill_for_neutral_questions():
    resolution = resolve_coach_skill(
        GENERAL_CHAT,
        "How easy should my easy sessions feel?",
    )
    assert resolution.skill == SKILL_GENERAL_CHAT


def test_personal_metric_question_detection():
    assert is_personal_metric_question("Why is my HRV so low this week?") is True
    assert is_personal_metric_question("What is HRV?") is False


def test_personal_metric_routes_to_science_intent():
    assert classify_chat_intent("Why is my HRV so low?", use_llm=False) == SCIENCE_LOOKUP


def test_personal_metric_in_general_chat_gets_explain_skill():
    resolution = resolve_coach_skill(
        GENERAL_CHAT,
        "Why is my HRV so low this week?",
    )
    assert resolution.skill == SKILL_EXPLAIN_METRIC


def test_skill_prompt_blocks_non_empty():
    for skill in (
        SKILL_REVIEW_SESSION,
        SKILL_REBUILD_WEEK,
        SKILL_WEEK_DEBRIEF,
        SKILL_ADJUST_DAY,
        SKILL_EXPLAIN_METRIC,
        SKILL_VALIDATE_PLAN,
        SKILL_GO_DEEPER,
        SKILL_SUPPORT_CHAT,
        SKILL_GENERAL_CHAT,
    ):
        block = skill_prompt_block(skill)
        assert skill.upper().replace("_", " ") in block.upper() or skill in block


def test_template_general_chat_elite_coach_no_headers():
    reply = template_general_chat(
        "What is ACWR?",
        {"load": {"minutes_acwr": 0.92}, "readiness": {"reason": "Cleared."}},
        [],
        context={"coros": {"latest_health": {"hrv": 63}}},
    )
    text = reply["reply"]
    assert "🧠 THE CALL" not in text
    assert "📌 ANSWER" not in text
    assert "PRIMED" not in text
    assert "0.92" in text


def test_template_support_chat_empathy_first():
    reply = template_support_chat(
        "I missed two sessions — what now?",
        {"load": {"minutes_acwr": 1.05}},
        [],
        context={"coros": {"latest_health": {"hrv": 48}}},
    )
    text = reply["reply"]
    assert "Hey" in text
    assert "missed" in text.lower() or "rough" in text.lower()
    assert "THE CALL" not in text
    assert "1.05" in text


def test_support_chat_system_prompt_has_elite_persona():
    prompt = support_chat_system_prompt()
    assert "ELITE COACH PERSONA" in prompt
    assert "SUPPORT CHAT MODE" in prompt
    assert "PRIMED/ACCUMULATE" in prompt


def test_plan_advice_still_routes_general_chat():
    assert classify_chat_intent(USER_PLAN_ADVICE, use_llm=False) == GENERAL_CHAT


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
