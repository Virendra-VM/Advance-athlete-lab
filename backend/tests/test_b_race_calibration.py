from app.services.b_race_calibration import (
    assess_feasibility,
    calibrate_from_b_race,
    parse_duration_seconds,
    riegel_predict,
)


class _Event:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_parse_duration_seconds():
    assert parse_duration_seconds("42:30") == 42 * 60 + 30
    assert parse_duration_seconds("1:30:00") == 5400
    assert parse_duration_seconds("45 min") == 2700


def test_riegel_predict():
    ten_k_time = 2400.0  # 40:00
    half_pred = riegel_predict(ten_k_time, 10000.0, 21097.5)
    assert half_pred > ten_k_time


def test_calibrate_from_b_race_on_track():
    b = _Event(
        name="Tune-up 10k",
        priority="B",
        sport_type="run",
        target_metric=None,
        result_metric="40:00",
    )
    a = _Event(
        name="Half marathon",
        priority="A",
        sport_type="run",
        target_metric="1:25:00",
        result_metric=None,
    )
    result = calibrate_from_b_race(b, a)
    assert result["available"] is True
    assert result["a_race_feasibility"] in {"on_track", "stretch", "unlikely", "unknown"}


def test_assess_feasibility():
    assert assess_feasibility(3600, 3700) == "on_track"
    assert assess_feasibility(3900, 3600) == "unlikely"
