"""Season plan preview — dry-run before committing."""

from datetime import date

from app.services.periodization import preview_season_plan


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeDb:
    def query(self, model):
        return _FakeQuery()


def test_preview_season_plan_requires_a_race(monkeypatch):
    profile = type(
        "Profile",
        (),
        {
            "id": 1,
            "name": "Test",
            "fitness_level": "intermediate",
            "planning_notes": None,
        },
    )()

    monkeypatch.setattr(
        "app.services.periodization.sync_a_race_from_profile",
        lambda db, p: None,
    )

    try:
        preview_season_plan(_FakeDb(), profile, today=date(2026, 9, 1))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "A-race" in str(exc)
