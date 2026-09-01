#!/usr/bin/env python3
"""Ingest the curated science corpus into science_sources / science_chunks.

Usage:
    python scripts/science_ingest/ingest.py
    python scripts/science_ingest/ingest.py --corpus-dir /path/to/corpus
    python scripts/science_ingest/ingest.py --dry-run
    python scripts/science_ingest/ingest.py --query "how hard should easy runs be"
"""

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.science_kb import (  # noqa: E402
    CORPUS_DIR,
    ingest_corpus,
    load_corpus_files,
    retrieve_science,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the science knowledge base corpus.")
    parser.add_argument("--corpus-dir", default=str(CORPUS_DIR))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate corpus files and print counts without writing to the database.",
    )
    parser.add_argument(
        "--query",
        help="After ingest, run a retrieval smoke test with this query.",
    )
    parser.add_argument("--sport", action="append", default=[], help="Sport filter for --query.")
    args = parser.parse_args()

    documents = load_corpus_files(args.corpus_dir)
    if not documents:
        print(f"No corpus files found in {args.corpus_dir}")
        return 1

    print(f"Found {len(documents)} source file(s) in {args.corpus_dir}")
    for document in documents:
        missing = [
            field for field in ("slug", "title", "license", "chunks") if not document.get(field)
        ]
        if missing:
            print(f"  ! {document.get('slug', '<no slug>')}: missing {', '.join(missing)}")
            return 1
        print(f"  - {document['slug']}: {len(document['chunks'])} chunk(s) · {document['license']}")

    if args.dry_run:
        print("Dry run complete — nothing written.")
        return 0

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reports = ingest_corpus(db, args.corpus_dir)
        for report in reports:
            print(
                f"  {report['slug']}: +{report['created']} new, "
                f"~{report['updated']} updated, -{report['removed']} removed"
            )

        if args.query:
            print(f"\nRetrieval smoke test for: {args.query!r}")
            hits = retrieve_science(db, args.query, sports=args.sport, k=5)
            if not hits:
                print("  no matches")
            for hit in hits:
                print(f"  [{hit['score']}] {hit['heading']} ({hit['citation']['slug']})")
    finally:
        db.close()

    print("Ingest complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
