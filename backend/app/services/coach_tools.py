"""Phase B — deterministic coach tools (ground truth for the narrator).

The LLM narrates; tools fetch real athlete data. Each tool returns structured JSON
the model must not invent or override.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.coach_safety import detect_clinical_boundary, has_spine_lock
from app.services.session_blueprints import downgrade_today_workout

TOOL_GET_ATHLETE_SNAPSHOT = "get_athlete_snapshot"
TOOL_GET_WEEK_PLAN = "get_week_plan"
TOOL_PROPOSE_DAY_CHANGE = "propose_day_change"
TOOL_EXPLAIN_WITH_EVIDENCE = "explain_with_evidence"
TOOL_COMPARE_PLANNED_VS_DONE = "compare_planned_vs_done"
TOOL_CHECK_INJURY_RULES = "check_injury_rules"
TOOL_GET_COACH_MEMORY = "get_coach_memory"

ALL_TOOLS = (
    TOOL_GET_ATHLETE_SNAPSHOT,
    TOOL_GET_WEEK_PLAN,
    TOOL_PROPOSE_DAY_CHANGE,
    TOOL_EXPLAIN_WITH_EVIDENCE,
    TOOL_COMPARE_PLANNED_VS_DONE,
    TOOL_CHECK_INJURY_RULES,
    TOOL_GET_COACH_MEMORY,
)

METRIC_TOPIC_RE = re.compile(
    r"\b(acwr|hrv|ftp|lthr|tss|zone\s*2|readiness|sleep|polarized|periodization|taper)\b",
    re.I,
)


@dataclass
class CoachToolContext:
    message: str
    skill: str
    context: dict
    safety: dict
    clock: dict
    current_plan: dict | None = None
    hits: list[dict] = field(default_factory=list)
    session_packet: dict | None = None
    week_packet: dict | None = None
    activity_id: int | None = None
    memory_snapshot: list[dict] | None = None


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: dict[str, Any]
    error: str | None = None


def _today_workout(plan: dict | None, today: date) -> dict | None:
    if not plan:
        return None
    for workout in (plan.get("plan") or plan).get("workouts") or plan.get("workouts") or []:
        try:
            day = date.fromisoformat(str(workout.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        if day == today:
            return dict(workout)
    return None


def _infer_evidence_topic(message: str) -> str:
    text = (message or "").strip()
    match = METRIC_TOPIC_RE.search(text)
    if match:
        return match.group(1).lower()
    return text[:120] or "training load"


def tool_get_athlete_snapshot(ctx: CoachToolContext) -> ToolResult:
    load = (ctx.safety or {}).get("load") or {}
    readiness = (ctx.safety or {}).get("readiness") or {}
    auto = (ctx.safety or {}).get("autoregulation") or (ctx.safety or {}).get("todays_call") or {}
    health = ((ctx.context or {}).get("coros") or {}).get("latest_health") or {}
    physiology = (ctx.context or {}).get("physiology") or {}
    data = {
        "today": ctx.clock.get("today"),
        "readiness": {
            "action": readiness.get("action"),
            "reason": readiness.get("reason"),
            "call_level": auto.get("call_level"),
            "call_label": auto.get("label"),
        },
        "load": {
            "minutes_acwr": load.get("minutes_acwr"),
            "acute_minutes_7d": load.get("acute_minutes"),
            "chronic_minutes_28d": load.get("chronic_minutes"),
        },
        "daily_check_in": {
            "sleep_score": health.get("sleep_score"),
            "hrv": health.get("hrv"),
            "hrv_assessment": health.get("hrv_assessment"),
            "resting_hr_bpm": health.get("resting_heart_rate"),
            "stress": health.get("stress"),
            "metric_date": health.get("metric_date"),
        },
        "anchors": {
            "ftp_watts": physiology.get("ftp_watts") or physiology.get("ftp_estimated_watts"),
            "lthr_bpm": physiology.get("lthr_bpm"),
            "max_hr_bpm": physiology.get("max_hr_bpm"),
            "threshold_pace_sec_per_km": physiology.get("threshold_pace_sec_per_km"),
        },
        "flags": list((ctx.context or {}).get("readiness_flags") or []),
    }
    return ToolResult(TOOL_GET_ATHLETE_SNAPSHOT, True, data)


def tool_get_week_plan(ctx: CoachToolContext) -> ToolResult:
    plan = ctx.current_plan
    if not plan:
        return ToolResult(
            TOOL_GET_WEEK_PLAN,
            True,
            {"week_start": ctx.clock.get("week_start"), "workouts": [], "note": "no_active_plan"},
        )
    rows = []
    today = ctx.clock.get("today")
    for workout in (plan.get("plan") or plan).get("workouts") or []:
        try:
            day = date.fromisoformat(str(workout.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        when = "today" if day == today else ("past" if day < today else "upcoming")
        rows.append(
            {
                "date": day.isoformat(),
                "when": when,
                "title": workout.get("title"),
                "sport": workout.get("sport"),
                "session_type": workout.get("session_type"),
                "intensity": workout.get("intensity"),
                "duration_min": workout.get("duration_min"),
                "completed": bool(workout.get("completed_activity_id")),
            }
        )
    return ToolResult(
        TOOL_GET_WEEK_PLAN,
        True,
        {"week_start": ctx.clock.get("week_start"), "workouts": rows},
    )


def tool_propose_day_change(ctx: CoachToolContext) -> ToolResult:
    today = ctx.clock.get("today")
    if not isinstance(today, date):
        return ToolResult(TOOL_PROPOSE_DAY_CHANGE, False, {}, "invalid_clock")
    original = _today_workout(ctx.current_plan, today)
    if not original:
        return ToolResult(
            TOOL_PROPOSE_DAY_CHANGE,
            True,
            {"date": today.isoformat(), "changed": False, "reason": "no_session_scheduled_today"},
        )
    proposed = downgrade_today_workout(original, ctx.safety)
    changed = (
        proposed.get("session_type") != original.get("session_type")
        or proposed.get("title") != original.get("title")
        or proposed.get("intensity") != original.get("intensity")
    )
    return ToolResult(
        TOOL_PROPOSE_DAY_CHANGE,
        True,
        {
            "date": today.isoformat(),
            "changed": changed,
            "before": {
                "title": original.get("title"),
                "session_type": original.get("session_type"),
                "intensity": original.get("intensity"),
            },
            "after": {
                "title": proposed.get("title"),
                "session_type": proposed.get("session_type"),
                "intensity": proposed.get("intensity"),
                "description": proposed.get("description"),
            },
            "readiness_action": ((ctx.safety or {}).get("readiness") or {}).get("action"),
        },
    )


def tool_explain_with_evidence(ctx: CoachToolContext) -> ToolResult:
    topic = _infer_evidence_topic(ctx.message)
    chunks = []
    for hit in ctx.hits or []:
        citation = hit.get("citation") or {}
        chunks.append(
            {
                "slug": citation.get("slug"),
                "heading": hit.get("heading"),
                "excerpt": (hit.get("text") or hit.get("content") or "")[:400],
                "score": hit.get("score"),
            }
        )
    return ToolResult(
        TOOL_EXPLAIN_WITH_EVIDENCE,
        True,
        {
            "topic": topic,
            "grounded": bool(chunks),
            "chunks": chunks[:4],
            "instruction": "Cite only retrieved chunks; if empty say evidence is not in playbook.",
        },
    )


def tool_compare_planned_vs_done(ctx: CoachToolContext) -> ToolResult:
    packet = ctx.session_packet
    if not packet:
        return ToolResult(
            TOOL_COMPARE_PLANNED_VS_DONE,
            True,
            {"matched": False, "reason": "no_session_telemetry_loaded"},
        )
    summary = {
        "matched": True,
        "activity_id": packet.get("activity_id"),
        "sport": packet.get("sport"),
        "modality": packet.get("modality"),
        "date": packet.get("date"),
        "when": packet.get("when"),
        "classification": packet.get("classification"),
        "anchors_used": packet.get("anchors_used"),
        "prescription": packet.get("prescription"),
        "prescribed_vs_executed": packet.get("prescribed_vs_executed"),
        "library_compliance": packet.get("library_compliance"),
        "summary_metrics": {
            key: packet.get(key)
            for key in (
                "duration_min",
                "distance_km",
                "avg_hr",
                "normalized_power",
                "intensity_factor",
                "tss",
            )
            if packet.get(key) is not None
        },
    }
    return ToolResult(TOOL_COMPARE_PLANNED_VS_DONE, True, summary)


def tool_get_coach_memory(ctx: CoachToolContext) -> ToolResult:
    snapshot = ctx.memory_snapshot or []
    return ToolResult(
        TOOL_GET_COACH_MEMORY,
        True,
        {
            "count": len(snapshot),
            "memories": snapshot[:12],
            "instruction": "Reference naturally in empathy or advice — never dump as a list.",
        },
    )


def tool_check_injury_rules(ctx: CoachToolContext) -> ToolResult:
    injuries = (ctx.safety or {}).get("injuries") or {}
    clinical = detect_clinical_boundary(ctx.message)
    readiness = (ctx.safety or {}).get("readiness") or {}
    load = (ctx.safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    hard_veto = isinstance(acwr, (int, float)) and acwr > 1.5
    data = {
        "active_injuries": injuries.get("active") or [],
        "avoid_keywords": injuries.get("avoid_keywords") or [],
        "spine_lock": has_spine_lock(injuries) or bool(ctx.safety.get("spine_lock")),
        "clinical_boundary_hit": bool(clinical),
        "clinical_kind": (clinical or {}).get("kind") if clinical else None,
        "readiness_action": readiness.get("action"),
        "hard_session_veto": hard_veto or readiness.get("action") in {
            "rest_or_mobility",
            "downgrade_to_easy",
        },
        "acwr": acwr,
        "max_hard_sessions": ctx.safety.get("max_hard_sessions"),
        "no_consecutive_hard_days": ctx.safety.get("no_consecutive_hard_days"),
    }
    return ToolResult(TOOL_CHECK_INJURY_RULES, True, data)


TOOL_EXECUTORS = {
    TOOL_GET_ATHLETE_SNAPSHOT: tool_get_athlete_snapshot,
    TOOL_GET_WEEK_PLAN: tool_get_week_plan,
    TOOL_PROPOSE_DAY_CHANGE: tool_propose_day_change,
    TOOL_EXPLAIN_WITH_EVIDENCE: tool_explain_with_evidence,
    TOOL_COMPARE_PLANNED_VS_DONE: tool_compare_planned_vs_done,
    TOOL_CHECK_INJURY_RULES: tool_check_injury_rules,
    TOOL_GET_COACH_MEMORY: tool_get_coach_memory,
}


def execute_tool(name: str, ctx: CoachToolContext) -> ToolResult:
    executor = TOOL_EXECUTORS.get(name)
    if not executor:
        return ToolResult(name, False, {}, f"unknown_tool:{name}")
    try:
        return executor(ctx)
    except Exception as exc:  # noqa: BLE001 — one bad tool must not break chat
        return ToolResult(name, False, {}, str(exc))


def format_tool_results(results: list[ToolResult]) -> str:
    if not results:
        return ""
    blocks = [
        "COACH TOOLS (ground truth — use these numbers only; do not invent or override)",
    ]
    for result in results:
        status = "ok" if result.ok else "error"
        payload = result.data if result.ok else {"error": result.error}
        blocks.append(f"Tool: {result.tool} [{status}]\n{json.dumps(payload, indent=2, default=str)}")
    return "\n\n".join(blocks)
