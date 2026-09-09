"""Dynamic season replan when training reality diverges from the macro plan."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteInjury, AthleteProfile, PlannedWorkout, SeasonPhase, SeasonPlan, TrainingPlan
from app.services.periodization import (
    build_phase_blocks,
    get_active_season_plan,
    get_phases_for_plan,
    list_planned_events,
    monday_of,
    phase_payload,
    serialize_phase,
    sync_a_race_from_profile,
    validate_events,
    weeks_between_inclusive,
)
from app.services.season_baseline import build_season_baseline
from app.services.training_load import _round_load, _sum_session_load

REPLAN_META_PREFIX = "__REPLAN_META__:"
REPLAN_ACK_DAYS = 7

HARD_SESSION_TYPES = {"intervals", "vo2", "threshold", "tempo", "race", "hills", "speed", "hard"}


def _week_start(value: date) -> date:
    return monday_of(value)


def _serialize_phases(
    phases: list[SeasonPhase], baseline: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    return [serialize_phase(phase, baseline) for phase in phases]


def _parse_warnings(plan: SeasonPlan | None) -> tuple[list[str], dict[str, Any] | None]:
    if plan is None or not plan.warnings_json:
        return [], None
    try:
        payload = json.loads(plan.warnings_json)
    except json.JSONDecodeError:
        return [], None

    if isinstance(payload, dict):
        warnings = [str(item) for item in payload.get("warnings") or []]
        meta = payload.get("replan")
        return warnings, meta if isinstance(meta, dict) else None

    if not isinstance(payload, list):
        return [], None

    warnings: list[str] = []
    meta: dict[str, Any] | None = None
    for item in payload:
        text = str(item)
        if text.startswith(REPLAN_META_PREFIX):
            try:
                meta = json.loads(text[len(REPLAN_META_PREFIX) :])
            except json.JSONDecodeError:
                continue
            continue
        warnings.append(text)
    return warnings, meta


def _load_replan_meta(plan: SeasonPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None

    warnings, warning_meta = _parse_warnings(plan)
    column_meta: dict[str, Any] | None = None
    if plan.last_replan_at is not None:
        codes: list[str] = []
        ack_until: str | None = None
        if plan.last_replan_triggers_json:
            try:
                payload = json.loads(plan.last_replan_triggers_json)
                if isinstance(payload, list):
                    codes = payload
                elif isinstance(payload, dict):
                    codes = list(payload.get("codes") or [])
                    ack_until = payload.get("ack_until")
            except json.JSONDecodeError:
                codes = []
        column_meta = {
            "at": plan.last_replan_at.isoformat(),
            "codes": codes,
            "ack_until": ack_until,
        }

    if column_meta and warning_meta:
        # Prefer the most recent acknowledgment.
        try:
            column_at = datetime.fromisoformat(str(column_meta.get("at")))
            warning_at = datetime.fromisoformat(str(warning_meta.get("at")))
            return column_meta if column_at >= warning_at else warning_meta
        except ValueError:
            return column_meta
    return column_meta or warning_meta


def _save_replan_meta(
    plan: SeasonPlan,
    *,
    codes: list[str],
    replanned_at: datetime,
    as_of: date,
    replan_note: str,
) -> list[str]:
    ack_until = (as_of + timedelta(days=REPLAN_ACK_DAYS)).isoformat()
    meta = {
        "at": replanned_at.isoformat(),
        "codes": codes,
        "ack_until": ack_until,
    }
    warnings, _old_meta = _parse_warnings(plan)
    warnings = [line for line in warnings if not line.startswith("Replanned on")]
    warnings.append(f"Replanned on {as_of.isoformat()}: {replan_note}")
    warnings.append(REPLAN_META_PREFIX + json.dumps(meta))

    plan.last_replan_at = replanned_at
    plan.last_replan_triggers_json = json.dumps({"codes": codes, "ack_until": ack_until})
    plan.warnings_json = json.dumps(warnings)
    plan.updated_at = replanned_at
    return warnings


def _meta_replanned_at(meta: dict[str, Any] | None) -> datetime | None:
    if not meta or not meta.get("at"):
        return None
    try:
        return datetime.fromisoformat(str(meta["at"]))
    except ValueError:
        return None


def _meta_ack_until(meta: dict[str, Any] | None, as_of: date) -> date | None:
    if not meta:
        return None
    raw = meta.get("ack_until")
    if raw:
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            pass
    replanned_at = _meta_replanned_at(meta)
    if replanned_at is None:
        return None
    return replanned_at.date() + timedelta(days=REPLAN_ACK_DAYS)


def _meta_codes(meta: dict[str, Any] | None) -> set[str]:
    if not meta:
        return set()
    return {str(code) for code in meta.get("codes") or []}


def count_missed_key_sessions(
    db: Session,
    athlete_profile_id: int,
    *,
    week_start: date,
    week_end: date,
    as_of: date | None = None,
) -> int:
    as_of = as_of or date.today()
    rows = (
        db.query(PlannedWorkout)
        .join(TrainingPlan, PlannedWorkout.training_plan_id == TrainingPlan.id)
        .filter(
            PlannedWorkout.athlete_profile_id == athlete_profile_id,
            PlannedWorkout.workout_date >= week_start,
            PlannedWorkout.workout_date <= min(week_end, as_of),
            TrainingPlan.status == "active",
        )
        .all()
    )
    missed = 0
    for row in rows:
        session_type = (row.session_type or "").lower()
        if session_type not in HARD_SESSION_TYPES:
            continue
        if row.workout_date >= as_of:
            continue
        if row.completed_activity_id is None:
            missed += 1
    return missed


def has_active_injury(db: Session, athlete_profile_id: int) -> bool:
    return (
        db.query(AthleteInjury)
        .filter(
            AthleteInjury.athlete_profile_id == athlete_profile_id,
            AthleteInjury.status == "active",
        )
        .count()
        > 0
    )


def _load_acwr_for_window(
    db: Session,
    athlete_profile_id: int,
    *,
    end: datetime,
) -> float | None:
    seven_days_ago = end - timedelta(days=7)
    twenty_eight_days_ago = end - timedelta(days=28)
    acute_load = _sum_session_load(db, athlete_profile_id, seven_days_ago, end)
    total_28d_load = _sum_session_load(db, athlete_profile_id, twenty_eight_days_ago, end)
    chronic_load = _round_load(total_28d_load / 4.0)
    if chronic_load <= 0:
        return None
    return round(acute_load / chronic_load, 2)


def consecutive_caution_acwr_weeks(
    db: Session,
    athlete_profile_id: int,
    *,
    as_of: date | None = None,
) -> int:
    as_of = as_of or date.today()
    end = datetime.combine(as_of, datetime.max.time())
    caution_weeks = 0
    for offset in range(2):
        anchor = end - timedelta(days=offset * 7)
        acwr = _load_acwr_for_window(db, athlete_profile_id, end=anchor)
        if isinstance(acwr, (int, float)) and acwr >= 1.3:
            caution_weeks += 1
        else:
            break
    return caution_weeks


def _collect_raw_triggers(
    db: Session,
    profile: AthleteProfile,
    *,
    as_of: date,
    new_bc_race: bool,
    plan: SeasonPlan | None,
) -> list[dict[str, Any]]:
    triggers: list[dict[str, Any]] = []

    week_start = _week_start(as_of)
    week_end = week_start + timedelta(days=6)
    missed = count_missed_key_sessions(
        db, profile.id, week_start=week_start, week_end=week_end, as_of=as_of
    )
    if missed >= 2:
        triggers.append(
            {
                "code": "missed_key_sessions",
                "message": f"{missed} key sessions missed this week.",
                "severity": "warn",
            }
        )

    if new_bc_race:
        triggers.append(
            {
                "code": "new_bc_race",
                "message": "New B/C race added — remaining phases should be rebalanced.",
                "severity": "info",
            }
        )
    elif plan is not None:
        recent_bc = (
            db.query(AthleteEvent)
            .filter(
                AthleteEvent.athlete_profile_id == profile.id,
                AthleteEvent.priority.in_(["B", "C"]),
                AthleteEvent.status == "planned",
                AthleteEvent.created_at >= datetime.utcnow() - timedelta(days=7),
            )
            .count()
        )
        if recent_bc > 0:
            triggers.append(
                {
                    "code": "new_bc_race",
                    "message": "New B/C race added in the last week — consider replanning remaining phases.",
                    "severity": "info",
                }
            )

    if has_active_injury(db, profile.id):
        triggers.append(
            {
                "code": "active_injury",
                "message": "Active injury on file — shift toward recovery and absorb phases.",
                "severity": "warn",
            }
        )

    if consecutive_caution_acwr_weeks(db, profile.id, as_of=as_of) >= 2:
        triggers.append(
            {
                "code": "sustained_high_acwr",
                "message": "ACWR in caution zone for two consecutive weeks.",
                "severity": "warn",
            }
        )

    return triggers


def _trigger_escalated_after_replan(
    db: Session,
    profile: AthleteProfile,
    code: str,
    *,
    as_of: date,
    replanned_at: datetime,
    addressed_codes: set[str],
) -> bool:
    """Return True when a previously-addressed trigger should fire again."""
    if code not in addressed_codes:
        return True

    if code == "new_bc_race":
        newer = (
            db.query(AthleteEvent)
            .filter(
                AthleteEvent.athlete_profile_id == profile.id,
                AthleteEvent.priority.in_(["B", "C"]),
                AthleteEvent.status == "planned",
                AthleteEvent.created_at > replanned_at,
            )
            .count()
        )
        return newer > 0

    if code == "missed_key_sessions":
        return monday_of(replanned_at.date()) < monday_of(as_of)

    if code == "active_injury":
        injury = (
            db.query(AthleteInjury)
            .filter(
                AthleteInjury.athlete_profile_id == profile.id,
                AthleteInjury.status == "active",
            )
            .order_by(AthleteInjury.updated_at.desc())
            .first()
        )
        if injury is None:
            return False
        if injury.updated_at and injury.updated_at > replanned_at:
            return True
        if injury.created_at and injury.created_at > replanned_at:
            return True
        return False

    if code == "sustained_high_acwr":
        return (as_of - replanned_at.date()).days >= REPLAN_ACK_DAYS

    return (as_of - replanned_at.date()).days >= REPLAN_ACK_DAYS


def acknowledge_season_triggers(
    plan: SeasonPlan,
    *,
    codes: list[str],
    replan_note: str,
    as_of: date | None = None,
) -> list[str]:
    """Record that current replan triggers were addressed on this plan."""
    as_of = as_of or date.today()
    replanned_at = datetime.utcnow()
    return _save_replan_meta(
        plan,
        codes=codes,
        replanned_at=replanned_at,
        as_of=as_of,
        replan_note=replan_note,
    )


def acknowledge_current_season_triggers(
    db: Session,
    profile: AthleteProfile,
    plan: SeasonPlan,
    *,
    replan_note: str,
    as_of: date | None = None,
) -> list[str]:
    """Acknowledge whatever replan triggers apply right now."""
    as_of = as_of or date.today()
    codes = [
        trigger["code"]
        for trigger in _collect_raw_triggers(
            db, profile, as_of=as_of, new_bc_race=False, plan=plan
        )
    ]
    return acknowledge_season_triggers(
        plan, codes=codes, replan_note=replan_note, as_of=as_of
    )


def detect_replan_triggers(
    db: Session,
    profile: AthleteProfile,
    *,
    as_of: date | None = None,
    new_bc_race: bool = False,
    plan: SeasonPlan | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or date.today()
    plan = plan or get_active_season_plan(db, profile.id)
    raw = _collect_raw_triggers(db, profile, as_of=as_of, new_bc_race=new_bc_race, plan=plan)
    if not raw:
        return []

    meta = _load_replan_meta(plan)
    if meta is None:
        return raw

    ack_until = _meta_ack_until(meta, as_of)
    if ack_until is not None and as_of <= ack_until:
        replanned_at = _meta_replanned_at(meta)
        addressed = _meta_codes(meta)
        if replanned_at is None:
            return raw
        return [
            trigger
            for trigger in raw
            if _trigger_escalated_after_replan(
                db,
                profile,
                trigger["code"],
                as_of=as_of,
                replanned_at=replanned_at,
                addressed_codes=addressed,
            )
        ]

    return raw


def _occurrence_keys(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Label repeated phase types so the Nth base block pairs with the Nth base block."""
    seen: dict[str, int] = {}
    keys: list[tuple[str, int]] = []
    for row in rows:
        phase_type = row["phase_type"]
        seen[phase_type] = seen.get(phase_type, 0) + 1
        keys.append((phase_type, seen[phase_type]))
    return keys


