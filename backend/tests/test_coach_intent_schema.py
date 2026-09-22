"""Blueprint CoachIntent contract and the legacy runtime map."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai_schemas import CoachIntent
from app.services.coach_intent import (
    ARCHITECTURE_INTENTS,
    ARCHITECTURE_TO_RUNTIME,
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    MONTH_REVIEW,
    OFF_TOPIC,
    SCHEDULE_MUTATION,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEKLY_EXECUTIVE_SUMMARY,
    WEEK_PLAN_REVIEW,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
    WORKOUT_SINGLE_AUTOPSY,
    YEAR_REVIEW,
    architecture_intent_for,
    classify_chat_intent,
    decision_to_coach_intent,
    normalize_intent,
    runtime_intent_for,
)
from app.services.coach_intent import IntentDecision


@pytest.mark.parametrize("category", ARCHITECTURE_INTENTS)
def test_each_architecture_lens_validates(category):
    intent = CoachIntent(
        intent_category=category,
        confidence_score=0.91,
        requires_database_patch=False,
        target_date=None,
    )
    assert intent.intent_category == category
    assert intent.requires_database_patch is False
    assert intent.target_date is None


def test_confidence_bounds():
    CoachIntent(
        intent_category=SCIENCE_LOOKUP,
        confidence_score=0.0,
        requires_database_patch=False,
    )
    CoachIntent(
        intent_category=SCIENCE_LOOKUP,
        confidence_score=1.0,
        requires_database_patch=False,
    )
    with pytest.raises(ValidationError):
        CoachIntent(
            intent_category=SCIENCE_LOOKUP,
            confidence_score=-0.01,
            requires_database_patch=False,
        )
    with pytest.raises(ValidationError):
        CoachIntent(
            intent_category=SCIENCE_LOOKUP,
            confidence_score=1.01,
            requires_database_patch=False,
        )


def test_unknown_lens_and_missing_patch_flag_fail():
    with pytest.raises(ValidationError):
        CoachIntent(
            intent_category="GENERAL_CHAT",
            confidence_score=0.8,
            requires_database_patch=False,
        )
    with pytest.raises(ValidationError):
        CoachIntent(intent_category=CLINICAL_VETO, confidence_score=0.9)


@pytest.mark.parametrize(
    "raw",
    ["22-09-2026", "2026/09/22", "2026-13-01", "2026-02-31", "tomorrow", "20260922"],
)
def test_target_date_rejects_non_iso_and_impossible_dates(raw):
    with pytest.raises(ValidationError):
        CoachIntent(
            intent_category=SCHEDULE_MUTATION,
            confidence_score=0.8,
            requires_database_patch=True,
            target_date=raw,
        )


def test_target_date_accepts_real_iso_day_and_blank():
    intent = CoachIntent(
        intent_category=SCHEDULE_MUTATION,
        confidence_score=0.88,
        requires_database_patch=True,
        target_date="2026-09-22",
    )
    assert intent.target_date == "2026-09-22"
    blank = CoachIntent(
        intent_category=SCHEDULE_MUTATION,
        confidence_score=0.88,
        requires_database_patch=False,
        target_date="  ",
    )
    assert blank.target_date is None


def test_architecture_names_normalize_back_to_runtime_labels():
    assert normalize_intent(WORKOUT_SINGLE_AUTOPSY) == WORKOUT_AUDIT
    assert normalize_intent(WEEKLY_EXECUTIVE_SUMMARY) == WEEK_REVIEW
    assert normalize_intent(SCHEDULE_MUTATION) == SCHEDULE_UPDATE
    assert normalize_intent(SCIENCE_LOOKUP) == SCIENCE_LOOKUP
    assert normalize_intent(CLINICAL_VETO) == CLINICAL_VETO
    assert normalize_intent("session_analysis") == WORKOUT_AUDIT
    assert normalize_intent("not-a-real-intent") == GENERAL_CHAT


def test_runtime_labels_round_trip_through_the_canonical_lens():
    for lens, runtime in ARCHITECTURE_TO_RUNTIME.items():
        assert architecture_intent_for(runtime) == lens
        assert runtime_intent_for(lens) == runtime
        assert normalize_intent(lens) == runtime


def test_macro_and_day_labels_share_a_lens_without_changing_the_reverse_map():
    assert architecture_intent_for(MONTH_REVIEW) == WEEKLY_EXECUTIVE_SUMMARY
    assert architecture_intent_for(YEAR_REVIEW) == WEEKLY_EXECUTIVE_SUMMARY
    assert architecture_intent_for(DAY_ADJUST) == SCHEDULE_MUTATION
    assert architecture_intent_for(WEEK_PLAN_REVIEW) == SCHEDULE_MUTATION
    assert runtime_intent_for(WEEKLY_EXECUTIVE_SUMMARY) == WEEK_REVIEW
    assert runtime_intent_for(SCHEDULE_MUTATION) == SCHEDULE_UPDATE


def test_chat_and_off_topic_have_no_architecture_lens():
    assert architecture_intent_for(GENERAL_CHAT) is None
    assert architecture_intent_for(OFF_TOPIC) is None
    assert architecture_intent_for("") is None
    assert architecture_intent_for(None) is None
    with pytest.raises(ValueError):
        runtime_intent_for(GENERAL_CHAT)


def test_decision_to_coach_intent_validates_patch_and_date():
    decision = IntentDecision(DAY_ADJUST, 0.96, "structural")
    intent = decision_to_coach_intent(
        decision,
        requires_database_patch=True,
        target_date="2026-09-22",
    )
    assert intent is not None
    assert intent.intent_category == SCHEDULE_MUTATION
    assert intent.confidence_score == 0.96
    assert intent.requires_database_patch is True
    assert intent.target_date == "2026-09-22"

    chat = decision_to_coach_intent(IntentDecision(GENERAL_CHAT, 0.85, "structural_default"))
    assert chat is None

    with pytest.raises(ValidationError):
        decision_to_coach_intent(
            IntentDecision(SCHEDULE_UPDATE, 0.7, "structural"),
            requires_database_patch=True,
            target_date="Sunday",
        )


def test_live_router_still_returns_runtime_labels():
    assert classify_chat_intent("How was today's session?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("What is ACWR?", use_llm=False) == SCIENCE_LOOKUP
    assert (
        classify_chat_intent("I have sharp pain in my tendon when running", use_llm=False)
        == CLINICAL_VETO
    )
