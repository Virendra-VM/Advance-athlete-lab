"""Phase 3 — expanded catalog, versioning, ingest validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_library import (  # noqa: E402
    clear_library_cache,
    get_template_by_id,
    library_stats,
    list_templates,
    validate_library_catalog,
)


def test_catalog_has_200_plus_templates():
    clear_library_cache()
    stats = library_stats()
    assert stats["version"] == "2.0.0"
    assert stats["total"] >= 200
    assert stats["unique_ids"] >= 200


def test_catalog_validation_passes():
    clear_library_cache()
    report = validate_library_catalog()
    assert report["valid"], report["errors"][:5]
    assert report["total"] >= 200


def test_versioned_template_returns_latest_by_default():
    clear_library_cache()
    latest = get_template_by_id("run_threshold_2x10_lthr1")
    assert latest is not None
    assert int(latest.get("version") or 1) == 2

    v1 = get_template_by_id("run_threshold_2x10_lthr1", version=1)
    v2 = get_template_by_id("run_threshold_2x10_lthr1", version=2)
    assert v1 is not None and v2 is not None
    assert v1["main"]["off"]["duration_min"] == 3
    assert v2["main"]["off"]["duration_min"] == 4


def test_expansion_sports_present():
    clear_library_cache()
    stats = library_stats()
    assert stats["by_sport"].get("rowing", 0) >= 10
    assert stats["by_sport"].get("walking", 0) >= 8
    assert stats["by_sport"].get("cross_training", 0) >= 4


def test_list_templates_rowing_vo2():
    clear_library_cache()
    rows = list_templates(sport="rowing", intent="vo2")
    assert len(rows) >= 2
    assert all("vo2" in row["id"] or row.get("intent") == "vo2" for row in rows)


def test_manifest_exists():
    manifest = BACKEND_ROOT / "data" / "workout_library" / "manifest.json"
    assert manifest.is_file()


def test_ingest_script_passes():
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts/workout_library_ingest/ingest.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_build_packs_dry_run():
    result = subprocess.run(
        [
            sys.executable,
            str(BACKEND_ROOT / "scripts/workout_library_ingest/build_packs.py"),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
