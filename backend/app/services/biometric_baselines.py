"""Rolling personal baselines for HRV, RHR, and sleep."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from app.models import AthleteBiometric


def fetch_biometric_rows(
    db: Session,
    athlete_profile_id: int,
    *,
    end_date: date | None = None,
    days: int = 28,
) -> list[AthleteBiometric]:
    end_date = end_date or date.today()
    start = end_date - timedelta(days=max(1, days) - 1)
    return (
        db.query(AthleteBiometric)
        .filter(
            AthleteBiometric.athlete_profile_id == athlete_profile_id,
            AthleteBiometric.metric_date >= start,
            AthleteBiometric.metric_date <= end_date,
        )
        .order_by(AthleteBiometric.metric_date.asc())
        .all()
    )


def _values(rows: list[AthleteBiometric], attr: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = getattr(row, attr, None)
        if value is not None:
            out.append(float(value))
    return out


def compute_baselines(
    rows: list[AthleteBiometric],
    *,
    exclude_date: date | None = None,
) -> dict:
    """28-day rolling means excluding the target day when computing baseline."""
    filtered = [row for row in rows if exclude_date is None or row.metric_date != exclude_date]
    hrv_vals = _values(filtered, "heart_rate_variability")
    rhr_vals = [float(row.resting_heart_rate) for row in filtered if row.resting_heart_rate is not None]
    sleep_hours = [
        float(row.sleep_seconds) / 3600.0
        for row in filtered
        if row.sleep_seconds is not None and row.sleep_seconds > 0
    ]
    readiness_vals = _values(filtered, "readiness_score")

    return {
        "sample_days": len(filtered),
        "hrv_mean": round(mean(hrv_vals), 2) if hrv_vals else None,
        "hrv_count": len(hrv_vals),
        "rhr_mean": round(mean(rhr_vals), 1) if rhr_vals else None,
        "sleep_hours_mean": round(mean(sleep_hours), 2) if sleep_hours else None,
        "readiness_mean": round(mean(readiness_vals), 1) if readiness_vals else None,
    }


def hrv_delta_pct(today_hrv: float | None, baseline_mean: float | None) -> float | None:
    if today_hrv is None or baseline_mean is None or baseline_mean <= 0:
        return None
    return round(((float(today_hrv) - baseline_mean) / baseline_mean) * 100.0, 1)


def sleep_hours_from_row(row: AthleteBiometric | None) -> float | None:
    if row is None or row.sleep_seconds is None or row.sleep_seconds <= 0:
        return None
    return round(float(row.sleep_seconds) / 3600.0, 2)


def recent_sleep_hours(rows: list[AthleteBiometric], end_date: date, nights: int = 3) -> list[float]:
    by_date = {row.metric_date: sleep_hours_from_row(row) for row in rows}
    values: list[float] = []
    for offset in range(nights):
        day = end_date - timedelta(days=offset)
        hours = by_date.get(day)
        if hours is not None:
            values.append(hours)
    return values


def recent_readiness_scores(rows: list[AthleteBiometric], end_date: date, days: int = 3) -> list[float]:
    by_date = {
        row.metric_date: float(row.readiness_score)
        for row in rows
        if row.readiness_score is not None
    }
    values: list[float] = []
    for offset in range(days):
        day = end_date - timedelta(days=offset)
        if day in by_date:
            values.append(by_date[day])
    return values
