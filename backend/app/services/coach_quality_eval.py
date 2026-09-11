"""Phase E — conversation quality at scale (routing + reply regression)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.coach_advisory import is_go_deeper_followup, is_plan_advice_message
from app.services.coach_intent import classify_chat_intent
from app.services.coach_advisory import template_plan_advice
from app.services.coach_reply_eval import (
    CoachEvalExpectation,
    score_message_grounding,
    score_phase_e_reply,
)
from app.services.coach_skills import resolve_coach_skill

DEFAULT_ROUTING_PASS_RATE = 0.98
DEFAULT_QUALITY_PASS_SCORE = 0.65


@dataclass(frozen=True)
class RoutingResult:
    intent: str
    skill: str
    plan_advice_mode: bool
    go_deeper_mode: bool


def resolve_message_routing(message: str) -> RoutingResult:
    plan_advice_mode = is_plan_advice_message(message)
    go_deeper_mode = is_go_deeper_followup(message)
    intent = classify_chat_intent(message, use_llm=False)
    resolution = resolve_coach_skill(
        intent,
        message,
        plan_advice_mode=plan_advice_mode,
        go_deeper_mode=go_deeper_mode,
    )
    return RoutingResult(
        intent=intent,
        skill=resolution.skill,
        plan_advice_mode=plan_advice_mode,
        go_deeper_mode=go_deeper_mode,
    )


def evaluate_routing_case(case) -> dict[str, Any]:
    routing = resolve_message_routing(case.message)
    skill_ok = routing.skill in case.acceptable_skills
    intent_ok = case.expected_intent is None or routing.intent == case.expected_intent
    return {
        "case_id": case.case_id,
        "category": getattr(case, "category", None),
        "message": case.message,
        "pass": skill_ok,
        "skill_ok": skill_ok,
        "intent_ok": intent_ok,
        "expected_skill": case.expected_skill,
        "acceptable_skills": list(case.acceptable_skills),
        "expected_intent": case.expected_intent,
        "actual_skill": routing.skill,
        "actual_intent": routing.intent,
        "plan_advice_mode": routing.plan_advice_mode,
        "go_deeper_mode": routing.go_deeper_mode,
    }


def run_routing_regression(
    cases,
    *,
    min_pass_rate: float = DEFAULT_ROUTING_PASS_RATE,
) -> dict[str, Any]:
    results = [evaluate_routing_case(case) for case in cases]
    passed = sum(1 for row in results if row["pass"])
    total = len(results)
    pass_rate = passed / total if total else 1.0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 4),
        "min_pass_rate": min_pass_rate,
        "regression_pass": pass_rate >= min_pass_rate,
        "failures": [row for row in results if not row["pass"]],
        "cases": results,
    }


def evaluate_reply_quality(
    reply: str,
    *,
    skill: str | None,
    expectation: CoachEvalExpectation | None = None,
    require_science_terms: bool = False,
) -> dict[str, Any]:
    return score_phase_e_reply(
        reply,
        skill=skill,
        expectation=expectation,
        require_science_terms=require_science_terms,
    )


def evaluate_grounding_case(case) -> dict[str, Any]:
    reply_payload = template_plan_advice(
        case.message,
        {"load": {"minutes_acwr": 0.95}},
        context={
            "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
            "coros": {"latest_health": {"hrv": 63}},
        },
    )
    reply = reply_payload.get("reply") or ""
    score, detail = score_message_grounding(
        reply,
        forbidden_patterns=case.forbidden_patterns,
        required_patterns=case.required_patterns,
    )
    return {
        "case_id": case.case_id,
        "description": getattr(case, "description", None),
        "pass": score >= 1.0,
        "score": score,
        "detail": detail,
        "reply_preview": reply[:240],
    }


def run_grounding_regression(
    cases,
    *,
    min_pass_rate: float = 1.0,
) -> dict[str, Any]:
    results = [evaluate_grounding_case(case) for case in cases]
    passed = sum(1 for row in results if row["pass"])
    total = len(results)
    pass_rate = passed / total if total else 1.0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 4),
        "min_pass_rate": min_pass_rate,
        "regression_pass": pass_rate >= min_pass_rate,
        "failures": [row for row in results if not row["pass"]],
        "cases": results,
    }


def run_quality_regression(
    reply_cases: list[tuple[Any, str, CoachEvalExpectation | None]],
    *,
    min_avg_score: float = DEFAULT_QUALITY_PASS_SCORE,
) -> dict[str, Any]:
    scored_rows: list[dict[str, Any]] = []
    for case, reply, expectation in reply_cases:
        skill = getattr(case, "expected_skill", None)
        scored = evaluate_reply_quality(
            reply,
            skill=skill,
            expectation=expectation,
            require_science_terms=getattr(case, "category", "") == "explain_metric",
        )
        scored_rows.append(
            {
                "case_id": case.case_id,
                "category": getattr(case, "category", None),
                "score": scored,
                "pass": scored["total"] >= min_avg_score,
            }
        )
    totals = [row["score"]["total"] for row in scored_rows]
    avg = sum(totals) / len(totals) if totals else 1.0
    return {
        "cases": len(scored_rows),
        "overall_avg": round(avg, 3),
        "min_avg_score": min_avg_score,
        "regression_pass": avg >= min_avg_score,
        "rows": scored_rows,
    }
