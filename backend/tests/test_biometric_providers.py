from datetime import date

from app.services.biometric_providers import (
    BiometricDailyPayload,
    MergeResult,
    ProviderSyncResult,
    merge_provider_payloads,
)


def test_merge_coros_wins_over_manual():
    coros = ProviderSyncResult(
        provider="coros",
        metric_date=date(2026, 6, 1),
        payload=BiometricDailyPayload(resting_heart_rate=52, heart_rate_variability=65.0),
        available=True,
    )
    manual = ProviderSyncResult(
        provider="manual",
        metric_date=date(2026, 6, 1),
        payload=BiometricDailyPayload(resting_heart_rate=55, heart_rate_variability=60.0),
        available=True,
    )
    merged, info = merge_provider_payloads([manual, coros], metric_date=date(2026, 6, 1))
    assert merged.resting_heart_rate == 52
    assert merged.heart_rate_variability == 65.0
    assert info.winner == "coros"
    assert len(info.conflicts) == 2


def test_merge_empty_returns_empty():
    merged, info = merge_provider_payloads([], metric_date=date(2026, 6, 1))
    assert merged.as_updates() == {}
    assert isinstance(info, MergeResult)
