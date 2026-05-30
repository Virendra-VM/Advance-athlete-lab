#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.services.strava_import import get_import_status, run_import


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Strava bulk export FIT files into PostgreSQL."
    )
    parser.add_argument(
        "--athlete-profile-id",
        type=int,
        required=True,
        help="Athlete profile id to associate imported activities with.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        run_import(db, args.athlete_profile_id)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    status = get_import_status()
    print(
        "Import complete: "
        f"processed={status['processed']} "
        f"imported={status['imported']} "
        f"skipped={status['skipped']} "
        f"errors={len(status['errors'])}"
    )
    for error in status["errors"]:
        print(f"  - {error}", file=sys.stderr)
    return 0 if not status["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
