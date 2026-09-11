"""Plan advice routing — conversational answers without schedule rebuild."""

from __future__ import annotations

from app.services.coach_advisory import (
    finalize_advisory_reply,
    go_deeper_prompt_block,
    is_go_deeper_followup,
    is_plan_advice_message,
    polish_advisory_reply,
    strip_schedule_sections,
    template_go_deeper_brief,
    template_plan_advice,
)
from scripts.ai_eval.coach_golden_bank import WEEKEND_BASE_WEEK_MESSAGE
from app.services.coach_intent import GENERAL_CHAT, SCHEDULE_UPDATE, classify_chat_intent


USER_MESSAGE = (
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


def test_plan_advice_message_detected():
    assert is_plan_advice_message(USER_MESSAGE) is True


def test_weekend_base_week_message_detected_as_plan_advice():
    assert is_plan_advice_message(WEEKEND_BASE_WEEK_MESSAGE) is True


def test_template_plan_advice_weekend_no_memory_bleed():
    reply = template_plan_advice(
        WEEKEND_BASE_WEEK_MESSAGE,
        {"load": {"minutes_acwr": 0.95}},
        context={"physiology": {"ftp_watts": 232}, "coros": {"latest_health": {"hrv": 63}}},
    )
    text = reply["reply"].lower()
    assert "bike fit" not in text
    assert "kolhapur" not in text
    assert "on the train" not in text
    assert "pros:" in text
    assert "cons:" in text
    assert "long easy run" in text
    assert "rest week" in text


def test_plan_advice_routes_to_general_chat_not_schedule():
    assert classify_chat_intent(USER_MESSAGE, use_llm=False) == GENERAL_CHAT


def test_go_deeper_followup_detected():
    assert is_go_deeper_followup(GO_DEEPER) is True
    assert classify_chat_intent(GO_DEEPER, use_llm=False) == GENERAL_CHAT


def test_explicit_week_rebuild_still_schedule():
    assert (
        classify_chat_intent("Plan my week around my lower back", use_llm=False)
        == SCHEDULE_UPDATE
    )


def test_template_plan_advice_elite_coach_persona():
    reply = template_plan_advice(
        USER_MESSAGE,
        {"load": {"minutes_acwr": 0.92}},
        context={"physiology": {"ftp_watts": 232}, "coros": {"latest_health": {"hrv": 63}}},
    )
    text = reply["reply"]
    assert "REVISED WEEK" not in text
    assert "TODAY'S CALL" not in text
    assert "PRIMED" not in text
    assert "Mostly yes — with three edits" not in text
    assert "bike fit" in text.lower()
    assert "Coach's Rule:" in text
    assert "The Bottom Line:" in text
    assert "Friday (Tomorrow):" in text
    assert "0.92" in text
    assert "63" in text
    assert "Kolhapur" in text or "train" in text.lower()


def test_polish_advisory_reply_strips_status_lead():
    bloated = (
        "🟢 PRIMED / ACCUMULATE — You're cleared for the planned hard session.\n\n"
        "Mostly yes — with three edits. Missing today for bike fit is fine."
    )
    cleaned = polish_advisory_reply(bloated)
    assert "PRIMED" not in cleaned
    assert "Mostly yes — with three edits" not in cleaned
    assert "bike fit" in cleaned.lower()


def test_strip_schedule_sections():
    bloated = """Skip your DIY stack.

🟢 TODAY'S CALL
**Ready**

🗓️ REVISED WEEK
| Day | Session |
|---|---|
| Fri | Hard |

Keep Friday easy."""
    cleaned = strip_schedule_sections(bloated)
    assert "REVISED WEEK" not in cleaned
    assert "TODAY'S CALL" not in cleaned
    assert "Keep Friday easy" in cleaned


def test_plan_advice_message_rejects_vague_should_i():
    assert is_plan_advice_message("") is False
    assert is_plan_advice_message("should I?") is False
    assert is_plan_advice_message("what do you think about FTP?") is False


def test_template_go_deeper_brief_stays_short_and_grounded():
    reply = template_go_deeper_brief(
        {"load": {"minutes_acwr": 0.92}},
        current_plan={
            "workouts": [
                {
                    "title": "Thursday intervals",
                    "session_type": "intervals",
                    "intensity": "Hard",
                }
            ]
        },
        context={"physiology": {"ftp_watts": 232}},
    )
    text = reply["reply"]
    assert "REVISED WEEK" not in text
    assert "PRIMED" not in text
    assert "0.92" in text
    assert "Thursday intervals" in text or "enough hard work" in text.lower()
    assert reply["intent"] == "GENERAL_CHAT"
    assert reply["citations"] == ["aal-safety-and-load"]


def test_finalize_advisory_reply_and_go_deeper_prompt():
    finalized = finalize_advisory_reply(
        {
            "reply": (
                "🟢 PRIMED / ACCUMULATE — You're cleared for the planned hard session.\n\n"
                "Keep Friday easy around zone 2."
            ),
            "intent": "GENERAL_CHAT",
        }
    )
    assert "PRIMED" not in finalized["reply"]
    assert "Keep Friday easy" in finalized["reply"]

    block = go_deeper_prompt_block()
    assert "GO DEEPER MODE" in block
    assert "No week table" in block
