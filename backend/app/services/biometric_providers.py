"""Hardware-agnostic daily biometric ingestion."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteBiometric, DailyHealthMetric, FitnessAssessment
from app.services.biometric_sync import upsert_biometric_row

PROVIDER_PRIORITY = {"coros": 3, "manual": 2, "garmin": 1}


@dataclass
class BiometricDailyPayload:
    resting_heart_rate: int | None = None
    heart_rate_variability: float | None = None
    sleep_seconds: int | None = None
    sleep_score: float | None = None
    readiness_score: float | None = None
    stress_score: float | None = None
    temperature_deviation: float | None = None
    raw: Any = None

    def as_updates(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "resting_heart_rate": self.resting_heart_rate,
                "heart_rate_variability": self.heart_rate_variability,
                "sleep_seconds": self.sleep_seconds,
                "sleep_score": self.sleep_score,
                "readiness_score": self.readiness_score,
                "stress_score": self.stress_score,
                "temperature_deviation": self.temperature_deviation,
            }.items()
            if value is not None
        }


@dataclass
class ProviderSyncResult:
    provider: str
    metric_date: date
    payload: BiometricDailyPayload
    available: bool = True
    message: str | None = None


@dataclass
class MergeResult:
    metric_date: date
    merged_fields: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    winner: str | None = None


class BiometricProvider(ABC):
    name: str

    @abstractmethod
    def sync_daily(
        self,
        db: Session,
        athlete_profile_id: int,
        metric_date: date,
    ) -> ProviderSyncResult:
        """Return normalized payload for one athlete-day (may be empty)."""


class CorosBiometricProvider(BiometricProvider):
    name = "coros"

    def sync_daily(
        self,
        db: Session,
        athlete_profile_id: int,
        metric_date: date,
    ) -> ProviderSyncResult:
        health = (
            db.query(DailyHealthMetric)
            .filter(
                DailyHealthMetric.athlete_profile_id == athlete_profile_id,
                DailyHealthMetric.metric_date == metric_date,
                DailyHealthMetric.provider == "coros",
            )
            .first()
        )
        readiness = None
        if metric_date == date.today():
            fitness = (
                db.query(FitnessAssessment)
                .filter(
                    FitnessAssessment.athlete_profile_id == athlete_profile_id,
                    FitnessAssessment.provider == "coros",
                )
                .order_by(FitnessAssessment.snapshot_at.desc())
                .first()
            )
            if fitness and fitness.recovery_pct is not None:
                readiness = float(fitness.recovery_pct)

        if health is None and readiness is None:
            return ProviderSyncResult(
                provider=self.name,
                metric_date=metric_date,
                payload=BiometricDailyPayload(),
                available=False,
                message="No COROS health row for this date.",
            )

        sleep_seconds = None
        if health and health.sleep_duration_min is not None:
            sleep_seconds = int(round(float(health.sleep_duration_min) * 60))

        payload = BiometricDailyPayload(
            resting_heart_rate=int(health.resting_heart_rate)
            if health and health.resting_heart_rate is not None
            else None,
            heart_rate_variability=health.hrv if health else None,
            sleep_seconds=sleep_seconds,
            sleep_score=health.sleep_score if health else None,
            readiness_score=readiness,
            stress_score=health.stress if health else None,
            raw={"provider": "coros", "metric_date": metric_date.isoformat()},
        )
        return ProviderSyncResult(
            provider=self.name,
            metric_date=metric_date,
            payload=payload,
            available=True,
        )


class ManualBiometricProvider(BiometricProvider):
    name = "manual"

    def sync_daily(
        self,
        db: Session,
        athlete_profile_id: int,
        metric_date: date,
    ) -> ProviderSyncResult:
        row = (
            db.query(AthleteBiometric)
            .filter(
                AthleteBiometric.athlete_profile_id == athlete_profile_id,
                AthleteBiometric.metric_date == metric_date,
                AthleteBiometric.source_device == "manual",
            )
            .first()
        )
        if row is None:
            return ProviderSyncResult(
                provider=self.name,
                metric_date=metric_date,
                payload=BiometricDailyPayload(),
                available=False,
            )
        payload = BiometricDailyPayload(
            resting_heart_rate=row.resting_heart_rate,
            heart_rate_variability=row.heart_rate_variability,
            sleep_seconds=row.sleep_seconds,
            sleep_score=row.sleep_score,
            readiness_score=row.readiness_score,
            stress_score=row.stress_score,
            temperature_deviation=row.temperature_deviation,
            raw={"provider": "manual"},
        )
        return ProviderSyncResult(
            provider=self.name,
            metric_date=metric_date,
            payload=payload,
            available=True,
        )


class GarminBiometricProvider(BiometricProvider):
    """Stub for future Garmin Health API integration."""

    name = "garmin"

    def sync_daily(
        self,
        db: Session,
        athlete_profile_id: int,
        metric_date: date,
    ) -> ProviderSyncResult:
        return ProviderSyncResult(
            provider=self.name,
            metric_date=metric_date,
            payload=BiometricDailyPayload(),
            available=False,
            message="Garmin adapter not configured.",
        )


def default_providers() -> list[BiometricProvider]:
    return [CorosBiometricProvider(), ManualBiometricProvider(), GarminBiometricProvider()]


def merge_provider_payloads(
    results: list[ProviderSyncResult],
    *,
    metric_date: date,
) -> tuple[BiometricDailyPayload, MergeResult]:
    """COROS wins over manual over garmin when both supply the same field."""
    merge = MergeResult(metric_date=metric_date)
    winners: dict[str, tuple[str, Any]] = {}

    ordered = sorted(
        [result for result in results if result.available],
        key=lambda item: PROVIDER_PRIORITY.get(item.provider, 0),
        reverse=True,
    )

    for result in ordered:
        for field_name, value in result.payload.as_updates().items():
            if field_name not in winners:
                winners[field_name] = (result.provider, value)
                merge.merged_fields.append(field_name)
                continue
            existing_provider, existing_value = winners[field_name]
            if existing_value == value:
                continue
            merge.conflicts.append(
                {
                    "field": field_name,
                    "kept_provider": existing_provider,
                    "kept_value": existing_value,
                    "discarded_provider": result.provider,
                    "discarded_value": value,
                }
            )

    merge.winner = ordered[0].provider if ordered else None
    merged = BiometricDailyPayload()
    for field_name, (_provider, value) in winners.items():
        setattr(merged, field_name, value)
    return merged, merge


def ingest_daily_biometrics(
    db: Session,
    athlete_profile_id: int,
    metric_date: date,
    *,
    providers: list[BiometricProvider] | None = None,
) -> dict[str, Any]:
    """Sync all providers for one day and upsert the merged athlete_biometrics row."""
    providers = providers or default_providers()
    results = [provider.sync_daily(db, athlete_profile_id, metric_date) for provider in providers]
    merged, merge_info = merge_provider_payloads(results, metric_date=metric_date)

    if not merge_info.merged_fields:
        return {
            "metric_date": metric_date.isoformat(),
            "updated": False,
            "conflicts": merge_info.conflicts,
            "providers": [
                {"provider": result.provider, "available": result.available, "message": result.message}
                for result in results
            ],
        }

    winner = merge_info.winner or "coros"
    upsert_biometric_row(
        db,
        athlete_profile_id,
        metric_date,
        resting_heart_rate=merged.resting_heart_rate,
        heart_rate_variability=merged.heart_rate_variability,
        sleep_seconds=merged.sleep_seconds,
        sleep_score=merged.sleep_score,
        readiness_score=merged.readiness_score,
        stress_score=merged.stress_score,
        temperature_deviation=merged.temperature_deviation,
        source_device=winner,
        raw={
            "merge": merge_info.merged_fields,
            "conflicts": merge_info.conflicts,
            "providers": [result.provider for result in results if result.available],
        },
    )

    if merge_info.conflicts:
        _log_conflicts(db, athlete_profile_id, metric_date, merge_info.conflicts)

    return {
        "metric_date": metric_date.isoformat(),
        "updated": True,
        "source_device": winner,
        "merged_fields": merge_info.merged_fields,
        "conflicts": merge_info.conflicts,
        "providers": [
            {"provider": result.provider, "available": result.available, "message": result.message}
            for result in results
        ],
    }


def _log_conflicts(
    db: Session,
    athlete_profile_id: int,
    metric_date: date,
    conflicts: list[dict[str, Any]],
) -> None:
    row = (
        db.query(AthleteBiometric)
        .filter(
            AthleteBiometric.athlete_profile_id == athlete_profile_id,
            AthleteBiometric.metric_date == metric_date,
        )
        .first()
    )
    if row is None:
        return
    existing: dict[str, Any] = {}
    if row.raw_json:
        try:
            existing = json.loads(row.raw_json)
        except json.JSONDecodeError:
            existing = {}
    existing["conflict_log"] = conflicts
    existing["conflict_logged_at"] = datetime.utcnow().isoformat()
    row.raw_json = json.dumps(existing, default=str)[:20000]
