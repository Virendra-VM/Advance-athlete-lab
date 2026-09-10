#!/usr/bin/env python3
"""Validate the Science Workout Library corpus (base + packs).

Usage:
    python scripts/workout_library_ingest/ingest.py
    python scripts/workout_library_ingest/ingest.py --dry-run
    python scripts/workout_library_ingest/ingest.py --rebuild-packs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_library import (  # noqa: E402
    LIBRARY_DIR,
    clear_library_cache,
    library_stats,
    validate_library_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the workout library corpus.")
    parser.add_argument("--dry-run", action="store_true", help="Validate only.")
    parser.add_argument(
        "--rebuild-packs",
        action="store_true",
        help="Regenerate packs/*.json from build_packs.py before validating.",
    )
    parser.add_argument("--min-templates", type=int, default=200)
    args = parser.parse_args()

    if args.rebuild_packs:
        cmd = [sys.executable, str(BACKEND_ROOT / "scripts/workout_library_ingest/build_packs.py")]
        if args.dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            return result.returncode

    clear_library_cache()
    report = validate_library_catalog()
    stats = library_stats()

    print(f"Library directory: {LIBRARY_DIR}")
    print(f"Library version: {stats['version']}")
    print(f"Templates: {stats['total']} ({stats['unique_ids']} unique ids)")
    print(f"Versioned ids (>1 version): {stats.get('versioned_ids', 0)}")

    if not report["valid"]:
        print("\nValidation errors:")
        for err in report["errors"][:20]:
            print(f"  - {err}")
        if len(report["errors"]) > 20:
            print(f"  ... and {len(report['errors']) - 20} more")
        return 1

    if stats["total"] < args.min_templates:
        print(f"\nExpected at least {args.min_templates} templates, found {stats['total']}")
        return 1

    print("\nBy sport:")
    for sport, count in sorted(stats["by_sport"].items()):
        print(f"  - {sport}: {count}")

    print("\nCatalog validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
