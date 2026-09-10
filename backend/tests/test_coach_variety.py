"""Phase 5 — variety engine tests."""

from __future__ import annotations

from app.services.coach_variety import (
    DEGENERATE_OVERLAP_THRESHOLD,
    analyze_reply_variety,
    build_variety_retry_block,
    extract_analogies_used,
    extract_section_signature,
    is_degenerate_reply,
    max_overlap_with_recent,
    normalize_for_overlap,
    trigram_overlap,
    variety_prompt_block,
)


def test_trigram_overlap_identical():
    text = "Thursday is your only hard hit with intervals at two hundred watts."
    assert trigram_overlap(text, text) == 1.0


def test_trigram_overlap_different():
    a = "Thursday is your only hard hit with bike intervals."
    b = "Easy aerobic run today keep heart rate conversational and light."
    assert trigram_overlap(a, b) < 0.25


def test_is_degenerate_reply_detects_copy():
    prior = "Hold the calendar today. ACWR is elevated so protect easy days this week."
    history = [{"role": "assistant", "content": prior}]
    duplicate = prior + " Same plan."
    assert is_degenerate_reply(duplicate, history) is True


def test_is_degenerate_reply_allows_fresh_reply():
    history = [{"role": "assistant", "content": "Old week table and directive about easy days."}]
    fresh = "Rebuild complete — FTP 232 W now drives every session target in the plan."
    assert is_degenerate_reply(fresh, history) is False


def test_max_overlap_with_recent():
    history = [
        {"role": "assistant", "content": "Alpha beta gamma delta epsilon zeta eta theta."},
        {"role": "assistant", "content": "Completely unrelated words about swimming technique drills."},
    ]
    score, index = max_overlap_with_recent(
        "Alpha beta gamma delta epsilon zeta eta theta iota.",
        history,
    )
    assert score >= DEGENERATE_OVERLAP_THRESHOLD
    assert index == 1


def test_extract_section_signature():
    text = """🟢 TODAY'S CALL
**Ready**
🗣️ LOCKER ROOM DIRECTIVE
Go easy
🗓️ REVISED WEEK
| Day | Session |"""
    sig = extract_section_signature(text)
    assert "today_call" in sig
    assert "directive" in sig
    assert "revised_week" in sig


def test_extract_analogies_used():
    text = "Think of ACWR like a battery that needs charging before hard work."
    found = extract_analogies_used(text)
    assert "battery" in found


def test_build_variety_retry_block_mentions_overlap():
    block = build_variety_retry_block(
        overlap_score=0.82,
        last_reply="Same words again about ACWR and easy days.",
        section_signature=["today_call", "directive"],
        analogies_used=["engine"],
    )
    assert "82%" in block or "0.82" in block.lower() or "82" in block
    assert "engine" in block
    assert "Say it differently" in block


def test_analyze_reply_variety_metadata():
    history = [{"role": "assistant", "content": "Prior reply about training load."}]
    meta = analyze_reply_variety(
        "🟢 TODAY'S CALL\n**Ready**\n🗣️ DIRECTIVE\nGo",
        history,
    )
    assert "overlap_score" in meta
    assert "section_signature" in meta
    assert "section_signature_hash" in meta
    assert isinstance(meta["analogies_used"], list)


def test_variety_prompt_block_with_history():
    history = [
        {
            "role": "assistant",
            "content": "🟢 TODAY'S CALL\nEngine metaphor for ACWR loading.",
        }
    ]
    block = variety_prompt_block(history)
    assert "Phase 5" in block
    assert "engine" in block.lower() or "Banned" in block


def test_normalize_for_overlap_strips_table():
    text = """Intro line here
| Day | Session |
|---|---|
| Mon | Easy |"""
    normalized = normalize_for_overlap(text)
    assert "|" not in normalized
    assert "intro line" in normalized


def run() -> None:
    tests = [
        test_trigram_overlap_identical,
        test_trigram_overlap_different,
        test_is_degenerate_reply_detects_copy,
        test_is_degenerate_reply_allows_fresh_reply,
        test_max_overlap_with_recent,
        test_extract_section_signature,
        test_extract_analogies_used,
        test_build_variety_retry_block_mentions_overlap,
        test_analyze_reply_variety_metadata,
        test_variety_prompt_block_with_history,
        test_normalize_for_overlap_strips_table,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()
