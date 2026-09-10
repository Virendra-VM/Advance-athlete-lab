"""Estimate physiology anchors from recent activities and device data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity, AthleteProfile, DailyHealthMetric, FitnessAssessment
from app.services.session_telemetry import resolve_physiology
from app.services.test_activity_detection import detect_test_suggestions
from app.services.zone_engine import build_anchor_nudges, merge_coros_anchors, profile_anchor_fields


def _recent_activities(db: Session, athlete_profile_id: int, *, days: int = 28, limit: int = 40):
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= since,
            Activity.canonical_activity_id.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(limit)
        .all()
    )


def _latest_coros_fitness(db: Session, athlete_profile_id: int) -> FitnessAssessment | None:
    return (
        db.query(FitnessAssessment)
        .filter(
            FitnessAssessment.athlete_profile_id == athlete_profile_id,
            FitnessAssessment.provider == "coros",
        )
        .order_by(FitnessAssessment.snapshot_at.desc())
        .first()
    )


def _latest_resting_hr(db: Session, athlete_profile_id: int) -> float | None:
    row = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == athlete_profile_id,
            DailyHealthMetric.provider == "coros",
            DailyHealthMetric.resting_heart_rate.isnot(None),
        )
        .order_by(DailyHealthMetric.metric_date.desc())
        .first()
    )
    return float(row.resting_heart_rate) if row and row.resting_heart_rate else None


def build_physiology_estimate(
    db: Session,
    profile: AthleteProfile,
) -> dict[str, Any]:
    """Non-destructive preview of anchors derivable from activities and COROS."""
    activities = _recent_activities(db, profile.id)
    resting_hr = _latest_resting_hr(db, profile.id)
    fitness = _latest_coros_fitness(db, profile.id)
    coros_fitness = {}
    if fitness:
        coros_fitness = {
            "vo2max": fitness.vo2max,
            "threshold_pace": fitness.threshold_pace,
        }

    resolved = resolve_physiology(profile, activities, resting_hr=resting_hr)
    merged_anchors = merge_coros_anchors(profile_anchor_fields(profile), coros_fitness)

    suggestions: dict[str, Any] = {}
    sources: dict[str, str] = {}

    if profile.ftp_watts is None:
        estimated_ftp = resolved.get("ftp_estimated_watts") or resolved.get("ftp_watts")
        if estimated_ftp:
            suggestions["ftp_watts"] = round(float(estimated_ftp))
            sources["ftp_watts"] = resolved.get("ftp_source") or "estimated"

    if profile.max_hr_bpm is None and resolved.get("max_hr_bpm"):
        suggestions["max_hr_bpm"] = round(float(resolved["max_hr_bpm"]))
        sources["max_hr_bpm"] = resolved.get("max_hr_source") or "estimated"

    if profile.lthr_bpm is None and resolved.get("lthr_bpm"):
        suggestions["lthr_bpm"] = round(float(resolved["lthr_bpm"]))
        sources["lthr_bpm"] = resolved.get("lthr_source") or "estimated"

    if profile.resting_hr_bpm is None and resting_hr:
        suggestions["resting_hr_bpm"] = round(float(resting_hr))
        sources["resting_hr_bpm"] = "coros_health"

    if profile.threshold_pace_sec_per_km is None:
        threshold = merged_anchors.get("threshold_pace_sec_per_km")
        if threshold:
            suggestions["threshold_pace_sec_per_km"] = round(float(threshold), 1)
            sources["threshold_pace_sec_per_km"] = (
                "coros_fitness" if fitness and fitness.threshold_pace else "derived"
            )

    if profile.vo2max is None and coros_fitness.get("vo2max"):
        suggestions["vo2max"] = round(float(coros_fitness["vo2max"]), 1)
        sources["vo2max"] = "coros_fitness"

    if profile.css_sec_per_100m is None and suggestions.get("threshold_pace_sec_per_km"):
        suggestions["css_sec_per_100m"] = round(
            float(suggestions["threshold_pace_sec_per_km"]) * 0.18, 1
        )
        sources["css_sec_per_100m"] = "estimated_from_threshold_pace"

    test_suggestions = detect_test_suggestions(activities)
    for hit in test_suggestions:
        field = hit["field"]
        if getattr(profile, field, None) is not None:
            continue
        rank = {"high": 3, "medium": 2, "low": 1}
        current_source = sources.get(field)
        current_rank = 3 if current_source in {"coros_fitness", "coros_health"} else 2
        if rank.get(hit.get("confidence"), 0) >= current_rank:
            suggestions[field] = hit["value"]
            sources[field] = f"activity_{hit['kind']}"

    skipped = {}
    for field in (
        "ftp_watts",
        "lthr_bpm",
        "max_hr_bpm",
        "resting_hr_bpm",
        "threshold_pace_sec_per_km",
        "css_sec_per_100m",
        "vo2max",
    ):
        if field not in suggestions and getattr(profile, field, None) is not None:
            skipped[field] = getattr(profile, field)

    nudges = build_anchor_nudges(profile, resolved)

    return {
        "suggestions": suggestions,
        "sources": sources,
        "skipped": skipped,
        "activity_count": len(activities),
        "test_suggestions": test_suggestions,
        "nudges": nudges,
    }


def apply_physiology_estimate(
    db: Session,
    profile: AthleteProfile,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Apply activity/device estimates to profile anchors."""
    preview = build_physiology_estimate(db, profile)
    applied: dict[str, Any] = {}

    for field, value in preview["suggestions"].items():
        current = getattr(profile, field, None)
        if current is not None and not overwrite:
            continue
        setattr(profile, field, value)
        applied[field] = value

    if applied.get("ftp_watts") and (overwrite or profile.ftp_source in (None, "estimated")):
        profile.ftp_source = "estimated"

    db.commit()
    db.refresh(profile)
    return {
        "applied": applied,
        "sources": {key: preview["sources"][key] for key in applied},
        "skipped": preview["skipped"],
        "activity_count": preview["activity_count"],
        "test_suggestions": preview.get("test_suggestions") or [],
        "nudges": preview.get("nudges") or [],
    }


def apply_test_suggestion(
    db: Session,
    profile: AthleteProfile,
    suggestion_id: str,
) -> dict[str, Any]:
    """Apply one detected test-activity suggestion by id (e.g. lthr-42)."""
    preview = build_physiology_estimate(db, profile)
    hit = next(
        (row for row in preview.get("test_suggestions") or [] if row.get("id") == suggestion_id),
        None,
    )
    if hit is None:
        raise LookupError("Test suggestion not found or no longer applicable.")
    field = hit["field"]
    value = hit["value"]
    setattr(profile, field, value)
    if field == "ftp_watts":
        profile.ftp_source = "estimated"
    db.commit()
    db.refresh(profile)
    return {
        "applied": {field: value},
        "sources": {field: f"activity_{hit['kind']}"},
        "suggestion": hit,
    }
