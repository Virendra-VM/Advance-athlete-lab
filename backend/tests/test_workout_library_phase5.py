"""Phase 5 — export integration with library catalog."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_device_export import build_device_export, validate_fit_bytes  # noqa: E402
from app.services.workout_library import get_template_by_id, list_templates  # noqa: E402


def test_all_running_threshold_templates_export_to_valid_fit():
    templates = list_templates(sport="running", intent="threshold")
    assert len(templates) >= 3
    checked = 0
    for template in templates[:5]:
        package = build_device_export(
            {
                "library_template_id": template["id"],
                "duration_min": 50,
                "sport": "Running",
                "title": template.get("title"),
            },
            physiology={"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
        )
        assert validate_fit_bytes(package["formats"]["fit"]["bytes"])["valid"]
        checked += 1
    assert checked >= 3


def test_cycling_vo2_template_exports_zwo_and_fit():
    template = get_template_by_id("bike_vo2_5x3")
    if template is None:
        candidates = list_templates(sport="cycling", intent="vo2")
        template = candidates[0] if candidates else None
    assert template is not None
    package = build_device_export(
        {
            "library_template_id": template["id"],
            "duration_min": 60,
            "sport": "Cycling",
            "title": template.get("title"),
        },
        physiology={"ftp_watts": 260},
    )
    assert "fit" in package["formats"]
    assert "zwo" in package["formats"]
    assert validate_fit_bytes(package["formats"]["fit"]["bytes"])["valid"]


def test_swim_template_exports_fit_without_zwo():
    templates = list_templates(sport="swimming")
    assert templates
    template = templates[0]
    package = build_device_export(
        {
            "library_template_id": template["id"],
            "duration_min": 45,
            "sport": "Swimming",
            "title": template.get("title"),
        },
        physiology={"css_sec_per_100m": 95},
    )
    assert "fit" in package["formats"]
    assert "zwo" not in package["formats"]
    assert validate_fit_bytes(package["formats"]["fit"]["bytes"])["valid"]
