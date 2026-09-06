"""Dynamic season replan when training reality diverges from the macro plan."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteInjury, AthleteProfile, PlannedWorkout, SeasonPhase, SeasonPlan, TrainingPlan
from app.services.periodization import (
    PHASE_DEFAULTS,
    build_phase_blocks,
    get_active_season_plan,
    get_phases_for_plan,
    list_planned_events,
    monday_of,
    serialize_phase,
    sync_a_race_from_profile,
    validate_events,
    weeks_between_inclusive,
)
from app.services.training_load import _round_load, _sum_session_load

REPLAN_META_PREFIX = "__REPLAN_META__:"
REPLAN_ACK_DAYS = 7

HARD_SESSION_TYPES = {"intervals", "vo2", "threshold", "tempo", "race", "hills", "speed", "hard"}


def _week_start(value: date) -> date:
    return monday_of(value)


def _serialize_phases(phases: list[SeasonPhase]) -> list[dict[str, Any]]:
    return [serialize_phase(phase) for phase in phases]


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


def _phase_diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diff: list[dict[str, Any]] = []
    after_by_type = {row["phase_type"]: row for row in after}
    for row in before:
        replacement = after_by_type.get(row["phase_type"])
        if replacement is None:
            diff.append(
                {
                    "phase_type": row["phase_type"],
                    "change": "removed",
                    "before": f"{row['start_date']} → {row['end_date']}",
                }
            )
            continue
        before_dates = (row["start_date"], row["end_date"])
        after_dates = (replacement["start_date"], replacement["end_date"])
        before_intent = row.get("intent")
        after_intent = replacement.get("intent")
        before_volume = row.get("volume_bias")
        after_volume = replacement.get("volume_bias")
        if before_dates != after_dates or before_intent != after_intent or before_volume != after_volume:
            diff.append(
                {
                    "phase_type": row["phase_type"],
                    "change": "shifted",
                    "before": f"{row['start_date']} → {row['end_date']}",
                    "after": f"{replacement['start_date']} → {replacement['end_date']}",
                }
            )
    for row in after:
        if row["phase_type"] not in {item["phase_type"] for item in before}:
            diff.append(
                {
                    "phase_type": row["phase_type"],
                    "change": "added",
                    "after": f"{row['start_date']} → {row['end_date']}",
                }
            )
    return diff


def _build_future_payloads(
    profile: AthleteProfile,
    events: list[AthleteEvent],
    *,
    as_of: date,
    a_race_date: date,
    triggers: list[dict[str, Any]],
    past_phase_count: int,
) -> list[dict[str, Any]]:
    remaining_weeks = weeks_between_inclusive(as_of, a_race_date)
    extra_recovery = any(
        trigger["code"] in {"missed_key_sessions", "active_injury", "sustained_high_acwr"}
        for trigger in triggers
    )
    has_bc_trigger = any(trigger["code"] == "new_bc_race" for trigger in triggers)

    future_payloads = build_phase_blocks(profile, as_of, a_race_date)
    if has_bc_trigger:
        future_payloads = _annotate_phases_for_bc_races(future_payloads, events, as_of=as_of)
    if extra_recovery and remaining_weeks >= 3:
        recovery_defaults = PHASE_DEFAULTS["recovery_week"]
        recovery_end = as_of + timedelta(days=6)
        future_payloads.insert(
            0,
            {
                "phase_type": "recovery_week",
                "start_date": as_of,
                "end_date": recovery_end,
                "week_count": 1,
                "intent": recovery_defaults["intent"],
                "volume_bias": recovery_defaults["volume_bias"],
                "intensity_bias": recovery_defaults["intensity_bias"],
                "long_session_allowed_min": recovery_defaults["long_session_allowed_min"],
                "sort_order": past_phase_count,
            },
        )
        shift_days = 7
        adjusted: list[dict[str, Any]] = []
        for payload in future_payloads[1:]:
            if payload["phase_type"] == "recovery_week":
                adjusted.append(payload)
                continue
            adjusted.append(
                {
                    **payload,
                    "start_date": payload["start_date"] + timedelta(days=shift_days),
                    "end_date": payload["end_date"] + timedelta(days=shift_days),
                }
            )
        future_payloads = [future_payloads[0], *adjusted]
        future_payloads = [
            payload for payload in future_payloads if payload["start_date"] <= a_race_date
        ]
    return future_payloads


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
    phases = get_phases_for_plan(db, plan.id)
    past_phases = [phase for phase in phases if phase.end_date < as_of]
    future_before = [phase for phase in phases if phase.end_date >= as_of]
    before_snapshot = _serialize_phases(future_before)

    future_payloads = _build_future_payloads(
        profile,
        events,
        as_of=as_of,
        a_race_date=a_race.event_date,
        triggers=triggers,
        past_phase_count=len(past_phases),
    )
    after_snapshot = _snapshot_from_payloads(future_payloads, as_of=as_of)
    diff = _phase_diff(before_snapshot, after_snapshot)

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
        for row in _payloads_to_phase_rows(
            plan,
            future_payloads,
            as_of=as_of,
            sort_order_start=len(past_phases),
        ):
            db.add(row)

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
