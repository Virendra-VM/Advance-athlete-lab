"""Pros/Cons hard gate and memory scrub for plan advice replies."""

from __future__ import annotations

from app.services.coach_advisory import (
    finalize_plan_advice_reply,
    scrub_memory_bleed,
    strip_pros_cons_unless_requested,
    template_plan_advice,
)
from scripts.ai_eval.coach_golden_bank import WEEKEND_BASE_WEEK_MESSAGE

NO_PROS_MESSAGE = (
    "Hello coach So tell me now that's it 3 pm i will do endurance ride at 4pm 1 hr ride "
    "and after 30 mins to 60 mins I'll do Upper body + core And tomorrow I'll do Long ride "
    "and mobility in evening and on sunday I'll be doing long easy run no matter what, got it. "
    "so tell me how can i plan it, as my rest week starts from monday so before that i want to "
    "finish the base week perfectly as per my plan so tell me is there any problem in my plan "
    "which i told you right now?"
)

BLOATED_REPLY = (
    "Friday looks fine.\n\n"
    "**Pros**\n- Easy ride fits the week.\n\n"
    "**Cons**\n- Back-to-back long days.\n\n"
    "**The Bottom Line:** Keep it easy."
)

BLEED_REPLY = (
    "Sunday long easy run works on the train-travel day.\n"
    "You'll arrive in Kolhapur fresh after yesterday's bike fit."
)


def test_strip_pros_cons_when_not_requested():
    cleaned = strip_pros_cons_unless_requested(BLOATED_REPLY, NO_PROS_MESSAGE)
    assert "Pros" not in cleaned
    assert "Cons" not in cleaned
    assert "The Bottom Line:" in cleaned


def test_keep_pros_cons_when_requested():
    asked = NO_PROS_MESSAGE + " tell me my plans Pros and cons."
    cleaned = strip_pros_cons_unless_requested(BLOATED_REPLY, asked)
    assert "**Pros**" in cleaned
    assert "**Cons**" in cleaned


def test_template_plan_advice_omits_pros_without_request():
    reply = template_plan_advice(
        NO_PROS_MESSAGE,
        {"load": {"minutes_acwr": 0.86}},
        context={"physiology": {"ftp_watts": 232}, "coros": {"latest_health": {"hrv": 61}}},
    )
    finalized = finalize_plan_advice_reply(reply, NO_PROS_MESSAGE)
    text = finalized["reply"].lower()
    assert "pros:" not in text
    assert "cons:" not in text


def test_scrub_memory_bleed_drops_kolhapur_and_train():
    cleaned = scrub_memory_bleed(BLEED_REPLY, NO_PROS_MESSAGE)
    assert "kolhapur" not in cleaned.lower()
    assert "train" not in cleaned.lower()
    assert "bike fit" not in cleaned.lower()
