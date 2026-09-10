"""Phase 4 — plain-language layer tests."""

from __future__ import annotations

from datetime import date

from app.services.ai_coach import template_schedule
from app.services.coach_plain_language import (
    apply_plain_language_layer,
    build_plain_lead,
    build_plain_why_sentence,
    collapse_formal_labels,
    ensure_plain_lead,
    has_plain_lead,
    pick_watch_number,
    plain_language_prompt_block,
    strip_journal_filler,
    word_count_excluding_table,
)
from app.services.coach_schedule_mode import (
    ACTION_SUMMARY,
    finalize_schedule_narrator_reply,
)


def _safety(acwr=1.13):
    return {
        "load": {"minutes_acwr": acwr},
        "readiness": {"action": "proceed", "reason": "Cleared."},
        "injuries": {"active": [], "has_severe_active": False},
        "max_session_minutes": 180,
        "max_hard_sessions": 2,
        "max_days_per_week": 5,
        "max_weekly_minutes": 400,
        "weekly_minutes_budget": 400,
        "typical_session_minutes": 45,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
    }


def _context(sleep=82, ftp=232, lthr=168):
    return {
        "coros": {"latest_health": {"sleep_score": sleep, "hrv": 60}},
        "physiology": {"ftp_watts": ftp, "lthr_bpm": lthr},
    }


def test_word_count_excluding_table():
    text = """Short intro here.

| Day | Session |
|---|---|
| Mon | Easy |
"""
    assert word_count_excluding_table(text) == 3


def test_pick_watch_number_from_quality_session():
    proposed = {
        "workouts": [
            {
                "date": "2026-09-04",
                "title": "Bike O/U 3×12",
                "session_type": "threshold",
                "intensity": "under 204–213 W · over 244–267 W",
            }
        ]
    }
    watch = pick_watch_number(
        _context(),
        _safety(),
        proposed_plan=proposed,
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    assert watch is not None
    assert "204" in watch or "Bike O/U" in watch


def test_build_plain_lead_has_decision_watch_and_why():
    proposed = {
        "workouts": [
            {
                "date": "2026-09-04",
                "title": "Bike O/U",
                "session_type": "threshold",
                "intensity": "under 204–213 W",
            }
        ]
    }
    lead = build_plain_lead(
        _context(),
        _safety(),
        proposed_plan=proposed,
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    assert "CAUTION" in lead or "PRIMED" in lead or "REST" in lead
    assert "204" in lead or "232" in lead or "1.13" in lead
    assert len(lead.split(".")) >= 2


def test_build_plain_why_sentence_acwr_elevated():
    why = build_plain_why_sentence(_safety(acwr=1.32), _context(), band="amber")
    assert "1.32" in why


def test_strip_journal_filler():
    text = "The glycolytic flux was high during parasympathetic tone recovery."
    cleaned = strip_journal_filler(text)
    assert "glycolytic" not in cleaned.lower()


def test_collapse_formal_labels():
    text = """Good line
• 🔬 THE SCIENCE: ACWR
• 🗣️ LOCKER ROOM LINGO: easy week
Still good"""
    cleaned = collapse_formal_labels(text)
    assert "THE SCIENCE" not in cleaned
    assert "Still good" in cleaned


def test_ensure_plain_lead_prepends_when_missing():
    text = "🟢 TODAY'S CALL\n**Ready**"
    out = ensure_plain_lead(
        text,
        context=_context(),
        safety=_safety(),
        proposed_plan={"workouts": []},
        clock={"today": date(2026, 9, 3)},
    )
    assert has_plain_lead(out)
    assert "TODAY'S CALL" in out


def test_apply_plain_language_layer_short_reply():
    raw = """🟢 TODAY'S CALL
**🟡 CAUTION / ABSORB**

🗣️ LOCKER ROOM DIRECTIVE
Hold the calendar."""
    out = apply_plain_language_layer(
        raw,
        context=_context(),
        safety=_safety(),
        proposed_plan={
            "workouts": [
                {
                    "date": "2026-09-04",
                    "title": "Bike O/U",
                    "session_type": "threshold",
                    "intensity": "under 204–213 W",
                }
            ]
        },
        clock={"today": date(2026, 9, 3)},
    )
    assert has_plain_lead(out)
    assert "THE SCIENCE" not in out


def test_plain_language_prompt_block_phase4():
    block = plain_language_prompt_block()
    assert "Phase 4" in block
    assert "smart training partner" in block


def test_finalize_narrator_includes_plain_lead():
    proposed = {
        "title": "Week",
        "week_start": "2026-09-01",
        "workouts": [
            {
                "date": "2026-09-04",
                "title": "Bike O/U",
                "session_type": "threshold",
                "intensity": "under 204–213 W",
            }
        ],
    }
    out = finalize_schedule_narrator_reply(
        {"reply": "🟢 TODAY'S CALL\n**🟡 CAUTION / ABSORB**"},
        proposed_plan=proposed,
        schedule_mode=ACTION_SUMMARY,
        schedule_diff={"changes": []},
        physiology_lines=["**FTP:** 232 W"],
        message="Plan my week again keep schedule same with new FTP",
        safety=_safety(),
        context=_context(),
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    assert has_plain_lead(out["reply"])
    assert "WHAT CHANGED" in out["reply"]


def test_template_schedule_action_summary_opens_with_plain_lead():
    context = {
        "profile": {
            "primary_goal": "Half marathon",
            "sports": [{"sport": "Cycling", "priority": "primary"}],
            "days_per_week": 4,
        },
        "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
        "coros": {"latest_health": {"sleep_score": 82, "hrv": 63}},
        "season": {"current_phase": {"phase_type": "build"}},
    }
    proposed = {
        "title": "Week",
        "week_start": "2026-08-31",
        "workouts": [
            {
                "date": "2026-09-04",
                "title": "Bike O/U 3×12",
                "sport": "Cycling",
                "session_type": "threshold",
                "intensity": "under 204–213 W · over 244–267 W",
            }
        ],
    }
    reply = template_schedule(
        "Plan my this week again keep the schedule same with new FTP",
        _safety(),
        [],
        response_mode=ACTION_SUMMARY,
        proposed_plan=proposed,
        diff={"changes": [], "unchanged_days": 1, "same_shape": True},
        physiology_lines=["**FTP:** 232 W"],
        context=context,
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    text = reply["reply"]
    first_block = text.split("\n\n")[0]
    assert "CAUTION" in first_block or "PRIMED" in first_block or "REST" in first_block
    assert "THE SCIENCE" not in text
    assert "204" in text or "232" in text


def run() -> None:
    tests = [
        test_word_count_excluding_table,
        test_pick_watch_number_from_quality_session,
        test_build_plain_lead_has_decision_watch_and_why,
        test_build_plain_why_sentence_acwr_elevated,
        test_strip_journal_filler,
        test_collapse_formal_labels,
        test_ensure_plain_lead_prepends_when_missing,
        test_apply_plain_language_layer_short_reply,
        test_plain_language_prompt_block_phase4,
        test_finalize_narrator_includes_plain_lead,
        test_template_schedule_action_summary_opens_with_plain_lead,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()
