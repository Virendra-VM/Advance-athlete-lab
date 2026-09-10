"""Phase D — athlete coach context cache.

Rebuilds ``build_athlete_coach_context`` at most once per TTL window unless
underlying signals change (sync, new activity, health row).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity, AthleteProfile, DailyHealthMetric, TrainingLoadSnapshot
from app.services.athlete_coach_context import build_athlete_coach_context
from app.services.coros_sync import get_coros_connection

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 120

# profile_id -> (fingerprint, expires_at_monotonic, context)
_CONTEXT_CACHE: dict[int, tuple[str, float, dict[str, Any]]] = {}


def invalidate_coach_context_cache(profile_id: int | None = None) -> None:
    """Drop cached context for one athlete or everyone."""
    if profile_id is None:
        _CONTEXT_CACHE.clear()
        return
    _CONTEXT_CACHE.pop(profile_id, None)


def context_fingerprint(db: Session, profile_id: int) -> str:
    """Cheap signal hash — full context rebuild only when this changes."""
    latest_activity = (
        db.query(Activity.id, Activity.activity_date)
        .filter(
            Activity.athlete_profile_id == profile_id,
            Activity.canonical_activity_id.is_(None),
        )
        .order_by(Activity.activity_date.desc(), Activity.id.desc())
        .first()
    )
    latest_health = (
        db.query(DailyHealthMetric.metric_date, DailyHealthMetric.hrv, DailyHealthMetric.sleep_score)
        .filter(
            DailyHealthMetric.athlete_profile_id == profile_id,
            DailyHealthMetric.provider == "coros",
        )
        .order_by(DailyHealthMetric.metric_date.desc())
        .first()
    )
    load = (
        db.query(TrainingLoadSnapshot.snapshot_at, TrainingLoadSnapshot.load_ratio)
        .filter(
            TrainingLoadSnapshot.athlete_profile_id == profile_id,
            TrainingLoadSnapshot.provider == "coros",
        )
        .order_by(TrainingLoadSnapshot.snapshot_at.desc())
        .first()
    )
    connection = get_coros_connection(db, profile_id)
    profile = db.query(AthleteProfile).filter(AthleteProfile.id == profile_id).first()
    payload = {
        "activity_id": latest_activity[0] if latest_activity else None,
        "activity_date": str(latest_activity[1])[:19] if latest_activity and latest_activity[1] else None,
        "health_date": latest_health[0].isoformat() if latest_health else None,
        "hrv": latest_health[1] if latest_health else None,
        "sleep": latest_health[2] if latest_health else None,
        "load_at": str(load[0])[:19] if load and load[0] else None,
        "load_ratio": load[1] if load else None,
        "coros_synced": connection.last_synced_at.isoformat()
        if connection and connection.last_synced_at
        else None,
        "goal": profile.primary_goal if profile else None,
        "planning_notes": (profile.planning_notes or "")[:120] if profile else None,
        "ftp": profile.ftp_watts if profile else None,
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _strip_cache_meta(context: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(context)
    cleaned.pop("_cache", None)
    return cleaned


def get_athlete_coach_context(
    db: Session,
    profile_id: int,
    *,
    force_refresh: bool = False,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Cached wrapper around ``build_athlete_coach_context``."""
    fingerprint = context_fingerprint(db, profile_id)
    now = time.monotonic()
    cached = _CONTEXT_CACHE.get(profile_id)
    if (
        not force_refresh
        and cached is not None
        and cached[0] == fingerprint
        and cached[1] > now
    ):
        context = dict(cached[2])
        context["_cache"] = {"hit": True, "fingerprint": fingerprint, "ttl_seconds": ttl_seconds}
        logger.debug("Coach context cache hit profile=%s", profile_id)
        return context

    context = build_athlete_coach_context(db, profile_id)
    _CONTEXT_CACHE[profile_id] = (fingerprint, now + ttl_seconds, dict(context))
    context["_cache"] = {"hit": False, "fingerprint": fingerprint, "ttl_seconds": ttl_seconds}
    logger.debug("Coach context cache miss profile=%s", profile_id)
    return context


def coach_context_for_response(
    db: Session,
    profile_id: int,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Context dict safe for ``CoachContextResponse`` (no cache metadata)."""
    return _strip_cache_meta(
        get_athlete_coach_context(db, profile_id, force_refresh=force_refresh)
    )


def cache_stats(profile_id: int) -> dict[str, Any]:
    cached = _CONTEXT_CACHE.get(profile_id)
    if not cached:
        return {"cached": False}
    fingerprint, expires_at, _ = cached
    return {
        "cached": True,
        "fingerprint": fingerprint,
        "expires_in_seconds": max(0, int(expires_at - time.monotonic())),
    }
