"""Deterministic season plan audit — rules first, no LLM.

Compares the active macro plan and athlete baseline against periodization
heuristics already used in the engine. Returns actionable flags, not a
pass/fail grade.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteProfile
from app.services.periodization import (
    TAPER_MAX_WEEKS,
    build_season_context,
    get_active_season_plan,
    get_phases_for_plan,
    list_planned_events,
    sync_a_race_from_profile,
    validate_events,
    weeks_between_inclusive,
)
from app.services.planning_notes import parse_planning_notes
from app.services.season_replan import detect_replan_triggers

ACWR_CAUTION = 1.3
ACWR_HIGH = 1.5
MIN_WEEKS_FOR_TAPER_REVIEW = 12
SHORT_TAPER_WEEKS = 1
LONG_SEASON_WEEKS = 16
MIN_TAPER_WEEKS_LONG = 2


AUDIT_DOMAINS = {
    "periodization": "Periodization structure",
    "load_management": "Training load & recovery",
    "race_calendar": "Race calendar",
    "athlete_readiness": "Athlete readiness",
    "general": "General",
}


def _flag(
    code: str,
    severity: str,
    title: str,
    detail: str,
    *,
    action: str = "none",
    action_label: str | None = None,
    category: str = "general",
    evidence: str | None = None,
    metric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "action": action,
        "action_label": action_label,
        "category": category if category in AUDIT_DOMAINS else "general",
        "evidence": evidence,
        "metric": metric,
    }


def _domain_summary(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in AUDIT_DOMAINS}
    for row in flags:
        buckets.setdefault(row.get("category") or "general", []).append(row)

    domains: list[dict[str, Any]] = []
    for domain_id, label in AUDIT_DOMAINS.items():
        if domain_id == "general":
            continue
        rows = buckets.get(domain_id) or []
        if not rows:
            status = "green"
        elif any(row["severity"] == "critical" for row in rows):
            status = "red"
        elif any(row["severity"] == "warning" for row in rows):
            status = "amber"
        else:
            status = "green"
        domains.append(
            {
                "id": domain_id,
                "label": label,
                "status": status,
                "flag_count": len(rows),
            }
        )
    return domains


def _severity_rank(severity: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(severity, 0)


def _summarize(flags: list[dict[str, Any]]) -> dict[str, Any]:
    critical = sum(1 for row in flags if row["severity"] == "critical")
    warning = sum(1 for row in flags if row["severity"] == "warning")
    info = sum(1 for row in flags if row["severity"] == "info")

    if critical:
        status = "red"
        headline = (
            f"{critical} critical issue{'s' if critical != 1 else ''} — address before loading harder."
        )
    elif warning:
        status = "amber"
        headline = (
            f"{warning} item{'s' if warning != 1 else ''} worth adjusting — plan can work with tweaks."
        )
    elif info:
        status = "green"
        headline = "Structure looks sound — minor notes only."
    else:
        status = "green"
        headline = "No structural flags — roadmap aligns with your profile and history."

    return {
        "status": status,
        "headline": headline,
        "critical_count": critical,
        "warning_count": warning,
        "info_count": info,
    }


def _audit_events(events, a_race) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for message in validate_events(events, a_race):
        flags.append(
            _flag(
                "event_spacing",
                "warning",
                "Race calendar conflict",
                message,
                action="replan",
                action_label="Replan remaining weeks",
                category="race_calendar",
                evidence="Stacked B-races or B-races <14 days before A-race reduce taper quality (Mujika & Padilla, 2003).",
            )
        )
    return flags


def _audit_planning_notes(profile: AthleteProfile) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    parsed = parse_planning_notes(profile.planning_notes)
    for warning in parsed["warnings"]:
        flags.append(
            _flag(
                "planning_notes",
                "info",
                "Athlete note on file",
                warning,
                action="coach",
                action_label="Plan this week in Coach",
            )
        )
    return flags


def _audit_phases(
    phases: list,
    *,
    a_race_date: date | None,
    season_start: date,
    today: date,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if not phases:
        flags.append(
            _flag(
                "no_phases",
                "critical",
                "No phases on plan",
                "The season plan has no phase blocks. Generate or rebuild the roadmap.",
                action="rebuild",
                action_label="Rebuild season",
            )
        )
        return flags

    taper_phases = [p for p in phases if p.phase_type == "taper"]
    peak_phases = [p for p in phases if p.phase_type == "peak"]
    recovery_phases = [p for p in phases if p.phase_type == "recovery_week"]

    total_weeks = weeks_between_inclusive(season_start, a_race_date) if a_race_date else 0

    if total_weeks and total_weeks < 8:
        flags.append(
            _flag(
                "short_season",
                "warning",
                "Short runway to A-race",
                f"Only {total_weeks} week(s) remain — expect compressed blocks and limited base work.",
                action="none",
            )
        )

    if taper_phases:
        taper_weeks = sum(p.week_count for p in taper_phases)
        if taper_weeks <= SHORT_TAPER_WEEKS and total_weeks >= MIN_WEEKS_FOR_TAPER_REVIEW:
            flags.append(
                _flag(
                    "short_taper",
                    "warning",
                    "Taper may be tight",
                    f"Taper is {taper_weeks} week(s) on a {total_weeks}-week season. "
                    "Endurance meta-analyses favour ~1–2 weeks at 40–60% volume reduction.",
                    action="replan",
                    action_label="Replan remaining weeks",
                    category="periodization",
                    evidence="Bosquet et al. (2007): 41–60% volume drop with maintained intensity improves performance.",
                    metric={
                        "label": "Taper length",
                        "value": f"{taper_weeks} wk",
                        "reference": "Target 1–2 wk",
                    },
                )
            )
        if taper_weeks > TAPER_MAX_WEEKS:
            flags.append(
                _flag(
                    "long_taper",
                    "warning",
                    "Taper runs long",
                    f"Taper spans {taper_weeks} weeks — fitness may leak before race day.",
                    action="replan",
                    action_label="Replan remaining weeks",
                )
            )
        if total_weeks >= LONG_SEASON_WEEKS and taper_weeks < MIN_TAPER_WEEKS_LONG:
            flags.append(
                _flag(
                    "taper_under_protected",
                    "info",
                    "Consider a longer taper",
                    "For a long build-up, a 2-week taper often clears fatigue better than a single week.",
                    action="replan",
                    action_label="Replan remaining weeks",
                )
            )
    elif a_race_date and a_race_date > today:
        flags.append(
            _flag(
                "missing_taper",
                "critical",
                "No taper block before A-race",
                "Every A-race plan should include a taper before race day.",
                action="rebuild",
                action_label="Rebuild season",
            )
        )

    if not peak_phases and total_weeks >= 10:
        flags.append(
            _flag(
                "no_peak",
                "info",
                "No dedicated peak block",
                "Long seasons usually include race-pace sharpening before taper. "
                "Confirm your build ends with specificity work.",
                action="replan",
                action_label="Replan remaining weeks",
            )
        )

    if total_weeks >= 12 and not recovery_phases:
        flags.append(
                _flag(
                    "no_recovery_weeks",
                    "warning",
                    "No recovery weeks scheduled",
                    "Loading blocks without down weeks increase non-functional overreaching risk.",
                    action="replan",
                    action_label="Replan remaining weeks",
                    category="periodization",
                    evidence="3:1 or 4:1 load/recovery mesocycles reduce overreaching in endurance athletes (Issurin, 2010).",
                )
        )

    return flags


def _audit_baseline(baseline: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not baseline:
        return []

    flags: list[dict[str, Any]] = []

    acwr = baseline.get("acwr")
    if acwr is not None:
        if acwr >= ACWR_HIGH:
            flags.append(
                _flag(
                    "acwr_high",
                    "critical",
                    "Load spike vs usual",
                    f"ACWR is {acwr:.2f} — recent volume is well above your chronic baseline. "
                    "Hold quality down until the ratio settles.",
                    action="coach",
                    action_label="Plan easy week in Coach",
                    category="load_management",
                    evidence="ACWR >1.5 is associated with elevated injury risk in team-sport cohorts (Hulin et al., 2016).",
                    metric={
                        "label": "ACWR",
                        "value": f"{acwr:.2f}",
                        "reference": "Caution ≥1.3 · High ≥1.5",
                    },
                )
            )
        elif acwr >= ACWR_CAUTION:
            flags.append(
                _flag(
                    "acwr_elevated",
                    "warning",
                    "Load climbing fast",
                    f"ACWR is {acwr:.2f} — in the caution band. Avoid stacking hard days this week.",
                    action="coach",
                    action_label="Plan this week in Coach",
                    category="load_management",
                    evidence="Rapid load spikes outpace chronic adaptation — the 10% rule is a conservative guardrail.",
                    metric={
                        "label": "ACWR",
                        "value": f"{acwr:.2f}",
                        "reference": "Caution ≥1.3 · High ≥1.5",
                    },
                )
            )

    if baseline.get("thin_baseline") or (baseline.get("weeks_with_training") or 0) < 3:
        flags.append(
            _flag(
                "thin_baseline",
                "info",
                "Limited training history",
                "Phase limits are conservative because fewer than three recent weeks are logged. "
                "Sync activities so sizing tracks reality.",
                action="none",
            )
        )

    damp = float(baseline.get("volume_damp") or 1.0)
    if damp < 0.9:
        flags.append(
            _flag(
                "volume_damped",
                "info",
                "Volume held below target",
                f"Plan volume is scaled to {round(damp * 100)}% of phase defaults based on your logged training.",
                action="none",
            )
        )

    if baseline.get("load_response_pattern") == "fast_fatiguer":
        flags.append(
            _flag(
                "fast_fatiguer",
                "info",
                "You respond as a fast fatiguer",
                "Extended history suggests you need recovery after loading blocks — "
                f"recovery every {baseline.get('recovery_cycle_weeks', 4)} weeks fits your pattern.",
                action="none",
            )
        )

    injuries = baseline.get("active_injuries") or []
    if injuries:
        flags.append(
            _flag(
                "active_injury",
                "warning",
                "Active injury on file",
                f"Plan assumes modified loading: {', '.join(injuries)}. Keep Coach weeks within safety caps.",
                action="coach",
                action_label="Plan this week in Coach",
            )
        )

    return flags


def _audit_current_week(
    ctx: dict[str, Any],
    *,
    today: date,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    current = ctx.get("current_phase")
    week_intent = ctx.get("week_intent") or {}
    if not current or not week_intent:
        return flags

    phase_type = current.get("phase_type")
    intensity = (week_intent.get("intensity_bias") or "").lower()
    volume_bias = float(week_intent.get("volume_bias") or 1.0)

    if phase_type == "taper" and volume_bias > 0.75:
        flags.append(
            _flag(
                "taper_volume_high",
                "warning",
                "This week is heavy for taper",
                f"Volume bias is {volume_bias}× during taper — taper weeks should sit nearer 0.55×.",
                action="replan",
                action_label="Replan remaining weeks",
            )
        )

    if phase_type == "recovery_week" and intensity in {"high", "moderate"}:
        flags.append(
            _flag(
                "recovery_intensity",
                "warning",
                "Recovery week still calls quality",
                "Recovery blocks should stay easy — check this week's sessions in Coach.",
                action="coach",
                action_label="Plan this week in Coach",
            )
        )

    if phase_type == "base" and intensity == "high":
        flags.append(
            _flag(
                "base_intensity_high",
                "info",
                "High intensity in base phase",
                "Base blocks prioritise aerobic volume — confirm quality fits your macro intent.",
                action="coach",
                action_label="Review week in Coach",
            )
        )

    week_events = week_intent.get("events") or []
    if week_events and phase_type in {"taper", "recovery_week"}:
        names = ", ".join(event.get("name") or "event" for event in week_events)
        flags.append(
            _flag(
                "events_in_down_week",
                "info",
                "Race on a down week",
                f"{names} land this week — mini-taper or recovery rules may override phase defaults.",
                action="none",
            )
        )

    return flags


def _audit_replan_triggers(triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for trigger in triggers:
        severity = "warning" if trigger.get("severity") == "warning" else "info"
        if trigger.get("code") in {"load_spike", "missed_sessions", "injury_flag"}:
            severity = "warning"
        flags.append(
            _flag(
                f"trigger_{trigger.get('code')}",
                severity,
                "Training drift detected",
                trigger.get("message") or "Plan may no longer match recent training.",
                action="replan",
                action_label="Replan remaining weeks",
            )
        )
    return flags


def audit_season_plan(
    db: Session,
    profile: AthleteProfile,
    *,
    on_date: date | None = None,
) -> dict[str, Any]:
    """Run all deterministic checks and return a structured audit payload."""
    today = on_date or date.today()
    ctx = build_season_context(db, profile, on_date=today)

    if ctx is None or not ctx.get("has_plan"):
        a_race = sync_a_race_from_profile(db, profile)
        flags: list[dict[str, Any]] = []
        if a_race:
            flags.append(
                _flag(
                    "no_plan",
                    "warning",
                    "Roadmap not generated",
                    "Your A-race is set but no season plan exists yet. Generate the roadmap first.",
                    action="rebuild",
                    action_label="Generate season",
                )
            )
        else:
            flags.append(
                _flag(
                    "no_a_race",
                    "critical",
                    "No A-race configured",
                    "Set a goal event on Profile before auditing a season plan.",
                    action="profile",
                    action_label="Edit A-race on Profile",
                )
            )
        return {
            "audited_at": datetime.utcnow().isoformat() + "Z",
            "has_plan": False,
            "summary": _summarize(flags),
            "domains": _domain_summary(flags),
            "flags": flags,
        }

    plan = get_active_season_plan(db, profile.id)
    phases = get_phases_for_plan(db, plan.id) if plan else []
    events = list_planned_events(db, profile.id)
    a_race_data = ctx.get("a_race")
    a_race_date = (
        date.fromisoformat(str(a_race_data["date"])[:10]) if a_race_data else None
    )
    baseline = ctx.get("baseline")

    from app.models import AthleteEvent

    event_rows = (
        db.query(AthleteEvent)
        .filter(AthleteEvent.athlete_profile_id == profile.id)
        .all()
    )
    a_race_row = next(
        (event for event in event_rows if event.id == plan.a_race_event_id),
        None,
    )

    flags: list[dict[str, Any]] = []
    flags.extend(_audit_events(event_rows, a_race_row))
    flags.extend(_audit_planning_notes(profile))
    flags.extend(
        _audit_phases(
            phases,
            a_race_date=a_race_date,
            season_start=plan.start_date,
            today=today,
        )
    )
    flags.extend(_audit_baseline(baseline))
    flags.extend(_audit_current_week(ctx, today=today))
    flags.extend(_audit_replan_triggers(detect_replan_triggers(db, profile, as_of=today, plan=plan)))

    stored_warnings = ctx.get("warnings") or []
    for warning in stored_warnings:
        if any(warning in row["detail"] for row in flags):
            continue
        flags.append(
            _flag(
                "stored_warning",
                "info",
                "Planner note",
                warning,
                action="replan",
                action_label="Replan remaining weeks",
            )
        )

    flags.sort(key=lambda row: (-_severity_rank(row["severity"]), row["code"]))

    return {
        "audited_at": datetime.utcnow().isoformat() + "Z",
        "has_plan": True,
        "summary": _summarize(flags),
        "domains": _domain_summary(flags),
        "flags": flags,
    }
