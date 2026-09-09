"""Grounded science retrieval — no invented papers when the playbook has no match."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.services.ai_coach import template_science_lookup  # noqa: E402
from app.services.science_kb import (  # noqa: E402
    format_science_for_prompt,
    grounded_hits,
    ingest_corpus,
    retrieve_science,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_acwr_query_is_grounded():
    db = _db()
    try:
        ingest_corpus(db)
        hits = retrieve_science(db, "What is ACWR and why does it matter?", k=6)
        strong = grounded_hits(hits)
        assert strong, hits
        blob = " ".join(hit["body"].lower() for hit in strong)
        assert "acute" in blob or "acwr" in blob
    finally:
        db.close()


def test_heat_and_bfr_have_playbook_chunks():
    db = _db()
    try:
        ingest_corpus(db)
        heat = grounded_hits(
            retrieve_science(
                db, "What is the latest research on heat acclimation for my half-marathon?"
            )
        )
        bfr = grounded_hits(
            retrieve_science(
                db,
                "How does blood flow restriction training affect my threshold recovery?",
            )
        )
        assert heat, "heat acclimation should retrieve a playbook chunk"
        assert bfr, "BFR should retrieve the conservative playbook chunk"
        assert any("heat" in (hit.get("heading") or "").lower() for hit in heat)
        assert any("restriction" in (hit.get("heading") or "").lower() for hit in bfr)
    finally:
        db.close()


def test_key_physiology_topics_are_grounded():
    db = _db()
    try:
        ingest_corpus(db)
        cho = grounded_hits(
            retrieve_science(
                db, "How should I periodize carbohydrates around zone 2 training?"
            )
        )
        lactate = grounded_hits(
            retrieve_science(db, "How do I improve lactate clearance between intervals?")
        )
        taper = grounded_hits(
            retrieve_science(db, "What tapering strategies should I use in race week?")
        )
        polarized = grounded_hits(
            retrieve_science(db, "What is polarized intensity distribution?")
        )
        assert cho, "zone 2 carbohydrate periodization should retrieve"
        assert lactate, "lactate clearance should retrieve"
        assert taper, "tapering strategies should retrieve"
        assert polarized, "polarized distribution should retrieve"
        cho_blob = " ".join(hit["body"].lower() for hit in cho)
        lactate_blob = " ".join(hit["body"].lower() for hit in lactate)
        assert "carbohydrate" in cho_blob or "glycogen" in cho_blob
        assert "lactate" in lactate_blob
    finally:
        db.close()


def test_nonsense_query_is_not_grounded():
    db = _db()
    try:
        ingest_corpus(db)
        hits = retrieve_science(db, "ketogenic quantum crystals for curling", k=6)
        assert grounded_hits(hits) == []
        prompt = format_science_for_prompt(hits, grounded=False)
        assert "Do not invent" in prompt or "not invent" in prompt.lower()
    finally:
        db.close()


def test_ungrounded_template_refuses_fake_papers():
    reply = template_science_lookup(
        "What is the latest 2026 ketogenic curling protocol?",
        {"load": {"minutes_acwr": 1.1}},
        [],
        grounded=False,
    )
    text = reply["reply"]
    assert "Not in playbook" in text
    assert "DOI" in text or "paper" in text.lower()
    assert reply["intent"] == "SCIENCE_LOOKUP"
    assert reply["citations"] == []


def run() -> None:
    tests = [
        test_acwr_query_is_grounded,
        test_heat_and_bfr_have_playbook_chunks,
        test_key_physiology_topics_are_grounded,
        test_nonsense_query_is_not_grounded,
        test_ungrounded_template_refuses_fake_papers,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()
