from datetime import date

from app.services.season_replan import _phase_diff, detect_replan_triggers


def test_phase_diff_shifted():
    before = [
        {"phase_type": "build", "start_date": "2026-03-01", "end_date": "2026-03-21"},
    ]
    after = [
        {"phase_type": "build", "start_date": "2026-03-08", "end_date": "2026-03-28"},
    ]
    diff = _phase_diff(before, after)
    assert len(diff) == 1
    assert diff[0]["change"] == "shifted"


def test_detect_replan_triggers_empty_without_db(monkeypatch):
    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def count(self):
            return 0

        def join(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    profile = type("Profile", (), {"id": 1})()
    triggers = detect_replan_triggers(FakeDb(), profile, as_of=date(2026, 6, 1))
    assert triggers == []