def _diff_row(
    phase_type: str,
    occurrence: int,
    change: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "phase_type": phase_type,
        "occurrence": occurrence,
        "change": change,
    }
    if before is not None:
        row["before"] = f"{before['start_date']} → {before['end_date']}"
        row["before_start"] = before["start_date"]
        row["before_end"] = before["end_date"]
        row["before_volume_bias"] = before.get("volume_bias")
    if after is not None:
        row["after"] = f"{after['start_date']} → {after['end_date']}"
        row["after_start"] = after["start_date"]
        row["after_end"] = after["end_date"]
        row["after_volume_bias"] = after.get("volume_bias")
    if before is not None and after is not None:
        shift = (
            date.fromisoformat(after["start_date"]) - date.fromisoformat(before["start_date"])
        ).days
        row["shift_days"] = shift
    return row


def _phase_diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Before/after per phase block.

    A real season repeats base, build and recovery_week several times, so blocks
    are paired by (phase type, occurrence). Keying on phase type alone compared
    the first base block against the last one and reported changes that were not
    there.
    """
    before_by_key = dict(zip(_occurrence_keys(before), before))
    after_by_key = dict(zip(_occurrence_keys(after), after))

    diff: list[dict[str, Any]] = []
    for key, row in before_by_key.items():
        phase_type, occurrence = key
        replacement = after_by_key.get(key)
        if replacement is None:
            diff.append(_diff_row(phase_type, occurrence, "removed", row, None))
            continue
        changed = (
            (row["start_date"], row["end_date"])
            != (replacement["start_date"], replacement["end_date"])
            or row.get("intent") != replacement.get("intent")
            or row.get("volume_bias") != replacement.get("volume_bias")
        )
        if changed:
            diff.append(_diff_row(phase_type, occurrence, "shifted", row, replacement))
    for key, row in after_by_key.items():
        if key not in before_by_key:
            diff.append(_diff_row(key[0], key[1], "added", None, row))
    return diff


PHASE_LABELS = {
    "base": "Base",
    "build": "Build",
    "peak": "Peak",
    "taper": "Taper",
    "recovery_week": "Recovery weeks",
    "restore": "Restore",
}
SUMMARY_PHASE_ORDER = ("base", "build", "peak", "taper", "recovery_week")


def _span_weeks(row: dict[str, Any]) -> int:
    start = date.fromisoformat(row["start_date"])
    end = date.fromisoformat(row["end_date"])
    return max(1, (end - start).days // 7 + 1)


def _weeks_by_type(rows: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        totals[row["phase_type"]] = totals.get(row["phase_type"], 0) + _span_weeks(row)
    return totals


def _first_start(rows: list[dict[str, Any]], phase_type: str) -> str | None:
    starts = [row["start_date"] for row in rows if row["phase_type"] == phase_type]
    return min(starts) if starts else None


def _replan_summary(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[str]:
    """What the replan actually changed, in the terms an athlete cares about.

    The block-level diff is exact but unreadable: re-laying out a season moves
    every recovery week, so a one-week change reports as a dozen shifts. This
    rolls those up into phase totals and the boundary dates that matter.
    """
    before_weeks = _weeks_by_type(before)
    after_weeks = _weeks_by_type(after)

    lines: list[str] = []
    for phase_type in SUMMARY_PHASE_ORDER:
        was = before_weeks.get(phase_type, 0)
        now = after_weeks.get(phase_type, 0)
        if was == now:
            continue
        delta = abs(now - was)
        unit = "week" if delta == 1 else "weeks"
        lines.append(
            f"{PHASE_LABELS[phase_type]}: {was} → {now} weeks "
            f"({delta} {unit} {'more' if now > was else 'less'})"
        )

    for phase_type in ("build", "peak", "taper"):
        was = _first_start(before, phase_type)
        now = _first_start(after, phase_type)
        if not was or not now or was == now:
            continue
        shift = (date.fromisoformat(now) - date.fromisoformat(was)).days
        lines.append(
            f"{PHASE_LABELS[phase_type]} now starts {now} — "
            f"{abs(shift)} days {'later' if shift > 0 else 'earlier'}."
        )

    if not lines:
        lines.append(
            "Phase lengths and start dates are unchanged — only the week-by-week "
            "detail inside them moved."
        )
    return lines


def _build_future_payloads(
    profile: AthleteProfile,
    events: list[AthleteEvent],
    *,
    as_of: date,
    a_race_date: date,
    triggers: list[dict[str, Any]],
    past_phase_count: int,
    baseline: dict[str, Any] | None = None,
    season_start: date | None = None,
) -> list[dict[str, Any]]:
    remaining_weeks = weeks_between_inclusive(as_of, a_race_date)
    season_weeks = weeks_between_inclusive(season_start or as_of, a_race_date)
    extra_recovery = any(
        trigger["code"] in {"missed_key_sessions", "active_injury", "sustained_high_acwr"}
        for trigger in triggers
    )
    has_bc_trigger = any(trigger["code"] == "new_bc_race" for trigger in triggers)

    if extra_recovery and remaining_weeks >= 3:
        # An athlete who is hurt, spiking load, or missing key sessions needs a
        # down week now. Spend it out of the remaining runway and re-run the
        # engine over what is left, so the A-race stays fixed and every phase
        # after it is rebuilt to fit. The previous approach shifted the old
        # phases forward by seven days, which left recovery weeks overlapping
        # their neighbours, a gap where the shift started, a taper that landed
        # after the A-race, and no restore phase at all.
        recovery_start = as_of
        # Snap to the nearest Monday so the rebuilt phases stay week-aligned;
        # that keeps the down block in the 4–10 day range whatever day it is.
        rebuild_start = monday_of(as_of + timedelta(days=10))
        future_payloads = [
            phase_payload(
                "recovery_week",
                recovery_start,
                rebuild_start - timedelta(days=1),
                sort_order=past_phase_count,
                baseline=baseline,
                week_count=1,
            ),
            *build_phase_blocks(
                profile,
                rebuild_start,
                a_race_date,
                baseline=baseline,
                season_weeks=season_weeks,
            ),
        ]
    else:
        future_payloads = build_phase_blocks(
            profile, as_of, a_race_date, baseline=baseline, season_weeks=season_weeks
        )

    if has_bc_trigger:
        future_payloads = _annotate_phases_for_bc_races(future_payloads, events, as_of=as_of)

    return [
        {**payload, "sort_order": past_phase_count + index}
        for index, payload in enumerate(future_payloads)
    ]


def _annotate_phases_for_bc_races(
    payloads: list[dict[str, Any]],
    events: list[AthleteEvent],
    *,
    as_of: date,
) -> list[dict[str, Any]]:
    """Apply visible B-race mini-taper adjustments to remaining macro phases."""
    b_races = [
        event
        for event in events
        if event.priority == "B"
        and event.status == "planned"
        and event.event_date >= as_of
    ]
    if not b_races:
        return payloads

    adjusted: list[dict[str, Any]] = []
    for payload in payloads:
        row = dict(payload)
        if row["end_date"] < as_of or row["phase_type"] == "restore":
            adjusted.append(row)
            continue
        notes: list[str] = []
        for event in b_races:
            if row["start_date"] <= event.event_date <= row["end_date"]:
                notes.append(
                    f"B-race '{event.name}' on {event.event_date.isoformat()} — "
                    "3-day mini-taper before, 3-day active recovery after."
                )
                row["volume_bias"] = round(float(row.get("volume_bias") or 1.0) * 0.88, 2)
        if notes:
            base_intent = row.get("intent") or ""
            marker = notes[0]
            if marker not in base_intent:
                row["intent"] = f"{base_intent} {marker}".strip()
        adjusted.append(row)
    return adjusted


def _snapshot_from_payloads(
    payloads: list[dict[str, Any]],
    *,
    as_of: date,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        if payload["end_date"] < as_of and payload["phase_type"] != "restore":
            continue
        rows.append(
            {
                "phase_type": payload["phase_type"],
                "start_date": payload["start_date"].isoformat()
                if isinstance(payload["start_date"], date)
                else payload["start_date"],
                "end_date": payload["end_date"].isoformat()
                if isinstance(payload["end_date"], date)
                else payload["end_date"],
                "intent": payload.get("intent"),
                "volume_bias": payload.get("volume_bias"),
            }
        )
    return rows


def _payloads_to_phase_rows(
    plan: SeasonPlan,
    payloads: list[dict[str, Any]],
    *,
    as_of: date,
    sort_order_start: int,
) -> list[SeasonPhase]:
    rows: list[SeasonPhase] = []
    sort_order = sort_order_start
    for payload in payloads:
        if payload["end_date"] < as_of and payload["phase_type"] != "restore":
            continue
        row = SeasonPhase(
            season_plan_id=plan.id,
            phase_type=payload["phase_type"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            week_count=payload["week_count"],
            intent=payload["intent"],
            volume_bias=payload["volume_bias"],
            intensity_bias=payload["intensity_bias"],
            sort_order=sort_order,
        )
        rows.append(row)
        sort_order += 1
    return rows


def replan_season(
    db: Session,
    profile: AthleteProfile,
    *,
    reason: str | None = None,
    force: bool = False,
    new_bc_race: bool = False,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Rebuild remaining macro phases while preserving the A-race date."""
    as_of = as_of or date.today()
    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        raise ValueError("No active season plan to replan. Generate a season first.")

    a_race = sync_a_race_from_profile(db, profile)
    if a_race is None:
        raise ValueError("No A-race configured.")

    if a_race.event_date <= as_of:
        raise ValueError("A-race has passed — replan is not applicable.")

    triggers = detect_replan_triggers(db, profile, as_of=as_of, new_bc_race=new_bc_race, plan=plan)
    if not force and not triggers:
        return {
            "replanned": False,
            "message": "No replan triggers detected. Pass force=true to replan anyway.",
            "triggers": [],
        }

    addressed_codes = [trigger["code"] for trigger in triggers]
    events = list_planned_events(db, profile.id)
    baseline = build_season_baseline(db, profile, as_of=as_of)
    phases = get_phases_for_plan(db, plan.id)

    # Macro phases are whole-week units, so the rewrite starts on Monday of the
    # current week. Rebuilding from an arbitrary weekday left the days already
    # lived in the current phase belonging to nothing.
    rebuild_from = monday_of(as_of)

    past_phases = [phase for phase in phases if phase.end_date < rebuild_from]
    overlapping = [phase for phase in phases if phase.end_date >= rebuild_from]

    # The athlete is partway through a phase. Its finished weeks are kept and
    # trimmed back to today rather than deleted, which would leave a gap. The
    # trim itself waits until we know the plan is actually being rewritten.
    straddling = [phase for phase in overlapping if phase.start_date < rebuild_from]
    future_before = [phase for phase in overlapping if phase not in straddling]
    kept_phases = [*past_phases, *straddling]
    # Compared over the same window as the rebuild, so a truncated current phase
    # does not read as a removed one.
    before_snapshot = _serialize_phases(future_before, baseline)

    future_payloads = _build_future_payloads(
        profile,
        events,
        as_of=rebuild_from,
        a_race_date=a_race.event_date,
        triggers=triggers,
        past_phase_count=len(kept_phases),
        baseline=baseline,
        season_start=plan.start_date,
    )
    after_snapshot = _snapshot_from_payloads(future_payloads, as_of=rebuild_from)
    diff = _phase_diff(before_snapshot, after_snapshot)
    summary = _replan_summary(before_snapshot, after_snapshot) if diff else []

    meta = _load_replan_meta(plan)
    replanned_at = _meta_replanned_at(meta)
    if (
        not force
        and not diff
        and replanned_at is not None
        and replanned_at.date() == as_of
        and _meta_codes(meta) == set(addressed_codes)
    ):
        return {
            "replanned": False,
            "message": "Season already replanned today for these conditions.",
            "triggers": [],
            "diff": [],
        }

    if diff:
        for phase in future_before:
            db.delete(phase)
        new_rows = _payloads_to_phase_rows(
            plan,
            future_payloads,
            as_of=rebuild_from,
            sort_order_start=len(kept_phases),
        )
        for row in new_rows:
            db.add(row)
        # The rebuilt tail can end on a different day than the old one, and the
        # timeline is drawn from the plan's own span — leaving it stale drew a
        # macro bar longer than the phases inside it.
        plan.end_date = max(
            [row.end_date for row in new_rows]
            + [phase.end_date for phase in kept_phases]
            + [a_race.event_date]
        )

    replanned_at = datetime.utcnow()
    replan_note = reason or "; ".join(trigger["message"] for trigger in triggers) or "Manual replan"
    warnings = _save_replan_meta(
        plan,
        codes=addressed_codes,
        replanned_at=replanned_at,
        as_of=as_of,
        replan_note=replan_note,
    )

    db.flush()
    db.refresh(plan)

    return {
        "replanned": True,
        "plan_id": plan.id,
        "triggers": [],
        "reason": replan_note,
        "diff": diff,
        "summary": summary,
        "warnings": warnings,
        "phases_before": before_snapshot,
        "phases_after": after_snapshot,
        "message": (
            f"Season replanned from {as_of.isoformat()} with A-race fixed on "
            f"{a_race.event_date.isoformat()}."
            if diff
            else "Replan acknowledged — your current phase timeline already matches these conditions."
        ),
    }
