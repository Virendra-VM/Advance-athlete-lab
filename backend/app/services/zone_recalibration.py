"""D-race threshold test completion and zone recalibration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteEvent, AthleteProfile


def d_race_test_protocol(event: AthleteEvent) -> dict[str, Any]:
    """Guided test template for a D-priority checkpoint event."""
    sport = (event.sport_type or "run").lower()
    if "bike" in sport or "cycl" in sport:
        return {
            "protocol": "cycling_ftp",
            "title": "30-min FTP test",
            "description": (
                "20 min easy warm-up, 5 min build, 30 min all-out steady effort, 10 min cool-down. "
                "Use average power for the 30-min block as ~95% FTP (divide by 0.95 for FTP estimate)."
            ),
            "duration_min": 65,
            "session_type": "threshold",
            "intensity": "Hard — controlled max sustainable",
            "metric": "ftp_watts",
        }
    return {
        "protocol": "run_lthr",
        "title": "20-min LTHR test",
        "description": (
            "15 min easy warm-up, 5 min build, 20 min hard steady effort, 10 min cool-down. "
            "Use average heart rate from the 20-min block as LTHR estimate."
        ),
        "duration_min": 50,
        "session_type": "threshold",
        "intensity": "Hard — controlled max sustainable",
        "metric": "lthr_bpm",
    }


def complete_d_race_event(
    db: Session,
    profile: AthleteProfile,
    event: AthleteEvent,
    *,
    ftp_watts: float | None = None,
    lthr_bpm: float | None = None,
    result_metric: str | None = None,
) -> dict[str, Any]:
    if event.priority != "D":
        raise ValueError("Only D-priority events support guided zone recalibration.")
    if event.athlete_profile_id != profile.id:
        raise ValueError("Event does not belong to this athlete.")

    updates: dict[str, Any] = {}
    event.status = "completed"
    event.result_metric = result_metric
    event.updated_at = datetime.utcnow()

    if ftp_watts is not None:
        new_ftp = float(ftp_watts)
        previous = profile.ftp_watts
        if previous is None or new_ftp >= float(previous):
            profile.ftp_watts = new_ftp
            profile.ftp_source = "test"
            updates["ftp_watts"] = new_ftp
            updates["ftp_improved"] = previous is None or new_ftp > float(previous)
        else:
            updates["ftp_watts"] = previous
            updates["ftp_improved"] = False
            updates["ftp_note"] = "Submitted FTP was lower than current — profile unchanged."

    if lthr_bpm is not None:
        new_lthr = float(lthr_bpm)
        previous = profile.lthr_bpm
        if previous is None or new_lthr >= float(previous):
            profile.lthr_bpm = new_lthr
            updates["lthr_bpm"] = new_lthr
            updates["lthr_improved"] = previous is None or new_lthr > float(previous)
        else:
            updates["lthr_bpm"] = previous
            updates["lthr_improved"] = False
            updates["lthr_note"] = "Submitted LTHR was lower than current — profile unchanged."

    db.commit()
    return {
        "event_id": event.id,
        "status": event.status,
        "result_metric": event.result_metric,
        "zones_updated": updates,
        "protocol": d_race_test_protocol(event),
    }
