"""Menstrual cycle detection and phase-aware training adjustments."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteProfile, CorosCycleSnapshot, CyclePeriodLog

ISO_DATE = re.compile(r"\b(20\d{2})[-/]?(0[1-9]|1[0-2])[-/]?([0-3]\d)\b")


def _parse_date_value(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    if len(text) == 8 and text.isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
    match = ISO_DATE.search(text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def parse_period_starts_from_coros(data: Any) -> list[date]:
    """Best-effort extraction of period start dates from COROS cycle payload."""
    starts: list[date] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_lower = str(key).lower()
                if any(token in key_lower for token in ("start", "period", "menstru", "cycle")):
                    parsed = _parse_date_value(value)
                    if parsed:
                        starts.append(parsed)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            parsed = _parse_date_value(node)
            if parsed:
                starts.append(parsed)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            for match in ISO_DATE.finditer(data):
                try:
                    starts.append(
                        date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    )
                except ValueError:
                    continue
            return sorted(set(starts))

    walk(data)
    return sorted(set(starts))


def ingest_coros_period_starts(db: Session, athlete_profile_id: int) -> int:
    """Persist period starts parsed from the latest COROS cycle snapshots."""
    rows = (
        db.query(CorosCycleSnapshot)
        .filter(CorosCycleSnapshot.athlete_profile_id == athlete_profile_id)
        .order_by(CorosCycleSnapshot.snapshot_at.desc())
        .limit(12)
        .all()
    )
    imported = 0
    seen: set[date] = set()
    for row in rows:
        raw = row.raw_json
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            payload = raw
        for start in parse_period_starts_from_coros(payload):
            if start in seen:
                continue
            seen.add(start)
            existing = (
                db.query(CyclePeriodLog)
                .filter(
                    CyclePeriodLog.athlete_profile_id == athlete_profile_id,
                    CyclePeriodLog.period_start_date == start,
                )
                .first()
            )
            if existing is None:
                db.add(
                    CyclePeriodLog(
                        athlete_profile_id=athlete_profile_id,
                        period_start_date=start,
                        source="coros",
                    )
                )
                imported += 1
    return imported


def list_period_starts(db: Session, athlete_profile_id: int, *, lookback_days: int = 120) -> list[date]:
    start = date.today() - timedelta(days=max(30, lookback_days))
    rows = (
        db.query(CyclePeriodLog.period_start_date)
        .filter(
            CyclePeriodLog.athlete_profile_id == athlete_profile_id,
            CyclePeriodLog.period_start_date >= start,
        )
        .order_by(CyclePeriodLog.period_start_date.asc())
        .all()
    )
    return [row[0] for row in rows]


def detect_cycle_starts(starts: list[date], *, gap_days: int = 7) -> list[date]:
    if not starts:
        return []
    ordered = sorted(set(starts))
    cycles = [ordered[0]]
    for current in ordered[1:]:
        if (current - cycles[-1]).days > gap_days:
            cycles.append(current)
    return cycles


def average_cycle_length(starts: list[date], *, default: int = 28) -> int:
    if len(starts) < 2:
        return default
    gaps = [(starts[index + 1] - starts[index]).days for index in range(len(starts) - 1)]
    gaps = [gap for gap in gaps if 18 <= gap <= 45]
    if not gaps:
        return default
    return max(18, min(45, round(mean(gaps))))


def map_cycle_phase(day_in_cycle: int, cycle_length: int) -> str:
    if day_in_cycle <= 5:
        return "menstrual"
    if day_in_cycle <= 13:
        return "follicular"
    if day_in_cycle <= 17:
        return "ovulatory"
    if day_in_cycle <= max(18, cycle_length - 3):
        return "luteal"
    return "late_luteal"


def build_cycle_context(
    profile: AthleteProfile,
    period_starts: list[date],
    *,
    on_date: date | None = None,
) -> dict[str, Any] | None:
    if not profile.cycle_tracking_enabled:
        return None

    on_date = on_date or date.today()
    cycle_starts = detect_cycle_starts(period_starts)
    if not cycle_starts:
        return {
            "enabled": True,
            "available": False,
            "message": "Cycle tracking is on — log a period start to enable phase adjustments.",
        }

    last_start = max(start for start in cycle_starts if start <= on_date) if any(
        start <= on_date for start in cycle_starts
    ) else cycle_starts[-1]
    cycle_length = profile.cycle_length_manual or average_cycle_length(cycle_starts)
    day_in_cycle = (on_date - last_start).days + 1
    if day_in_cycle < 1:
        day_in_cycle = 1

    next_start = last_start + timedelta(days=cycle_length)
    days_to_next = (next_start - on_date).days
    phase = map_cycle_phase(day_in_cycle, cycle_length)

    return {
        "enabled": True,
        "available": True,
        "on_date": on_date.isoformat(),
        "last_period_start": last_start.isoformat(),
        "cycle_length": cycle_length,
        "day_in_cycle": day_in_cycle,
        "phase": phase,
        "days_to_next_period": days_to_next,
        "late_luteal": phase == "late_luteal" or days_to_next <= 3,
        "training_note": phase_training_note(phase, day_in_cycle),
    }


def phase_training_note(phase: str, day_in_cycle: int) -> str:
    notes = {
        "menstrual": "Menstrual phase — prioritize recovery and easy aerobic work.",
        "follicular": "Follicular phase — rising tolerance; quality sessions generally well tolerated.",
        "ovulatory": "Ovulatory window — neuromuscular power often peaks; use quality wisely.",
        "luteal": "Luteal phase — respect RPE; hydration and sleep matter more.",
        "late_luteal": "Late luteal — downshift intensity; protect sleep and autonomic balance.",
    }
    return notes.get(phase, f"Cycle day {day_in_cycle}.")


def menstrual_downgrade_steps(cycle_ctx: dict[str, Any] | None) -> tuple[int, list[str], list[dict[str, str]]]:
    """Return extra downgrade steps and warnings for autoregulation."""
    if not cycle_ctx or not cycle_ctx.get("enabled") or not cycle_ctx.get("available"):
        return 0, [], []

    steps = 0
    reasons: list[str] = []
    warnings: list[dict[str, str]] = []
    phase = cycle_ctx.get("phase")
    day = cycle_ctx.get("day_in_cycle")
    days_to_next = cycle_ctx.get("days_to_next_period")

    if phase == "menstrual" or (isinstance(day, int) and 1 <= day <= 5):
        steps += 1
        reasons.append(f"Menstrual phase (day {day})")
    if cycle_ctx.get("late_luteal") or (
        isinstance(days_to_next, int) and 0 <= days_to_next <= 3
    ):
        steps += 1
        reasons.append("Late luteal — within 3 days of period")
        warnings.append(
            {
                "code": "period_incoming",
                "message": "Period likely within 3 days — consider downshifting intensity",
                "severity": "info",
                "link": "/profile#profile-health",
            }
        )
    return steps, reasons, warnings


def build_cycle_context_for_athlete(
    db: Session,
    profile: AthleteProfile,
    *,
    on_date: date | None = None,
    ingest_coros: bool = True,
) -> dict[str, Any] | None:
    if not profile.cycle_tracking_enabled:
        return None
    if ingest_coros:
        ingest_coros_period_starts(db, profile.id)
        db.commit()
    starts = list_period_starts(db, profile.id)
    return build_cycle_context(profile, starts, on_date=on_date)
