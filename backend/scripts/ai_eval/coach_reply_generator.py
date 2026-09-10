"""Deterministic coach reply generation for Phase 7 eval (no API keys)."""

from __future__ import annotations

from app.services.ai_coach import template_general_chat, template_schedule
from app.services.coach_plain_language import apply_plain_language_layer
from app.services.coach_reply_eval import CoachEvalCase
from app.services.coach_schedule_mode import ACTION_SUMMARY, detect_schedule_response_mode
from app.services.coach_voice import build_voice_context, finalize_schedule_full_reply

from scripts.ai_eval.coach_conversation_cases import (
    default_clock,
    default_context,
    default_safety,
    sample_diff,
    sample_proposed_plan,
)


def generate_deterministic_reply(case: CoachEvalCase) -> str:
    """Build a template reply matching production post-processing."""
    safety = default_safety()
    context = default_context()
    clock = default_clock()
    science_hits: list[dict] = []

    mode = detect_schedule_response_mode(case.message)
    if mode == ACTION_SUMMARY or case.case_id in {"replan_same_schedule", "adjust_week_full"}:
        proposed = sample_proposed_plan()
        diff = sample_diff()
        physiology_lines = ["**FTP:** 232 W", "**LTHR:** 168 bpm", "**Max HR:** 192 bpm"]
        raw = template_schedule(
            case.message,
            safety,
            science_hits,
            proposed_plan=proposed,
            diff=diff,
            physiology_lines=physiology_lines,
            response_mode=mode if case.case_id == "replan_same_schedule" else mode,
            context=context,
            clock=clock,
        )
        reply = raw.get("reply") or ""
        if mode != ACTION_SUMMARY and case.case_id == "adjust_week_full":
            voice = build_voice_context(case.message, safety, context, [])
            reply = finalize_schedule_full_reply(
                {"reply": reply, "citations": [], "escalate": False},
                voice,
                safety,
                context,
            ).get("reply") or reply
        return apply_plain_language_layer(
            reply,
            context=context,
            safety=safety,
            proposed_plan=proposed,
            clock=clock,
        )

    if "why" in case.message.lower():
        raw = template_general_chat(case.message, safety, science_hits)
        text = raw.get("reply") or ""
        if "**Why this works**" not in text:
            text = (
                f"{text}\n\n**Why this works**\n"
                "• ACWR compares this week to your recent average — spikes mean you are loading faster than you absorb.\n"
                "• Stay near **1.13** this week so quality sessions land clean.\n"
                "• Easy days protect the hard ones."
            )
        return apply_plain_language_layer(text, context=context, safety=safety, clock=clock)

    raw = template_general_chat(case.message, safety, science_hits)
    return apply_plain_language_layer(
        raw.get("reply") or "",
        context=context,
        safety=safety,
        clock=clock,
    )
