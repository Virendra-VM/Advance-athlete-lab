"""Week plan review/commit chat modes."""

from app.services.ai_coach import template_week_plan_review, week_plan_review_task
from app.services.coach_intent import WEEK_PLAN_REVIEW, normalize_intent


def test_week_plan_review_intent_registered():
    assert normalize_intent(WEEK_PLAN_REVIEW) == WEEK_PLAN_REVIEW


def test_template_week_plan_review_has_no_week_plan():
    reply = template_week_plan_review(
        "Train Tue Thu Sat only",
        {"load": {"minutes_acwr": 1.1}, "injuries": {"active": []}},
        [],
        context={"season": {"current_phase": {"phase_type": "base"}, "week_intent": {}}},
        clock={"today": None, "week_start": None},
    )
    assert reply["intent"] == WEEK_PLAN_REVIEW
    assert "week_plan" not in reply
    assert "Plan my week" in reply["reply"]


def test_week_plan_review_task_forbids_table():
    task = week_plan_review_task()
    assert "No full week table" in task or "No week table" in task
    assert "week_plan" in task
