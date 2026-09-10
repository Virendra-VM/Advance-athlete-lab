"""Phase B — skill-driven tool prefetch for coach chat.

The agent does not replace the intent router. It runs deterministic tools for the
resolved skill, then injects ground-truth JSON into the narrator prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.coach_skills import (
    SKILL_ADJUST_DAY,
    SKILL_EXPLAIN_METRIC,
    SKILL_GENERAL_CHAT,
    SKILL_GO_DEEPER,
    SKILL_REBUILD_WEEK,
    SKILL_REVIEW_SESSION,
    SKILL_SUPPORT_CHAT,
    SKILL_VALIDATE_PLAN,
    SKILL_WEEK_DEBRIEF,
    SKILL_WEEK_PLAN_REVIEW,
)
from app.services.coach_tools import (
    TOOL_CHECK_INJURY_RULES,
    TOOL_COMPARE_PLANNED_VS_DONE,
    TOOL_EXPLAIN_WITH_EVIDENCE,
    TOOL_GET_ATHLETE_SNAPSHOT,
    TOOL_GET_COACH_MEMORY,
    TOOL_GET_WEEK_PLAN,
    TOOL_PROPOSE_DAY_CHANGE,
    CoachToolContext,
    ToolResult,
    execute_tool,
    format_tool_results,
)

# Skill → tools to prefetch before the LLM narrates.
SKILL_TOOL_PLAN: dict[str, tuple[str, ...]] = {
    SKILL_VALIDATE_PLAN: (
        TOOL_GET_COACH_MEMORY,
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
        TOOL_CHECK_INJURY_RULES,
    ),
    SKILL_GO_DEEPER: (
        TOOL_GET_COACH_MEMORY,
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
    ),
    SKILL_SUPPORT_CHAT: (
        TOOL_GET_COACH_MEMORY,
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_CHECK_INJURY_RULES,
    ),
    SKILL_GENERAL_CHAT: (
        TOOL_GET_COACH_MEMORY,
        TOOL_GET_ATHLETE_SNAPSHOT,
    ),
    SKILL_EXPLAIN_METRIC: (
        TOOL_GET_COACH_MEMORY,
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_EXPLAIN_WITH_EVIDENCE,
    ),
    SKILL_ADJUST_DAY: (
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
        TOOL_PROPOSE_DAY_CHANGE,
        TOOL_CHECK_INJURY_RULES,
    ),
    SKILL_REVIEW_SESSION: (
        TOOL_COMPARE_PLANNED_VS_DONE,
        TOOL_GET_ATHLETE_SNAPSHOT,
    ),
    SKILL_REBUILD_WEEK: (
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
        TOOL_CHECK_INJURY_RULES,
    ),
    SKILL_WEEK_DEBRIEF: (
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
    ),
    SKILL_WEEK_PLAN_REVIEW: (
        TOOL_GET_ATHLETE_SNAPSHOT,
        TOOL_GET_WEEK_PLAN,
        TOOL_CHECK_INJURY_RULES,
    ),
}


@dataclass
class CoachAgentRun:
    skill: str
    tools_requested: list[str] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)

    @property
    def tools_used(self) -> list[str]:
        return [result.tool for result in self.results if result.ok]

    def prompt_block(self) -> str:
        return format_tool_results(self.results)


def tools_for_skill(skill: str) -> tuple[str, ...]:
    return SKILL_TOOL_PLAN.get(skill, (TOOL_GET_ATHLETE_SNAPSHOT,))


def run_coach_agent(ctx: CoachToolContext) -> CoachAgentRun:
    """Execute the tool plan for this skill."""
    requested = list(tools_for_skill(ctx.skill))
    results = [execute_tool(name, ctx) for name in requested]
    return CoachAgentRun(skill=ctx.skill, tools_requested=requested, results=results)
