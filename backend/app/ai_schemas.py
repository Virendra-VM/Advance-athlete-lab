"""Structured output contracts for the AI coach.

Every provider response is validated against these models before it reaches the
safety validator or the database. Anything that fails validation is retried once
and then falls back to the deterministic provider.
"""

from __future__ import annotations

from datetime import date

from typing import Any

from pydantic import BaseModel, Field, field_validator

SESSION_TYPES = {
    "rest",
    "easy",
    "long",
    "tempo",
    "threshold",
    "intervals",
    "hills",
    "speed",
    "strength",
    "mobility",
    "cross-training",
    "race",
}


class PlanSegment(BaseModel):
    segment: str
    duration_min: float | None = None
    intensity: str | None = None


class PlannedWorkoutJSON(BaseModel):
    date: date
    sport: str = Field(max_length=64)
    title: str = Field(max_length=200)
    session_type: str = Field(max_length=32)
    duration_min: float | None = Field(default=None, ge=0, le=600)
    distance_m: float | None = Field(default=None, ge=0, le=500000)
    intensity: str | None = Field(default=None, max_length=200)
    description: str | None = None
    structure: list[PlanSegment] = []

    @field_validator("session_type")
    @classmethod
    def normalize_session_type(cls, value: str) -> str:
        normalized = (value or "").strip().lower().replace("_", "-")
        if normalized in SESSION_TYPES:
            return normalized
        aliases = {
            "recovery": "easy",
            "aerobic": "easy",
            "endurance": "long",
            "interval": "intervals",
            "gym": "strength",
            "lifting": "strength",
            "stretch": "mobility",
            "yoga": "mobility",
            "off": "rest",
            "cross training": "cross-training",
            "crosstraining": "cross-training",
            "quality": "threshold",
            "hard": "threshold",
            "football": "cross-training",
            "soccer": "cross-training",
            "match": "cross-training",
        }
        return aliases.get(normalized, "easy")


class WeekPlanJSON(BaseModel):
    title: str = Field(max_length=200)
    summary: str
    focus: str | None = Field(default=None, max_length=200)
    week_start: date
    workouts: list[PlannedWorkoutJSON] = []
    coach_notes: str | None = None
    citations: list[str] = []


class DailyAdviceJSON(BaseModel):
    headline: str = Field(max_length=200)
    recommendation: str
    session_adjustment: str | None = None
    rationale: str | None = None
    citations: list[str] = []
    escalate: bool = False
    escalation_reason: str | None = None


class ChatReplyJSON(BaseModel):
    reply: str
    citations: list[str] = []
    escalate: bool = False
    escalation_reason: str | None = None
    intent: str | None = None
    week_plan: Any | None = None
