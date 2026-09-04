"""Sync normalized daily biometrics from provider health rows."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteBiometric, DailyHealthMetric, FitnessAssessment


def upsert_biometric_row(
    db: Session,
    athlete_profile_id: int,
    metric_date: date,
    *,
    resting_heart_rate: int | None = None,
    heart_rate_variability: float | None = None,
    sleep_seconds: int | None = None,
    sleep_score: float | None = None,
    readiness_score: float | None = None,
    stress_score: float | None = None,
    temperature_deviation: float | None = None,
    source_device: str = "coros",
    raw: Any = None,
) -> AthleteBiometric:
    row = (
        db.query(AthleteBiometric)
        .filter(
            AthleteBiometric.athlete_profile_id == athlete_profile_id,
            AthleteBiometric.metric_date == metric_date,
        )
        .first()
    )
    if row is None:
        row = AthleteBiometric(
            athlete_profile_id=athlete_profile_id,
            metric_date=metric_date,
            source_device=source_device,
        )
        db.add(row)

    if resting_heart_rate is not None:
        row.resting_heart_rate = int(resting_heart_rate)
    if heart_rate_variability is not None:
        row.heart_rate_variability = float(heart_rate_variability)
    if sleep_seconds is not None:
        row.sleep_seconds = int(sleep_seconds)
    if sleep_score is not None:
        row.sleep_score = float(sleep_score)
    if readiness_score is not None:
        row.readiness_score = float(readiness_score)
    if stress_score is not None:
        row.stress_score = float(stress_score)
    if temperature_deviation is not None:
        row.temperature_deviation = float(temperature_deviation)
    if source_device:
        row.source_device = source_device
    if raw is not None:
        row.raw_json = json.dumps(raw, default=str)[:20000]
    row.updated_at = datetime.utcnow()
    return row


def upsert_from_daily_health(
    db: Session,
    health_row: DailyHealthMetric,
    *,
    readiness_score: float | None = None,
) -> AthleteBiometric:
    sleep_seconds = None
    if health_row.sleep_duration_min is not None:
        sleep_seconds = int(round(float(health_row.sleep_duration_min) * 60))

    return upsert_biometric_row(
        db,
        health_row.athlete_profile_id,
        health_row.metric_date,
        resting_heart_rate=int(health_row.resting_heart_rate)
        if health_row.resting_heart_rate is not None
        else None,
        heart_rate_variability=health_row.hrv,
        sleep_seconds=sleep_seconds,
        sleep_score=health_row.sleep_score,
        readiness_score=readiness_score,
        stress_score=health_row.stress,
        source_device=health_row.provider or "coros",
        raw={"provider": health_row.provider, "metric_date": health_row.metric_date.isoformat()},
    )


def sync_biometrics_from_health(
    db: Session,
    athlete_profile_id: int,
    *,
    lookback_days: int = 35,
) -> int:
    """Backfill athlete_biometrics via provider merge (COROS > manual > garmin)."""
    from app.services.biometric_providers import ingest_daily_biometrics

    start = date.today() - timedelta(days=max(1, lookback_days))
    rows = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == athlete_profile_id,
            DailyHealthMetric.metric_date >= start,
        )
        .order_by(DailyHealthMetric.metric_date.asc())
        .all()
    )

    metric_dates = {row.metric_date for row in rows}
    metric_dates.add(date.today())

    count = 0
    for metric_date in sorted(metric_dates):
        ingest_daily_biometrics(db, athlete_profile_id, metric_date)
        count += 1
    return count


def patch_today_readiness(
    db: Session,
    athlete_profile_id: int,
    readiness_score: float | None,
) -> None:
    if readiness_score is None:
        return
    upsert_biometric_row(
        db,
        athlete_profile_id,
        date.today(),
        readiness_score=float(readiness_score),
        source_device="coros",
    )
    from app.services.biometric_providers import ingest_daily_biometrics

    ingest_daily_biometrics(db, athlete_profile_id, date.today())
