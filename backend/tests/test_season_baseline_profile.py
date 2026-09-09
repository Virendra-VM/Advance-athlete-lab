"""Season baseline uses profile fields beyond synced activities."""

from datetime import date

from app.models import AthleteProfile
from app.services.season_baseline import build_season_baseline, compose_season_baseline


def test_compose_applies_weekly_budget_cap():
    baseline = compose_season_baseline(
        fitness_level="intermediate",
        chronic_weekly_minutes=600,
        weeks_with_training=4,
        max_weekly_minutes_cap=300,
        data_sources=["Weekly minutes budget (300 min)"],
    )
    assert baseline["volume_damp"] < 1.0
    assert any("300 min weekly budget" in note for note in baseline["notes"])


def test_build_baseline_includes_profile_sources(monkeypatch):
    profile = AthleteProfile(
        name="Profile Tester",
        age=30,
        weight=70.0,
        fitness_level="intermediate",
        days_per_week=4,
        weekly_minutes_budget=240,
        training_history_months=3,
        workout_duration_minutes=60,
        planning_notes="Travel next month",
    )

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def scalar(self):
            return None

        def all(self):
            return []

    class FakeDb:
        def query(self, *args, **kwargs):
            return FakeQuery()

    monkeypatch.setattr(
        "app.services.season_baseline.compute_acwr",
        lambda db, athlete_id: {"acute_minutes": 0, "chronic_minutes": None, "acwr": None},
    )
    monkeypatch.setattr(
        "app.services.season_baseline._active_injuries",
        lambda db, athlete_id: ([], False),
    )
    monkeypatch.setattr(
        "app.services.season_baseline._longest_logged_minutes",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.season_baseline._weeks_with_training",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        "app.services.season_baseline._weekly_training_minutes",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.athlete_profile.get_profile_sports",
        lambda db, athlete_id: [],
    )

    baseline = build_season_baseline(FakeDb(), profile, as_of=date(2026, 9, 7))
    sources = baseline.get("data_sources") or []
    assert any("time budget" in item.lower() for item in sources)
    assert any("Training history" in item for item in sources)
    assert any("Planning notes" in item for item in sources)
