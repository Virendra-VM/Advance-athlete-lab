"""Deterministic season plan audit."""

from datetime import date

from app.services.season_audit import _audit_baseline, _audit_phases, _summarize, audit_season_plan


def test_summarize_green_when_no_flags():
    summary = _summarize([])
    assert summary["status"] == "green"
    assert summary["critical_count"] == 0


def test_summarize_red_on_critical():
    flags = [
        {
            "code": "acwr_high",
            "severity": "critical",
            "title": "x",
            "detail": "y",
            "action": "none",
            "action_label": None,
        }
    ]
    summary = _summarize(flags)
    assert summary["status"] == "red"
    assert summary["critical_count"] == 1


def test_audit_phases_flags_short_taper():
    phase = type(
        "Phase",
        (),
        {"phase_type": "taper", "week_count": 1, "start_date": date(2026, 3, 1), "end_date": date(2026, 3, 7)},
    )()
    flags = _audit_phases(
        [phase],
        a_race_date=date(2026, 4, 1),
        season_start=date(2025, 12, 1),
        today=date(2026, 2, 1),
    )
    codes = {row["code"] for row in flags}
    assert "short_taper" in codes


def test_audit_baseline_acwr_critical():
    flags = _audit_baseline({"acwr": 1.55, "weeks_with_training": 4, "volume_damp": 1.0})
    assert any(row["code"] == "acwr_high" and row["severity"] == "critical" for row in flags)


def test_audit_no_plan(monkeypatch):
    profile = type("Profile", (), {"id": 1, "planning_notes": None})()

    monkeypatch.setattr(
        "app.services.season_audit.build_season_context",
        lambda db, p, on_date=None: {"has_plan": False},
    )
    monkeypatch.setattr(
        "app.services.season_audit.sync_a_race_from_profile",
        lambda db, p: type("E", (), {"event_date": date(2026, 6, 1)})(),
    )

    result = audit_season_plan(None, profile)
    assert result["has_plan"] is False
    assert any(row["code"] == "no_plan" for row in result["flags"])
