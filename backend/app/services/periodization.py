"""Retrograde periodization from A-race backward through macro training blocks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteProfile, SeasonPhase, SeasonPlan
from app.services.b_race_calibration import calibrate_from_b_race
from app.services.zone_recalibration import d_race_test_protocol

VALID_PRIORITIES = frozenset({"A", "B", "C", "D", "E"})
VALID_SPORTS = frozenset({"run", "bike", "swim", "strength", "other"})
MACRO_PHASES = ("base", "build", "peak", "taper")
PHASE_RATIOS = {"base": 0.40, "build": 0.30, "peak": 0.20, "taper": 0.10}

PHASE_DEFAULTS: dict[str, dict[str, Any]] = {
    "base": {
        "intent": "Build aerobic volume, structural strength, and tissue durability.",
        "volume_bias": 1.1,
        "intensity_bias": "low",
        "long_session_allowed_min": 240,
    },
    "build": {
        "intent": "Raise LT2/FTP with tempo, over-unders, and controlled quality.",
        "volume_bias": 1.0,
        "intensity_bias": "moderate",
        "long_session_allowed_min": 210,
    },
    "peak": {
        "intent": "Race-pace economy, pacing precision, and muscular endurance.",
        "volume_bias": 0.95,
        "intensity_bias": "high",
        "long_session_allowed_min": 180,
    },
    "taper": {
        "intent": "Reduce volume 40–60% while keeping some race-pace touches.",
        "volume_bias": 0.55,
        "intensity_bias": "moderate",
        "long_session_allowed_min": 90,
    },
    "restore": {
        "intent": "Parasympathetic reset after A-race — mobility and easy aerobic work.",
        "volume_bias": 0.4,
        "intensity_bias": "low",
        "long_session_allowed_min": 60,
    },
    "recovery_week": {
        "intent": "Absorb load — keep frequency, cut duration and intensity ~30%.",
        "volume_bias": 0.7,
        "intensity_bias": "low",
        "long_session_allowed_min": 120,
    },
}


@dataclass(frozen=True)
class PhaseBlock:
    phase_type: str
    week_count: int


def monday_of(value: date) -> date:
    return value - timedelta(days=value.weekday())


def add_weeks(value: date, weeks: int) -> date:
    return value + timedelta(weeks=weeks)


def weeks_between_inclusive(start: date, end: date) -> int:
    """Calendar weeks from start Monday through end (minimum 1 if end >= start)."""
    if end < start:
        return 0
    start_m = monday_of(start)
    end_m = monday_of(end)
    days = (end_m - start_m).days
    return max(1, days // 7 + 1)


def distribute_macro_weeks(total_weeks: int, *, short_season: bool = False) -> dict[str, int]:
    """Split pre-race weeks into base/build/peak/taper (sums to total_weeks)."""
    if total_weeks <= 0:
        return {key: 0 for key in MACRO_PHASES}

    if total_weeks == 1:
        return {"base": 0, "build": 0, "peak": 0, "taper": 1}

    if total_weeks <= 4 or short_season:
        taper = 1
        peak = 1 if total_weeks >= 3 else 0
        build = 1 if total_weeks >= 4 else max(0, total_weeks - taper - peak)
        base = max(0, total_weeks - taper - peak - build)
        return {"base": base, "build": build, "peak": peak, "taper": taper}

    raw = {key: total_weeks * PHASE_RATIOS[key] for key in MACRO_PHASES}
    counts = {key: int(raw[key]) for key in MACRO_PHASES}
    # Ensure at least 1 week in taper and peak when season is long enough
    if counts["taper"] < 1:
        counts["taper"] = 1
    if total_weeks >= 8 and counts["peak"] < 1:
        counts["peak"] = 1

    assigned = sum(counts.values())
    remainder = total_weeks - assigned
    order = ["base", "build", "peak", "taper"]
    idx = 0
    while remainder > 0:
        counts[order[idx % len(order)]] += 1
        remainder -= 1
        idx += 1
    while remainder < 0:
        for key in ("base", "build"):
            if counts[key] > 1 and remainder < 0:
                counts[key] -= 1
                remainder += 1
    return counts


def insert_recovery_weeks(blocks: list[PhaseBlock], every: int = 4) -> list[PhaseBlock]:
    """Insert a recovery week after every N training weeks in base/build."""
    if every <= 0:
        return blocks

    expanded: list[PhaseBlock] = []
    train_week_idx = 0
    for block in blocks:
        if block.phase_type not in ("base", "build"):
            expanded.append(block)
            continue
        for _ in range(block.week_count):
            train_week_idx += 1
            expanded.append(PhaseBlock(block.phase_type, 1))
            if train_week_idx % every == 0:
                expanded.append(PhaseBlock("recovery_week", 1))
    return expanded


def collapse_blocks(blocks: list[PhaseBlock]) -> list[PhaseBlock]:
    if not blocks:
        return []
    merged: list[PhaseBlock] = []
    for block in blocks:
        if merged and merged[-1].phase_type == block.phase_type:
            merged[-1] = PhaseBlock(
                block.phase_type, merged[-1].week_count + block.week_count
            )
        else:
            merged.append(block)
    return merged


def blocks_to_dated_phases(
    blocks: list[PhaseBlock], season_start: date, a_race_date: date
) -> list[dict[str, Any]]:
    """Turn week blocks into dated phase rows ending the Sunday before A-race week."""
    race_week_start = monday_of(a_race_date)
    cursor = monday_of(season_start)
    phases: list[dict[str, Any]] = []
    sort_order = 0

    for block in blocks:
        if cursor >= race_week_start:
            break
        week_count = block.week_count
        phase_end = min(add_weeks(cursor, week_count) - timedelta(days=1), a_race_date - timedelta(days=1))
        if phase_end < cursor:
            break
        defaults = PHASE_DEFAULTS.get(block.phase_type, PHASE_DEFAULTS["base"])
        phases.append(
            {
                "phase_type": block.phase_type,
                "start_date": cursor,
                "end_date": phase_end,
                "week_count": week_count,
                "intent": defaults["intent"],
                "volume_bias": defaults["volume_bias"],
                "intensity_bias": defaults["intensity_bias"],
                "long_session_allowed_min": defaults["long_session_allowed_min"],
                "sort_order": sort_order,
            }
        )
        sort_order += 1
        cursor = phase_end + timedelta(days=1)
        cursor = monday_of(cursor)

    # Taper ends on A-race date (race week)
    taper_defaults = PHASE_DEFAULTS["taper"]
    taper_start = monday_of(a_race_date)
    phases.append(
        {
            "phase_type": "taper",
            "start_date": taper_start,
            "end_date": a_race_date,
            "week_count": 1,
            "intent": taper_defaults["intent"],
            "volume_bias": taper_defaults["volume_bias"],
            "intensity_bias": taper_defaults["intensity_bias"],
            "long_session_allowed_min": taper_defaults["long_session_allowed_min"],
            "sort_order": sort_order,
        }
    )
    return phases


def validate_events(events: list[AthleteEvent], a_race: AthleteEvent | None) -> list[str]:
    warnings: list[str] = []
    if a_race is None:
        return warnings

    a_date = a_race.event_date
    b_races = [event for event in events if event.priority == "B" and event.status == "planned"]

    for event in b_races:
        gap = (a_date - event.event_date).days
        if 0 <= gap < 14:
            warnings.append(
                f"B-race '{event.name}' is {gap} days before A-race — mini-taper may compromise A-race freshness."
            )
        if gap < 0:
            warnings.append(f"B-race '{event.name}' is after A-race — check priority assignment.")

    b_dates = sorted(event.event_date for event in b_races)
    for i in range(1, len(b_dates)):
        if (b_dates[i] - b_dates[i - 1]).days < 10:
            warnings.append("Two B-races are within 10 days — avoid stacked tapers.")

    return warnings


def infer_sport_type(profile: AthleteProfile) -> str:
    goal = (profile.primary_goal or "").lower()
    if "event" in goal or profile.goal_event_name:
        name = (profile.goal_event_name or "").lower()
        if "bike" in name or "cycle" in name:
            return "bike"
        if "swim" in name:
            return "swim"
        return "run"
    return "run"


def sync_a_race_from_profile(db: Session, profile: AthleteProfile) -> AthleteEvent | None:
    """Ensure profile goal_event maps to a priority-A athlete_events row."""
    if not profile.goal_event_date or not profile.goal_event_name:
        return (
            db.query(AthleteEvent)
            .filter(
                AthleteEvent.athlete_profile_id == profile.id,
                AthleteEvent.priority == "A",
                AthleteEvent.status == "planned",
            )
            .order_by(AthleteEvent.event_date.desc())
            .first()
        )

    existing = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.athlete_profile_id == profile.id,
            AthleteEvent.priority == "A",
            AthleteEvent.event_date == profile.goal_event_date,
        )
        .first()
    )
    sport = infer_sport_type(profile)
    if existing:
        existing.name = profile.goal_event_name
        existing.target_metric = profile.goal_metric
        existing.sport_type = sport
        existing.status = "planned"
        db.flush()
        canonical = existing
    else:
        row = AthleteEvent(
            athlete_profile_id=profile.id,
            name=profile.goal_event_name,
            event_date=profile.goal_event_date,
            priority="A",
            sport_type=sport,
            target_metric=profile.goal_metric,
            status="planned",
        )
        db.add(row)
        db.flush()
        canonical = row

    for duplicate in (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.athlete_profile_id == profile.id,
            AthleteEvent.priority == "A",
            AthleteEvent.status == "planned",
            AthleteEvent.id != canonical.id,
        )
        .all()
    ):
        duplicate.status = "cancelled"
    db.flush()
    return canonical


def sync_profile_from_a_race(profile: AthleteProfile, event: AthleteEvent) -> None:
    if event.priority != "A":
        return
    profile.goal_event_name = event.name
    profile.goal_event_date = event.event_date
    profile.goal_metric = event.target_metric


def list_planned_events(db: Session, athlete_profile_id: int) -> list[AthleteEvent]:
    return (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.athlete_profile_id == athlete_profile_id,
            AthleteEvent.status == "planned",
        )
        .order_by(AthleteEvent.event_date.asc())
        .all()
    )


def get_active_season_plan(db: Session, athlete_profile_id: int) -> SeasonPlan | None:
    return (
        db.query(SeasonPlan)
        .filter(
            SeasonPlan.athlete_profile_id == athlete_profile_id,
            SeasonPlan.status == "active",
        )
        .order_by(SeasonPlan.created_at.desc())
        .first()
    )


def get_phases_for_plan(db: Session, season_plan_id: int) -> list[SeasonPhase]:
    return (
        db.query(SeasonPhase)
        .filter(SeasonPhase.season_plan_id == season_plan_id)
        .order_by(SeasonPhase.sort_order.asc())
        .all()
    )


def build_phase_blocks(
    profile: AthleteProfile, season_start: date, a_race_date: date
) -> list[dict[str, Any]]:
    """Pure phase timeline ending with taper on A-race week."""
    pre_race_weeks = weeks_between_inclusive(season_start, a_race_date) - 1
    pre_race_weeks = max(pre_race_weeks, 0)
    short = pre_race_weeks <= 6 or (profile.fitness_level or "").lower().startswith("beginner")
    counts = distribute_macro_weeks(pre_race_weeks, short_season=short)

    blocks: list[PhaseBlock] = []
    for phase_type in MACRO_PHASES:
        if phase_type == "taper":
            continue
        if counts[phase_type] > 0:
            blocks.append(PhaseBlock(phase_type, counts[phase_type]))

    blocks = insert_recovery_weeks(blocks, every=4)
    blocks = collapse_blocks(blocks)
    phases = blocks_to_dated_phases(blocks, season_start, a_race_date)

    restore_start = a_race_date + timedelta(days=1)
    restore_end = restore_start + timedelta(days=6)
    restore_defaults = PHASE_DEFAULTS["restore"]
    phases.append(
        {
            "phase_type": "restore",
            "start_date": restore_start,
            "end_date": restore_end,
            "week_count": 1,
            "intent": restore_defaults["intent"],
            "volume_bias": restore_defaults["volume_bias"],
            "intensity_bias": restore_defaults["intensity_bias"],
            "long_session_allowed_min": restore_defaults["long_session_allowed_min"],
            "sort_order": len(phases),
        }
    )
    return phases


def generate_season_plan(
    db: Session,
    profile: AthleteProfile,
    *,
    today: date | None = None,
) -> SeasonPlan:
    """Build or rebuild the active season plan from A-race + events."""
    today = today or date.today()
    a_race = sync_a_race_from_profile(db, profile)
    if a_race is None:
        raise ValueError("No A-race configured. Set a goal event on your profile first.")

    if a_race.event_date <= today:
        raise ValueError("A-race date must be in the future to generate a season plan.")

    events = list_planned_events(db, profile.id)
    warnings = validate_events(events, a_race)

    for old in db.query(SeasonPlan).filter(
        SeasonPlan.athlete_profile_id == profile.id,
        SeasonPlan.status == "active",
    ):
        old.status = "archived"

    phase_payloads = build_phase_blocks(profile, today, a_race.event_date)
    restore_end = phase_payloads[-1]["end_date"] if phase_payloads else a_race.event_date

    plan = SeasonPlan(
        athlete_profile_id=profile.id,
        a_race_event_id=a_race.id,
        start_date=today,
        end_date=restore_end,
        status="active",
        template_key=f"{infer_sport_type(profile)}_{(profile.fitness_level or 'intermediate').lower()}",
        warnings_json=json.dumps(warnings),
    )
    db.add(plan)
    db.flush()

    for payload in phase_payloads:
        db.add(
            SeasonPhase(
                season_plan_id=plan.id,
                phase_type=payload["phase_type"],
                start_date=payload["start_date"],
                end_date=payload["end_date"],
                week_count=payload["week_count"],
                intent=payload["intent"],
                volume_bias=payload["volume_bias"],
                intensity_bias=payload["intensity_bias"],
                sort_order=payload["sort_order"],
            )
        )
    db.flush()
    return plan


def get_current_phase(
    phases: list[SeasonPhase], on_date: date | None = None
) -> SeasonPhase | None:
    on_date = on_date or date.today()
    for phase in phases:
        if phase.start_date <= on_date <= phase.end_date:
            return phase
    return None


def phase_defaults_for_type(phase_type: str) -> dict[str, Any]:
    return PHASE_DEFAULTS.get(phase_type, PHASE_DEFAULTS["base"])


def get_week_intent(
    phases: list[SeasonPhase],
    events: list[AthleteEvent],
    week_start: date,
    profile: AthleteProfile,
) -> dict[str, Any]:
    """Phase-aware intent for a calendar week, including race adapters."""
    week_end = week_start + timedelta(days=6)
    phase = None
    for row in phases:
        if row.start_date <= week_end and row.end_date >= week_start:
            phase = row
            break

    defaults = phase_defaults_for_type(phase.phase_type if phase else "base")
    intent = {
        "week_start": week_start.isoformat(),
        "phase_type": phase.phase_type if phase else None,
        "phase_intent": phase.intent if phase else defaults["intent"],
        "volume_bias": phase.volume_bias if phase and phase.volume_bias is not None else defaults["volume_bias"],
        "intensity_bias": phase.intensity_bias if phase else defaults["intensity_bias"],
        "long_session_allowed_min": defaults["long_session_allowed_min"],
        "notes": [],
        "events": [],
    }

    if phase:
        typed = phase_defaults_for_type(phase.phase_type)
        intent["long_session_allowed_min"] = typed["long_session_allowed_min"]

    week_events = [
        event
        for event in events
        if event.status == "planned" and week_start <= event.event_date <= week_end
    ]
    for event in week_events:
        intent["events"].append(
            {
                "name": event.name,
                "date": event.event_date.isoformat(),
                "priority": event.priority,
                "sport_type": event.sport_type,
            }
        )
        if event.priority == "B":
            intent["volume_bias"] = round(float(intent["volume_bias"]) * 0.85, 2)
            intent["notes"].append(
                f"B-race '{event.name}' — 3-day mini-taper before, 3-day active recovery after."
            )
        elif event.priority == "C":
            intent["notes"].append(
                f"C-race '{event.name}' — treat as hard workout; no taper or extra rest."
            )
        elif event.priority == "D":
            protocol = d_race_test_protocol(event)
            intent["notes"].append(
                f"D-race '{event.name}' — guided threshold test; recalibrate zones if improved."
            )
            intent.setdefault("d_race_protocols", []).append(
                {
                    "event_id": event.id,
                    "name": event.name,
                    "date": event.event_date.isoformat(),
                    **protocol,
                }
            )

    typical = profile.workout_duration_minutes or 60
    intent["typical_session_minutes"] = typical
    intent["notes"].append(
        f"Typical weekday session ~{typical} min is not a cap — long days up to "
        f"{intent['long_session_allowed_min']} min allowed in this phase."
    )
    return intent


def serialize_event(event: AthleteEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "name": event.name,
        "date": event.event_date.isoformat(),
        "priority": event.priority,
        "sport_type": event.sport_type,
        "target_metric": event.target_metric,
        "status": event.status,
        "result_metric": event.result_metric,
        "notes": event.notes,
    }


def serialize_phase(phase: SeasonPhase) -> dict[str, Any]:
    defaults = phase_defaults_for_type(phase.phase_type)
    return {
        "id": phase.id,
        "phase_type": phase.phase_type,
        "start_date": phase.start_date.isoformat(),
        "end_date": phase.end_date.isoformat(),
        "week_count": phase.week_count,
        "intent": phase.intent,
        "volume_bias": phase.volume_bias,
        "intensity_bias": phase.intensity_bias,
        "long_session_allowed_min": defaults["long_session_allowed_min"],
        "sort_order": phase.sort_order,
    }


def build_season_context(
    db: Session,
    profile: AthleteProfile,
    *,
    on_date: date | None = None,
) -> dict[str, Any] | None:
    """Compact season packet for coach context and prompts."""
    on_date = on_date or date.today()
    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        a_race = sync_a_race_from_profile(db, profile)
        if a_race is None:
            return None
        return {
            "has_plan": False,
            "a_race": serialize_event(a_race),
            "upcoming_events": [
                serialize_event(event)
                for event in list_planned_events(db, profile.id)
                if event.event_date >= on_date
            ][:8],
        }

    phases = get_phases_for_plan(db, plan.id)
    current = get_current_phase(phases, on_date)
    events = list_planned_events(db, profile.id)
    a_race = next((event for event in events if event.id == plan.a_race_event_id), None)
    if a_race is None and plan.a_race_event_id:
        a_race = db.query(AthleteEvent).filter(AthleteEvent.id == plan.a_race_event_id).first()

    week_start = monday_of(on_date)
    week_intent = get_week_intent(phases, events, week_start, profile)

    warnings: list[str] = []
    if plan.warnings_json:
        try:
            warnings = json.loads(plan.warnings_json)
        except json.JSONDecodeError:
            warnings = []

    week_in_phase = None
    if current:
        week_in_phase = weeks_between_inclusive(current.start_date, on_date)

    a_race_feasibility = None
    latest_b = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.athlete_profile_id == profile.id,
            AthleteEvent.priority == "B",
            AthleteEvent.status == "completed",
        )
        .order_by(AthleteEvent.event_date.desc())
        .first()
    )
    if latest_b and a_race:
        calibration = calibrate_from_b_race(latest_b, a_race)
        if calibration.get("available"):
            a_race_feasibility = {
                "feasibility": calibration.get("a_race_feasibility"),
                "predicted_a_time": calibration.get("predicted_a_time_formatted"),
                "b_race": calibration.get("b_race"),
                "peak_pace_note": calibration.get("peak_pace_note"),
            }
            if current and current.phase_type == "peak" and a_race_feasibility.get("peak_pace_note"):
                week_intent = {
                    **week_intent,
                    "notes": [
                        *(week_intent.get("notes") or []),
                        a_race_feasibility["peak_pace_note"],
                    ],
                }

    return {
        "has_plan": True,
        "plan_id": plan.id,
        "start_date": plan.start_date.isoformat(),
        "end_date": plan.end_date.isoformat(),
        "a_race": serialize_event(a_race) if a_race else None,
        "a_race_feasibility": a_race_feasibility,
        "current_phase": serialize_phase(current) if current else None,
        "week_in_phase": week_in_phase,
        "week_intent": week_intent,
        "phases": [serialize_phase(phase) for phase in phases],
        "upcoming_events": [
            serialize_event(event)
            for event in events
            if event.event_date >= on_date
        ][:8],
        "warnings": warnings,
    }


def season_prompt_block(season: dict[str, Any] | None) -> str:
    if not season:
        return "SEASON PLAN: none — athlete has no A-race season generated yet."
    if not season.get("has_plan"):
        a = season.get("a_race") or {}
        return (
            "SEASON PLAN: A-race is set but no macro phases generated yet.\n"
            f"- A-race: {a.get('name')} on {a.get('date')} (target {a.get('target_metric') or '—'})\n"
            "- Generate the season plan to unlock Base/Build/Peak/Taper coaching."
        )

    phase = season.get("current_phase") or {}
    intent = season.get("week_intent") or {}
    lines = [
        "SEASON PLAN (macro periodization — hard limits on phase focus):",
        f"- A-race: {(season.get('a_race') or {}).get('name')} on {(season.get('a_race') or {}).get('date')}",
        f"- Current phase: {phase.get('phase_type', '—')} ({phase.get('intent', '')})",
        f"- Week in phase: {season.get('week_in_phase') or '—'}",
        f"- Volume bias: {intent.get('volume_bias')} | Intensity: {intent.get('intensity_bias')}",
        f"- Long session allowance: up to {intent.get('long_session_allowed_min')} min this phase",
    ]
    for note in intent.get("notes") or []:
        lines.append(f"- {note}")
    for event in intent.get("events") or []:
        lines.append(
            f"- Event this week: {event.get('priority')}-race {event.get('name')} on {event.get('date')}"
        )
    for warning in season.get("warnings") or []:
        lines.append(f"- ⚠ {warning}")
    feasibility = season.get("a_race_feasibility")
    if feasibility:
        lines.append(
            f"- A-race feasibility (from B-race): {feasibility.get('feasibility')} "
            f"(projected {feasibility.get('predicted_a_time') or '—'})"
        )
        if feasibility.get("peak_pace_note"):
            lines.append(f"- Peak pacing: {feasibility['peak_pace_note']}")
    return "\n".join(lines)


def apply_season_to_safety(safety: dict, season: dict[str, Any] | None) -> dict:
    """Raise long-session ceiling when phase allows (never lowers safety caps)."""
    if not season or not season.get("has_plan"):
        return safety
    intent = season.get("week_intent") or {}
    long_allowed = intent.get("long_session_allowed_min")
    if not long_allowed:
        return safety
    adjusted = dict(safety)
    adjusted["max_session_minutes"] = max(
        int(safety.get("max_session_minutes") or 0), int(long_allowed)
    )
    adjusted["season_phase"] = (season.get("current_phase") or {}).get("phase_type")
    adjusted["long_session_allowed_min"] = int(long_allowed)
    return adjusted
