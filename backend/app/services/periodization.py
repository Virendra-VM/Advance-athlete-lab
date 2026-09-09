"""Retrograde periodization from A-race backward through macro training blocks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteProfile, SeasonPhase, SeasonPlan
from app.services.b_race_calibration import calibrate_from_b_race
from app.services.season_baseline import (
    SHORT_RECOVERY_CYCLE_WEEKS,
    build_season_baseline,
    is_loading_phase,
    recovery_cycle_weeks,
    scale_long_session,
    scale_volume_bias,
)
from app.services.zone_recalibration import d_race_test_protocol

VALID_PRIORITIES = frozenset({"A", "B", "C", "D", "E"})
VALID_SPORTS = frozenset({"run", "bike", "swim", "strength", "other"})
MACRO_PHASES = ("base", "build", "peak", "taper")
PHASE_RATIOS = {"base": 0.40, "build": 0.30, "peak": 0.20, "taper": 0.10}

# Taper research converges on 8–21 days of reduced load; longer than that and
# fitness starts leaking away. Peak is similarly self-limiting — race-pace work
# cannot be held for months. Weeks beyond these caps go to base, where extra
# aerobic runway is worth the most.
TAPER_MAX_WEEKS = 3
PEAK_MAX_WEEKS = 6
# Base:build split for whatever is left after peak and taper are reserved,
# holding the 40:30 intent of PHASE_RATIOS.
BASE_SHARE_OF_REMAINDER = 4 / 7

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


def distribute_macro_weeks(
    total_weeks: int,
    *,
    short_season: bool = False,
    anchor_weeks: int | None = None,
) -> dict[str, int]:
    """Split ``total_weeks`` into base/build/peak/taper (sums to total_weeks).

    ``anchor_weeks`` is the length of the whole season when ``total_weeks`` only
    covers what is left of it. Peak and taper are anchored to the A-race, so a
    replan must keep them at their full-season length and take the missing weeks
    out of base and build. Sizing them from the remaining runway instead made
    peak shrink every time the plan was touched — backwards, since peak is the
    part closest to the race.
    """
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

    # Reserve the sharp end first. Taper and peak have hard physiological
    # ceilings, so they are sized before the remainder is split, and a long
    # runway grows base rather than stretching a taper past three weeks.
    anchor = max(anchor_weeks or total_weeks, total_weeks)
    taper = min(TAPER_MAX_WEEKS, max(1, int(anchor * PHASE_RATIOS["taper"] + 0.5)))
    peak = min(PEAK_MAX_WEEKS, max(1, int(anchor * PHASE_RATIOS["peak"])))

    # Whatever the anchor asked for still has to fit in the weeks on hand.
    taper = min(taper, total_weeks - 1)
    peak = min(peak, total_weeks - taper - 1)
    remainder = total_weeks - taper - peak

    base = int(remainder * BASE_SHARE_OF_REMAINDER + 0.5)
    build = remainder - base
    return {"base": base, "build": build, "peak": peak, "taper": taper}


def insert_recovery_weeks(blocks: list[PhaseBlock], every: int = 4) -> list[PhaseBlock]:
    """Turn the last week of every N-week base/build cycle into a recovery week.

    Two rules keep this honest. The recovery week is spent *from* the block's own
    budget rather than added on top, because adding weeks used to push the
    timeline past the A-race and silently squeeze peak and taper out of long
    seasons. And the cycle counter resets per block, so a short build block is
    never handed a recovery week it cannot afford — base and build are separate
    mesocycles, not one continuous run.
    """
    if every <= 1:
        return blocks

    expanded: list[PhaseBlock] = []
    for block in blocks:
        if block.phase_type not in ("base", "build") or block.week_count < every:
            expanded.append(block)
            continue
        for week in range(1, block.week_count + 1):
            if week % every == 0:
                expanded.append(PhaseBlock("recovery_week", 1))
            else:
                expanded.append(PhaseBlock(block.phase_type, 1))
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


def phase_payload(
    phase_type: str,
    start_date: date,
    end_date: date,
    *,
    sort_order: int,
    baseline: dict[str, Any] | None = None,
    week_count: int | None = None,
) -> dict[str, Any]:
    """One dated phase row with its limits scaled to the athlete's baseline.

    ``week_count`` counts calendar weeks touched, which is what an athlete reads
    off a Monday-aligned timeline. Phases that start mid-week — restore begins
    the day after the A-race — pass their true length instead, so a 14-day
    restore is not labelled three weeks.
    """
    defaults = PHASE_DEFAULTS.get(phase_type, PHASE_DEFAULTS["base"])
    return {
        "phase_type": phase_type,
        "start_date": start_date,
        "end_date": end_date,
        "week_count": week_count or weeks_between_inclusive(start_date, end_date),
        "intent": defaults["intent"],
        "volume_bias": scale_volume_bias(
            defaults["volume_bias"], baseline, loading=is_loading_phase(phase_type)
        ),
        "intensity_bias": defaults["intensity_bias"],
        "long_session_allowed_min": scale_long_session(
            defaults["long_session_allowed_min"], baseline
        ),
        "sort_order": sort_order,
    }


def blocks_to_dated_phases(
    blocks: list[PhaseBlock],
    season_start: date,
    a_race_date: date,
    *,
    baseline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Turn week blocks into dated phases, with the taper landing on race day.

    Race week always belongs to the taper. Blocks are laid out up to the Sunday
    before it, and a trailing taper block merges into race week so a planned
    two- or three-week taper stays contiguous instead of overlapping it.
    """
    race_week_start = monday_of(a_race_date)
    cursor = monday_of(season_start)
    phases: list[dict[str, Any]] = []
    sort_order = 0

    for block in blocks:
        if cursor >= race_week_start:
            break
        # Race week is reserved, so a block may only run to the Sunday before it.
        phase_end = min(
            add_weeks(cursor, block.week_count) - timedelta(days=1),
            race_week_start - timedelta(days=1),
        )
        if phase_end < cursor:
            break
        phases.append(
            phase_payload(
                block.phase_type, cursor, phase_end, sort_order=sort_order, baseline=baseline
            )
        )
        sort_order += 1
        cursor = monday_of(phase_end + timedelta(days=1))

    # A taper block that runs right up to race week is the same taper: extend it
    # rather than emitting two adjacent taper phases.
    if phases and phases[-1]["phase_type"] == "taper":
        merged = phases.pop()
        phases.append(
            phase_payload(
                "taper",
                merged["start_date"],
                a_race_date,
                sort_order=merged["sort_order"],
                baseline=baseline,
            )
        )
    else:
        phases.append(
            phase_payload(
                "taper",
                max(race_week_start, monday_of(season_start)),
                a_race_date,
                sort_order=sort_order,
                baseline=baseline,
            )
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


_SPORT_LABEL_TO_TYPE = {
    "running": "run",
    "run": "run",
    "cycling": "bike",
    "bike": "bike",
    "swimming": "swim",
    "swim": "swim",
    "strength": "strength",
}


def infer_sport_type(profile: AthleteProfile, db: Session | None = None) -> str:
    """Primary sport from AthleteSport rows, profile JSON, then goal-event text."""
    from app.services.athlete_profile import get_profile_sports, load_json_column

    if db is not None:
        sports = get_profile_sports(db, profile.id)
        if sports:
            primary = next(
                (row for row in sports if (row.priority or "").lower() != "secondary"),
                sports[0],
            )
            mapped = _SPORT_LABEL_TO_TYPE.get((primary.sport or "").strip().lower())
            if mapped:
                return mapped

    primary_json = load_json_column(profile.primary_sports)
    if isinstance(primary_json, list) and primary_json:
        label = str(primary_json[0]).strip().lower()
        mapped = _SPORT_LABEL_TO_TYPE.get(label)
        if mapped:
            return mapped

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
    sport = infer_sport_type(profile, db)
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


def _phase_adjustability(
    phases: list, index: int, *, today: date
) -> tuple[bool, bool]:
    """Whether this block can grow or shrink by one week without moving the A-race.

    Grow steals a spare week from a later block. Shrink hands a week to the next
    block. Restore is locked to the days after the race, finished blocks stay
    finished, and the last pre-race block cannot shrink or the A-race week
    would be uncovered.
    """
    if index < 0 or index >= len(phases):
        return False, False
    target = phases[index]
    phase_type = getattr(target, "phase_type", None) or target.get("phase_type")
    end = getattr(target, "end_date", None) or date.fromisoformat(str(target["end_date"]))
    weeks = int(getattr(target, "week_count", None) or target.get("week_count") or 0)
    if phase_type == "restore" or end < today:
        return False, False

    later = []
    for row in phases[index + 1 :]:
        later_type = getattr(row, "phase_type", None) or row.get("phase_type")
        if later_type == "restore":
            continue
        later.append(row)

    grow = any(
        int(getattr(row, "week_count", None) or row.get("week_count") or 0) > 1
        for row in later
    )
    shrink = bool(later) and weeks > 1 and end - timedelta(days=7) >= today
    return grow, shrink


REPLACEABLE_PHASE_TYPES = frozenset({"base", "build", "peak", "recovery_week"})
LOCKED_PHASE_TYPES = frozenset({"restore", "taper"})


def _phase_neighbor_after(phases: list, index: int):
    for row in phases[index + 1 :]:
        later_type = getattr(row, "phase_type", None) or row.get("phase_type")
        if later_type == "restore":
            break
        return row
    return None


def _phase_deletability(phases: list, index: int, *, today: date) -> bool:
    """Whether a single future week can be removed (merged into a neighbor)."""
    if index < 0 or index >= len(phases):
        return False
    target = phases[index]
    phase_type = getattr(target, "phase_type", None) or target.get("phase_type")
    end = getattr(target, "end_date", None) or date.fromisoformat(str(target["end_date"])[:10])
    weeks = int(getattr(target, "week_count", None) or target.get("week_count") or 0)
    if phase_type in LOCKED_PHASE_TYPES or end < today or index == 0 or weeks != 1:
        return False

    pred = phases[index - 1]
    pred_type = getattr(pred, "phase_type", None) or pred.get("phase_type")
    pred_end = getattr(pred, "end_date", None) or date.fromisoformat(str(pred["end_date"])[:10])
    if pred_type == "restore" or pred_end < today:
        return False

    return _phase_neighbor_after(phases, index) is not None


def _phase_replaceability(phases: list, index: int, *, today: date) -> bool:
    if index < 0 or index >= len(phases):
        return False
    target = phases[index]
    phase_type = getattr(target, "phase_type", None) or target.get("phase_type")
    end = getattr(target, "end_date", None) or date.fromisoformat(str(target["end_date"])[:10])
    return phase_type not in LOCKED_PHASE_TYPES and end >= today


def annotate_phase_adjustability(
    serialized: list[dict[str, Any]], *, today: date | None = None
) -> list[dict[str, Any]]:
    today = today or date.today()
    for index, row in enumerate(serialized):
        grow, shrink = _phase_adjustability(serialized, index, today=today)
        row["can_grow"] = grow
        row["can_shrink"] = shrink
        deletable = _phase_deletability(serialized, index, today=today)
        row["can_delete"] = deletable
        row["can_drag"] = (
            row.get("phase_type") == "recovery_week"
            and _phase_replaceability(serialized, index, today=today)
        )
        row["can_replace"] = _phase_replaceability(serialized, index, today=today)
    return serialized


def _find_week_donor(phases: list[SeasonPhase], target_index: int, need: int) -> int | None:
    for index in range(target_index + 1, len(phases)):
        row = phases[index]
        if row.phase_type == "restore":
            continue
        if row.week_count - need >= 1:
            return index
    return None


def _assert_phases_contiguous(phases: list[SeasonPhase]) -> None:
    for prev, nxt in zip(phases, phases[1:]):
        if nxt.start_date != prev.end_date + timedelta(days=1):
            raise ValueError(
                "Those dates would leave a gap or overlap. The A-race week has to stay covered."
            )


def adjust_phase_weeks(
    db: Session,
    profile: AthleteProfile,
    phase_id: int,
    delta_weeks: int,
    *,
    today: date | None = None,
) -> SeasonPlan:
    """Move one week (or two) between this phase and a later one.

    The A-race date and Restore stay put. The athlete is trading weeks inside
    the existing runway, not rewriting the engine's ratios.
    """
    today = today or date.today()
    if delta_weeks == 0:
        raise ValueError("Pick a longer or shorter block — zero weeks changes nothing.")
    if abs(delta_weeks) > 2:
        raise ValueError("Move at most two weeks at a time so the rest of the season stays honest.")

    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        raise ValueError("No active season plan to edit.")

    phases = get_phases_for_plan(db, plan.id)
    index = next((i for i, row in enumerate(phases) if row.id == phase_id), None)
    if index is None:
        raise ValueError("That phase is not on the active season.")

    target = phases[index]
    grow, shrink = _phase_adjustability(phases, index, today=today)
    if delta_weeks > 0 and not grow:
        raise ValueError(
            "No later block has a spare week. Peak and taper have to keep at least one week each."
        )
    if delta_weeks < 0 and not shrink:
        raise ValueError(
            "This block cannot get shorter. Finished weeks stay, restore is fixed, "
            "and the last block before the A-race has to cover race week."
        )

    days = 7 * delta_weeks
    if delta_weeks > 0:
        donor_index = _find_week_donor(phases, index, delta_weeks)
        if donor_index is None:
            raise ValueError("No later block has a spare week to give.")
        donor = phases[donor_index]
        target.end_date = target.end_date + timedelta(days=days)
        target.week_count = target.week_count + delta_weeks
        for mid in phases[index + 1 : donor_index]:
            mid.start_date = mid.start_date + timedelta(days=days)
            mid.end_date = mid.end_date + timedelta(days=days)
        donor.start_date = donor.start_date + timedelta(days=days)
        donor.week_count = donor.week_count - delta_weeks
    else:
        recipient = phases[index + 1]
        target.end_date = target.end_date + timedelta(days=days)
        target.week_count = target.week_count + delta_weeks
        recipient.start_date = recipient.start_date + timedelta(days=days)
        recipient.week_count = recipient.week_count - delta_weeks

    for row in phases:
        if row.phase_type != "restore":
            row.week_count = weeks_between_inclusive(row.start_date, row.end_date)

    _assert_phases_contiguous(phases)
    db.flush()
    return plan


def shift_recovery_phase_to_week(
    db: Session,
    profile: AthleteProfile,
    phase_id: int,
    target_week_start: date,
    *,
    today: date | None = None,
) -> SeasonPlan:
    """Place a recovery week on a specific calendar Monday.

    The A-race date stays fixed. Weeks trade between the block before recovery
    and the block after it — the same total runway, just slid earlier or later.
    """
    today = today or date.today()
    target = monday_of(target_week_start)
    if target.weekday() != 0:
        raise ValueError("Pick the Monday that recovery week should start on.")

    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        raise ValueError("No active season plan to edit.")

    phases = get_phases_for_plan(db, plan.id)
    index = next((i for i, row in enumerate(phases) if row.id == phase_id), None)
    if index is None:
        raise ValueError("That phase is not on the active season.")

    recovery = phases[index]
    if recovery.phase_type != "recovery_week":
        raise ValueError("Only recovery weeks can be placed on a calendar week.")
    if recovery.end_date < today:
        raise ValueError("That recovery week has already passed.")
    if index == 0:
        raise ValueError("This recovery week has no earlier block to trade with.")

    delta_weeks = (target - monday_of(recovery.start_date)).days // 7
    if delta_weeks == 0:
        return plan
    if abs(delta_weeks) > 8:
        raise ValueError("Move recovery at most eight weeks at a time.")

    pred = phases[index - 1]
    if pred.phase_type == "restore" or pred.end_date < today:
        raise ValueError("The block before recovery cannot move.")

    succ = None
    for row in phases[index + 1 :]:
        if row.phase_type == "restore":
            break
        succ = row
        break
    if succ is None:
        raise ValueError("There is no block after recovery to trade weeks with.")

    n = abs(delta_weeks)
    succ_end_anchor = succ.end_date
    if delta_weeks < 0:
        if pred.week_count <= n:
            raise ValueError(
                "Not enough weeks in the block before recovery to move it earlier."
            )
        pred.end_date = pred.end_date - timedelta(days=7 * n)
        pred.week_count = pred.week_count - n
        recovery.start_date = pred.end_date + timedelta(days=1)
        recovery.end_date = recovery.start_date + timedelta(days=6)
        succ.start_date = recovery.end_date + timedelta(days=1)
        succ.week_count = succ.week_count + n
        succ.end_date = succ_end_anchor
    else:
        if succ.week_count <= n:
            raise ValueError(
                "Not enough weeks in the block after recovery to move it later."
            )
        pred.week_count = pred.week_count + n
        pred.end_date = pred.end_date + timedelta(days=7 * n)
        recovery.start_date = pred.end_date + timedelta(days=1)
        recovery.end_date = recovery.start_date + timedelta(days=6)
        succ.start_date = recovery.end_date + timedelta(days=1)
        succ.week_count = succ.week_count - n
        succ.end_date = succ_end_anchor

    for row in phases:
        if row.phase_type != "restore":
            row.week_count = weeks_between_inclusive(row.start_date, row.end_date)

    _assert_phases_contiguous(phases)

    db.flush()
    return plan


def replace_season_phase(
    db: Session,
    profile: AthleteProfile,
    phase_id: int,
    new_phase_type: str,
    *,
    today: date | None = None,
) -> SeasonPlan:
    """Swap a block's macro type while keeping its dates and week count."""
    today = today or date.today()
    new_phase_type = (new_phase_type or "").strip().lower()
    if new_phase_type not in REPLACEABLE_PHASE_TYPES:
        raise ValueError("Pick base, build, peak, or recovery week.")

    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        raise ValueError("No active season plan to edit.")

    phases = get_phases_for_plan(db, plan.id)
    index = next((i for i, row in enumerate(phases) if row.id == phase_id), None)
    if index is None:
        raise ValueError("That phase is not on the active season.")

    if not _phase_replaceability(phases, index, today=today):
        raise ValueError("Taper, restore, and finished blocks cannot be replaced.")

    target = phases[index]
    if target.phase_type == new_phase_type:
        return plan

    defaults = phase_defaults_for_type(new_phase_type)
    target.phase_type = new_phase_type
    target.intent = defaults["intent"]
    target.volume_bias = defaults["volume_bias"]
    target.intensity_bias = defaults["intensity_bias"]
    db.flush()
    return plan


def delete_season_phase(
    db: Session,
    profile: AthleteProfile,
    phase_id: int,
    *,
    merge_into: str = "next",
    today: date | None = None,
) -> SeasonPlan:
    """Remove a single future week and merge its calendar span into a neighbor block."""
    today = today or date.today()
    if merge_into not in {"prev", "next"}:
        raise ValueError("merge_into must be 'prev' or 'next'.")

    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        raise ValueError("No active season plan to edit.")

    phases = get_phases_for_plan(db, plan.id)
    index = next((i for i, row in enumerate(phases) if row.id == phase_id), None)
    if index is None:
        raise ValueError("That phase is not on the active season.")

    if not _phase_deletability(phases, index, today=today):
        raise ValueError(
            "Only a single future week can be removed. Taper, restore, multi-week blocks, "
            "and finished weeks stay fixed — shorten multi-week blocks first, or replace the block type."
        )

    recovery = phases[index]
    pred = phases[index - 1]
    succ = _phase_neighbor_after(phases, index)
    if succ is None:
        raise ValueError("There is no block after this week to merge into.")

    if merge_into == "next":
        succ.start_date = recovery.start_date
        succ.week_count = weeks_between_inclusive(succ.start_date, succ.end_date)
    else:
        pred.end_date = recovery.end_date
        pred.week_count = weeks_between_inclusive(pred.start_date, pred.end_date)
        succ.start_date = pred.end_date + timedelta(days=1)

    db.delete(recovery)
    remaining = [row for row in phases if row.id != phase_id]
    for sort_order, row in enumerate(remaining):
        row.sort_order = sort_order

    _assert_phases_contiguous(remaining)
    db.flush()
    return plan


def build_phase_blocks(
    profile: AthleteProfile,
    season_start: date,
    a_race_date: date,
    *,
    baseline: dict[str, Any] | None = None,
    season_weeks: int | None = None,
) -> list[dict[str, Any]]:
    """Pure phase timeline ending with the taper on A-race day.

    ``baseline`` is the athlete's carrying capacity from
    :mod:`app.services.season_baseline`. Omit it and the plan falls back to the
    phase defaults, which is what the pure unit tests exercise.

    ``season_weeks`` is the length of the *whole* build-up. A replan only rebuilds
    the runway that is left, and post-race recovery should reflect the training
    that earned it rather than shrinking every time the plan is touched.
    """
    # Race week belongs to the taper, so budget over the whole span including it.
    total_weeks = max(weeks_between_inclusive(season_start, a_race_date), 1)
    short = total_weeks <= 7 or (profile.fitness_level or "").lower().startswith("beginner")
    counts = distribute_macro_weeks(
        total_weeks, short_season=short, anchor_weeks=season_weeks
    )

    blocks: list[PhaseBlock] = []
    for phase_type in MACRO_PHASES:
        weeks = counts[phase_type]
        # blocks_to_dated_phases always owns race week for the taper, so only the
        # taper weeks *before* race week are laid out here.
        if phase_type == "taper":
            weeks -= 1
        if weeks > 0:
            blocks.append(PhaseBlock(phase_type, weeks))

    blocks = insert_recovery_weeks(blocks, every=recovery_cycle_weeks(baseline))
    blocks = collapse_blocks(blocks)
    phases = blocks_to_dated_phases(blocks, season_start, a_race_date, baseline=baseline)

    restore_start = a_race_date + timedelta(days=1)
    restore_weeks = restore_weeks_for_season(season_weeks or total_weeks)
    restore_end = restore_start + timedelta(days=7 * restore_weeks - 1)
    phases.append(
        phase_payload(
            "restore",
            restore_start,
            restore_end,
            sort_order=len(phases),
            baseline=baseline,
            week_count=restore_weeks,
        )
    )
    return phases


LONG_SEASON_WEEKS = 20


def restore_weeks_for_season(total_weeks: int) -> int:
    """A long build-up earns a longer reset — a marathon block is not a 5k block."""
    return 2 if total_weeks >= LONG_SEASON_WEEKS else 1


def _compute_season_phase_payloads(
    db: Session,
    profile: AthleteProfile,
    *,
    today: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[AthleteEvent], AthleteEvent, list[dict[str, Any]]]:
    """Shared dry-run inputs for preview and generate — no DB writes."""
    today = today or date.today()
    a_race = sync_a_race_from_profile(db, profile)
    if a_race is None:
        raise ValueError("No A-race configured. Set a goal event on your profile first.")
    if a_race.event_date <= today:
        raise ValueError("A-race date must be in the future to generate a season plan.")

    events = list_planned_events(db, profile.id)
    warnings = validate_events(events, a_race)
    from app.services.planning_notes import parse_planning_notes

    note_parse = parse_planning_notes(profile.planning_notes)
    for warning in note_parse["warnings"]:
        if warning not in warnings:
            warnings.append(warning)

    from app.services.season_replan import _build_future_payloads, _collect_raw_triggers

    baseline = build_season_baseline(db, profile, as_of=today)
    note_flags = set(note_parse.get("flags") or [])
    if note_flags & {"travel", "limited_time"}:
        baseline["volume_damp"] = round(min(float(baseline.get("volume_damp") or 1.0), 0.85), 2)
        baseline["notes"].append(
            "Planning notes mention travel or limited time — volume held slightly below phase targets."
        )
    if "recovery_requested" in note_flags:
        baseline["recovery_cycle_weeks"] = min(
            int(baseline.get("recovery_cycle_weeks") or 4), SHORT_RECOVERY_CYCLE_WEEKS
        )
        baseline["notes"].append(
            "Planning notes request recovery — shorter loading cycles are applied."
        )
    context_triggers = _collect_raw_triggers(
        db, profile, as_of=today, new_bc_race=False, plan=None
    )
    if context_triggers:
        phase_payloads = _build_future_payloads(
            profile,
            events,
            as_of=today,
            a_race_date=a_race.event_date,
            triggers=context_triggers,
            past_phase_count=0,
            baseline=baseline,
        )
    else:
        phase_payloads = build_phase_blocks(
            profile, today, a_race.event_date, baseline=baseline
        )
    return phase_payloads, baseline, warnings, events, a_race, context_triggers


def preview_season_plan(
    db: Session,
    profile: AthleteProfile,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Return everything the athlete should review before committing a season plan."""
    today = today or date.today()
    (
        phase_payloads,
        baseline,
        warnings,
        events,
        a_race,
        context_triggers,
    ) = _compute_season_phase_payloads(db, profile, today=today)

    from app.models import StravaConnection
    from app.services.athlete_profile import get_profile_injuries
    from app.services.coros_sync import get_coros_connection
    from app.services.season_replan import detect_replan_triggers

    strava = (
        db.query(StravaConnection)
        .filter(StravaConnection.athlete_profile_id == profile.id)
        .order_by(StravaConnection.id.desc())
        .first()
    )
    coros = get_coros_connection(db, profile.id)
    injuries = get_profile_injuries(db, profile.id)
    active_injury_labels = [
        f"{row.body_region}{f' ({row.condition})' if row.condition else ''}"
        for row in injuries
        if row.status == "active"
    ]

    existing = get_active_season_plan(db, profile.id)
    triggers = detect_replan_triggers(db, profile, as_of=today, plan=existing)

    restore_end = phase_payloads[-1]["end_date"] if phase_payloads else a_race.event_date
    phase_sketch = [
        {
            "phase_type": payload["phase_type"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "week_count": payload["week_count"],
            "intent": payload.get("intent"),
            "volume_bias": payload.get("volume_bias"),
            "long_session_allowed_min": payload.get("long_session_allowed_min"),
        }
        for payload in phase_payloads
    ]

    return {
        "a_race": serialize_event(a_race),
        "events": [serialize_event(event) for event in events if event.status == "planned"],
        "profile": {
            "name": profile.name,
            "fitness_level": profile.fitness_level,
            "days_per_week": profile.days_per_week,
            "workout_duration_minutes": profile.workout_duration_minutes,
            "weekly_minutes_budget": profile.weekly_minutes_budget,
            "training_history_months": profile.training_history_months,
            "preferred_workout_time": profile.preferred_workout_time,
            "planning_notes": profile.planning_notes,
            "active_injuries": active_injury_labels or list(baseline.get("active_injuries") or []),
        },
        "connections": {
            "strava_connected": strava is not None and bool(strava.access_token),
            "coros_connected": coros is not None,
        },
        "baseline": baseline,
        "warnings": warnings,
        "triggers": triggers,
        "phase_sketch": phase_sketch,
        "total_weeks": weeks_between_inclusive(today, a_race.event_date),
        "season_start": today,
        "season_end": restore_end,
        "has_existing_plan": existing is not None,
    }


def generate_season_plan(
    db: Session,
    profile: AthleteProfile,
    *,
    today: date | None = None,
) -> SeasonPlan:
    """Build or rebuild the active season plan from A-race + events."""
    today = today or date.today()
    (
        phase_payloads,
        baseline,
        warnings,
        _events,
        a_race,
        _context_triggers,
    ) = _compute_season_phase_payloads(db, profile, today=today)

    for old in db.query(SeasonPlan).filter(
        SeasonPlan.athlete_profile_id == profile.id,
        SeasonPlan.status == "active",
    ):
        old.status = "archived"

    from app.services.season_replan import acknowledge_current_season_triggers

    restore_end = phase_payloads[-1]["end_date"] if phase_payloads else a_race.event_date

    plan = SeasonPlan(
        athlete_profile_id=profile.id,
        a_race_event_id=a_race.id,
        start_date=today,
        end_date=restore_end,
        status="active",
        template_key=f"{infer_sport_type(profile, db)}_{(profile.fitness_level or 'intermediate').lower()}",
        warnings_json=json.dumps(warnings),
    )
    db.add(plan)
    db.flush()

    for sort_order, payload in enumerate(phase_payloads):
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
                sort_order=payload.get("sort_order", sort_order),
            )
        )

    acknowledge_current_season_triggers(
        db,
        profile,
        plan,
        replan_note="Season rebuilt from template",
        as_of=today,
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
    baseline: dict[str, Any] | None = None,
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
        "long_session_allowed_min": scale_long_session(
            defaults["long_session_allowed_min"], baseline
        ),
        "notes": [],
        "events": [],
    }

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


def serialize_phase(
    phase: SeasonPhase, baseline: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase row for the API.

    The long-session allowance is derived on read rather than stored, so the
    ceiling tracks the athlete's current longest session instead of freezing at
    whatever they could do the day the plan was generated.
    """
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
        "long_session_allowed_min": scale_long_session(
            defaults["long_session_allowed_min"], baseline
        ),
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

    baseline = build_season_baseline(db, profile, as_of=on_date)
    week_start = monday_of(on_date)
    week_intent = get_week_intent(phases, events, week_start, profile, baseline)

    warnings: list[str] = []
    if plan.warnings_json:
        try:
            loaded = json.loads(plan.warnings_json)
            if isinstance(loaded, list):
                warnings = [
                    str(item)
                    for item in loaded
                    if not str(item).startswith("__REPLAN_META__:")
                ]
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

    serialized_phases = annotate_phase_adjustability(
        [serialize_phase(phase, baseline) for phase in phases],
        today=on_date,
    )
    current_payload = serialize_phase(current, baseline) if current else None
    if current_payload:
        match = next(
            (row for row in serialized_phases if row["id"] == current_payload["id"]),
            None,
        )
        if match:
            current_payload["can_grow"] = match["can_grow"]
            current_payload["can_shrink"] = match["can_shrink"]
            current_payload["can_delete"] = match["can_delete"]
            current_payload["can_drag"] = match["can_drag"]
            current_payload["can_replace"] = match["can_replace"]

    return {
        "has_plan": True,
        "plan_id": plan.id,
        "start_date": plan.start_date.isoformat(),
        "end_date": plan.end_date.isoformat(),
        "a_race": serialize_event(a_race) if a_race else None,
        "a_race_feasibility": a_race_feasibility,
        "current_phase": current_payload,
        "week_in_phase": week_in_phase,
        "week_intent": week_intent,
        "phases": serialized_phases,
        "week_outline": build_week_outline(phases, events, on_date=on_date),
        "baseline": baseline,
        "upcoming_events": [
            serialize_event(event)
            for event in events
            if event.event_date >= on_date
        ][:8],
        "warnings": warnings,
    }


MAX_OUTLINE_WEEKS = 60


def build_week_outline(
    phases: list[SeasonPhase],
    events: list[AthleteEvent],
    *,
    on_date: date,
) -> list[dict[str, Any]]:
    """One row per calendar week of the season, for the week-by-week strip.

    Derived from the stored phases rather than recomputed, so the strip can never
    disagree with the macro timeline it sits under.
    """
    if not phases:
        return []

    first_monday = monday_of(min(phase.start_date for phase in phases))
    last_end = max(phase.end_date for phase in phases)
    current_monday = monday_of(on_date)

    events_by_week: dict[date, list[dict[str, Any]]] = {}
    for event in events:
        if event.status != "planned":
            continue
        events_by_week.setdefault(monday_of(event.event_date), []).append(
            {
                "name": event.name,
                "date": event.event_date.isoformat(),
                "priority": event.priority,
            }
        )

    rows: list[dict[str, Any]] = []
    cursor = first_monday
    index = 0
    while cursor <= last_end and index < MAX_OUTLINE_WEEKS:
        week_end = cursor + timedelta(days=6)
        phase = next(
            (
                row
                for row in phases
                if row.start_date <= week_end and row.end_date >= cursor
            ),
            None,
        )
        if phase is None:
            cursor += timedelta(days=7)
            index += 1
            continue
        rows.append(
            {
                "week_start": cursor.isoformat(),
                "week_number": index + 1,
                "phase_type": phase.phase_type,
                "phase_id": phase.id,
                "week_in_phase": weeks_between_inclusive(phase.start_date, week_end),
                "volume_bias": phase.volume_bias,
                "intensity_bias": phase.intensity_bias,
                "is_current": cursor == current_monday,
                "is_past": week_end < on_date,
                "events": events_by_week.get(cursor, []),
            }
        )
        cursor += timedelta(days=7)
        index += 1
    return rows


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
    baseline = season.get("baseline") or {}
    if baseline.get("notes"):
        lines.append("- Why these numbers (quote these, do not invent others):")
        for note in baseline["notes"]:
            lines.append(f"  · {note}")
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
