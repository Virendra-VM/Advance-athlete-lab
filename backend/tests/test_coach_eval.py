"""Phase 7 — coach conversation eval harness tests."""

from __future__ import annotations

from datetime import date

from app.services.ai_coach import template_schedule
from app.services.coach_plain_language import apply_plain_language_layer
from app.services.coach_reply_eval import (
    DIVERSITY_OVERLAP_FAIL,
    count_triplet_blocks,
    flesch_kincaid_grade,
    has_what_changed_block,
    mentions_zone_changes,
    score_coach_reply,
    score_diversity,
    score_intent_adherence,
    score_plain_language,
    would_read_whole_message,
    CoachEvalExpectation,
)
from app.services.coach_schedule_mode import ACTION_SUMMARY
from scripts.ai_eval.coach_conversation_cases import (
    COACH_CONVERSATION_CASES,
    REPLAN_SAME_SCHEDULE_MESSAGE,
    default_clock,
    default_context,
    default_safety,
    sample_diff,
    sample_proposed_plan,
)
from scripts.ai_eval.coach_reply_generator import generate_deterministic_reply
from scripts.ai_eval.run_coach_eval import run_eval


def _action_summary_reply() -> str:
    proposed = sample_proposed_plan()
    diff = sample_diff()
    safety = default_safety()
    context = default_context()
    clock = default_clock()
    raw = template_schedule(
        REPLAN_SAME_SCHEDULE_MESSAGE,
        safety,
        [],
        proposed_plan=proposed,
        diff=diff,
        physiology_lines=["**FTP:** 232 W", "**LTHR:** 168 bpm"],
        response_mode=ACTION_SUMMARY,
        context=context,
        clock=clock,
    )
    return apply_plain_language_layer(
        raw["reply"],
        context=context,
        safety=safety,
        proposed_plan=proposed,
        clock=clock,
    )


def test_score_diversity_penalizes_identical_runs():
    reply = "Thursday is your only hard hit — intervals at two hundred four watts."
    score, detail = score_diversity([reply] * 5)
    assert score < 0.5
    assert "max_overlap" in detail


def test_score_diversity_rewards_varied_runs():
    runs = [
        "Thursday is your only hard hit with bike intervals at two hundred watts.",
        "Keep Friday easy — conversational pace under one forty bpm all day.",
        "Sunday long run stays aerobic with no surges or finish-line sprints.",
        "Monday rest day — walk or stretch only, no structured intensity.",
        "Wednesday tempo lands at threshold pace for twenty steady minutes.",
    ]
    score, _ = score_diversity(runs, threshold=DIVERSITY_OVERLAP_FAIL)
    assert score >= 0.85


def test_intent_adherence_action_summary_passes_template():
    text = _action_summary_reply()
    expectation = CoachEvalExpectation(
        schedule_mode=ACTION_SUMMARY,
        require_what_changed=True,
        require_zone_mentions=True,
        ban_weekly_translations=True,
        max_triplet_blocks=0,
    )
    score, detail = score_intent_adherence(text, expectation)
    assert score >= 0.99
    assert has_what_changed_block(text)
    assert mentions_zone_changes(text)
    assert count_triplet_blocks(text) == 0
    assert "what_changed=y" in detail


def test_intent_adherence_fails_on_triplet_wall():
    bad = """📊 WHAT CHANGED
• FTP updated

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: polarized model
• 🗣️ LOCKER ROOM LINGO: one hard day
• 💡 REAL-WORLD EXAMPLE: radiator metaphor
"""
    expectation = CoachEvalExpectation(
        schedule_mode=ACTION_SUMMARY,
        require_what_changed=True,
        require_zone_mentions=True,
        max_triplet_blocks=0,
    )
    score, _ = score_intent_adherence(bad, expectation)
    assert score < 0.7


def test_plain_language_fk_grade_and_headers():
    good = (
        "Thursday is your only hard hit — intervals at **204–213 W** under and "
        "**244–267 W** over. Everything else stays easy enough to talk through."
    )
    fk = flesch_kincaid_grade(good)
    assert fk <= 10.0
    score, _ = score_plain_language(good, expectation=CoachEvalExpectation())
    assert score >= 0.8


def test_athlete_panel_would_read_action_summary():
    text = _action_summary_reply()
    assert would_read_whole_message(
        text,
        expectation=CoachEvalExpectation(schedule_mode=ACTION_SUMMARY, max_words=320),
    )


def test_athlete_panel_rejects_triplet_essay():
    wall = "\n".join(
        [
            "🔬 WEEKLY TRANSLATIONS",
            "• 🔬 THE SCIENCE: " + "glycolytic flux " * 20,
            "• 🗣️ LOCKER ROOM LINGO: " + "engine metaphor " * 20,
            "• 💡 REAL-WORLD EXAMPLE: " + "radiator story " * 20,
        ]
    )
    assert would_read_whole_message(wall) is False


def test_score_coach_reply_aggregate():
    text = _action_summary_reply()
    result = score_coach_reply(
        text,
        expectation=CoachEvalExpectation(
            schedule_mode=ACTION_SUMMARY,
            require_what_changed=True,
            require_zone_mentions=True,
            max_triplet_blocks=0,
        ),
        diversity_replies=[text, text],
    )
    assert result["total"] >= 0.75
    assert "intent_adherence" in result["dimensions"]
    assert result["would_read_whole_message"] is True


def test_generate_deterministic_reply_all_cases():
    for case in COACH_CONVERSATION_CASES:
        reply = generate_deterministic_reply(case)
        assert len(reply.strip()) > 40
        scored = score_coach_reply(reply, expectation=case.expectation)
        assert scored["total"] >= 0.7, f"{case.case_id} scored {scored['total']}"


def test_run_coach_eval_harness_end_to_end():
    report = run_eval(dry_run=False)
    assert report["phase"] == 7
    assert report["summary"]["cases"] == len(COACH_CONVERSATION_CASES)
    assert report["summary"]["overall_avg"] >= 0.75
    for case in report["cases"]:
        assert case["score"]["total"] >= 0.7


def test_run_coach_eval_dry_run():
    report = run_eval(dry_run=True)
    assert report["dry_run"] is True
    assert len(report["cases"]) == len(COACH_CONVERSATION_CASES)
