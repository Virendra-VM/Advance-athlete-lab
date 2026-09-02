"""Science knowledge base: ingest a curated corpus and retrieve citable chunks.

Retrieval is lexical (BM25-style scoring plus tag boosts) so the KB works with a
plain Postgres install. ``ScienceChunk.embedding_json`` is reserved for a later
pgvector upgrade; nothing here depends on an embedding provider.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import ScienceChunk, ScienceSource

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "science_corpus"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for", "from",
    "how", "i", "if", "in", "is", "it", "my", "of", "on", "or", "should", "than", "that",
    "the", "their", "them", "then", "there", "they", "this", "to", "was", "we", "what",
    "when", "which", "while", "with", "you", "your",
}

# Query words that reliably map onto corpus tags.
TOPIC_SYNONYMS = {
    "taper": ["periodization"],
    "peak": ["periodization"],
    "base": ["periodization"],
    "block": ["periodization"],
    "zone": ["intensity", "zones"],
    "zones": ["intensity", "zones"],
    "easy": ["intensity"],
    "hard": ["intensity"],
    "interval": ["intensity", "sessions"],
    "intervals": ["intensity", "sessions"],
    "threshold": ["intensity", "sessions"],
    "injury": ["injury", "injury-prevention", "contraindications"],
    "injured": ["injury", "contraindications"],
    "pain": ["injury", "red-flags", "safety"],
    "hurt": ["injury", "safety"],
    "sore": ["recovery", "readiness"],
    "tired": ["readiness", "recovery"],
    "sleep": ["sleep", "readiness"],
    "hrv": ["hrv", "readiness"],
    "recovery": ["recovery", "readiness"],
    "rest": ["recovery", "readiness"],
    "load": ["load-management", "acwr"],
    "acwr": ["acwr", "load-management"],
    "overtraining": ["load-management", "readiness"],
    "volume": ["weekly-volume", "progression"],
    "mileage": ["weekly-volume", "progression"],
    "progress": ["progression", "overload"],
    "progression": ["progression", "overload"],
    "strength": ["strength", "frequency"],
    "lifting": ["strength", "overload"],
    "gym": ["strength", "templates"],
    "mobility": ["mobility"],
    "beginner": ["beginner", "templates"],
    "plan": ["planning", "weekly-structure", "templates"],
    "week": ["weekly-structure", "planning"],
    "heat": ["heat", "environment"],
    "altitude": ["altitude", "environment"],
    "swolf": ["specificity", "sessions"],
    "stroke": ["specificity", "sessions"],
    "cadence": ["sessions"],
    "spm": ["sessions"],
    "eccentric": ["injury-prevention", "load-management"],
    "impact": ["injury-prevention", "load-management"],
    "vagal": ["recovery", "hrv", "readiness"],
    "parasympathetic": ["recovery", "hrv"],
    "cns": ["recovery", "readiness", "strength"],
    "rpe": ["rpe", "intensity"],
    "ftp": ["intensity", "zones", "power"],
    "watts": ["intensity", "power", "sessions"],
    "power": ["intensity", "power", "sessions"],
    "sweet": ["intensity", "sessions"],
    "over": ["intensity", "sessions"],
    "under": ["intensity", "sessions"],
    "decoupling": ["heart-rate", "readiness"],
    "drift": ["heart-rate", "readiness"],
    "fever": ["return-to-play", "safety"],
    "illness": ["return-to-play", "safety"],
    "swim": ["specificity"],
    "return": ["return-to-play", "progression"],
    "comeback": ["return-to-play"],
}

SPORT_ALIASES = {
    "running": "run",
    "run": "run",
    "runner": "run",
    "trail running": "run",
    "cycling": "ride",
    "ride": "ride",
    "bike": "ride",
    "cyclist": "ride",
    "swimming": "swim",
    "swim": "swim",
    "triathlon": "triathlon",
    "strength training": "strength",
    "strength": "strength",
    "gym": "strength",
    "yoga / mobility": "general",
    "yoga": "general",
    "mobility": "general",
    "pilates": "general",
    "walking / hiking": "general",
    "rowing": "general",
    "team sport": "general",
}


def normalize_sport(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower()
    return SPORT_ALIASES.get(key, key)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [word for word in words if word not in STOPWORDS and len(word) > 2]


def _split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip().lower() for part in value.split(",") if part.strip()]


# ---------------------------------------------------------------- ingest


def load_corpus_files(corpus_dir: Path | str = CORPUS_DIR) -> list[dict]:
    directory = Path(corpus_dir)
    if not directory.exists():
        return []
    documents = []
    for path in sorted(directory.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            documents.append(json.load(handle))
    return documents


def ingest_document(db: Session, document: dict) -> dict:
    """Upsert one corpus document and its chunks. Returns a small change report."""
    slug = document["slug"]
    source = db.query(ScienceSource).filter(ScienceSource.slug == slug).first()
    if source is None:
        source = ScienceSource(slug=slug)
        db.add(source)

    source.title = document["title"]
    source.authors = document.get("authors")
    source.year = document.get("year")
    source.publisher = document.get("publisher")
    source.license = document.get("license")
    source.url = document.get("url")
    source.source_type = document.get("source_type", "guideline")
    db.flush()

    seen_keys: set[str] = set()
    created = 0
    updated = 0
    for entry in document.get("chunks", []):
        chunk_key = entry["key"]
        seen_keys.add(chunk_key)
        chunk = (
            db.query(ScienceChunk)
            .filter(
                ScienceChunk.source_id == source.id,
                ScienceChunk.chunk_key == chunk_key,
            )
            .first()
        )
        if chunk is None:
            chunk = ScienceChunk(source_id=source.id, chunk_key=chunk_key)
            db.add(chunk)
            created += 1
        else:
            updated += 1
        chunk.heading = entry.get("heading")
        chunk.body = entry["body"]
        chunk.audience = entry.get("audience")
        chunk.sport_tags = ",".join(entry.get("sport_tags", []))
        chunk.topic_tags = ",".join(entry.get("topic_tags", []))

    # Drop chunks that were removed from the corpus file.
    stale = (
        db.query(ScienceChunk)
        .filter(ScienceChunk.source_id == source.id)
        .all()
    )
    removed = 0
    for chunk in stale:
        if chunk.chunk_key not in seen_keys:
            db.delete(chunk)
            removed += 1

    return {"slug": slug, "created": created, "updated": updated, "removed": removed}


def ingest_corpus(db: Session, corpus_dir: Path | str = CORPUS_DIR) -> list[dict]:
    reports = [ingest_document(db, document) for document in load_corpus_files(corpus_dir)]
    db.commit()
    return reports


def corpus_is_empty(db: Session) -> bool:
    return db.query(ScienceChunk.id).first() is None


def ensure_corpus_loaded(db: Session) -> list[dict]:
    """Upsert owned playbook chunks so new sport templates can retrieve them."""
    return ingest_corpus(db)


# ---------------------------------------------------------------- retrieval


def _expand_query_tags(tokens: list[str]) -> set[str]:
    tags: set[str] = set()
    for token in tokens:
        tags.update(TOPIC_SYNONYMS.get(token, []))
    return tags


def retrieve_science(
    db: Session,
    query: str,
    sports: list[str] | None = None,
    topics: list[str] | None = None,
    k: int = 6,
) -> list[dict]:
    """Return the top-k citable chunks for a query, best match first."""
    chunks = db.query(ScienceChunk).all()
    if not chunks:
        return []

    sources = {source.id: source for source in db.query(ScienceSource).all()}

    query_tokens = _tokenize(query)
    wanted_sports = {normalize_sport(sport) for sport in (sports or []) if sport}
    wanted_topics = {topic.strip().lower() for topic in (topics or []) if topic}
    wanted_topics |= _expand_query_tags(query_tokens)

    documents = []
    for chunk in chunks:
        text = " ".join(
            filter(None, [chunk.heading, chunk.body, chunk.topic_tags, chunk.sport_tags])
        )
        documents.append((chunk, Counter(_tokenize(text))))

    total_docs = len(documents)
    avg_length = sum(sum(counts.values()) for _, counts in documents) / max(1, total_docs)
    doc_frequency: Counter[str] = Counter()
    for _, counts in documents:
        doc_frequency.update(counts.keys())

    k1, b = 1.4, 0.75
    scored = []
    for chunk, counts in documents:
        length = sum(counts.values()) or 1
        score = 0.0
        for token in query_tokens:
            freq = counts.get(token, 0)
            if freq == 0:
                continue
            idf = math.log(1 + (total_docs - doc_frequency[token] + 0.5) / (doc_frequency[token] + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_length))

        chunk_topics = set(_split_tags(chunk.topic_tags))
        chunk_sports = set(_split_tags(chunk.sport_tags))

        topic_overlap = len(wanted_topics & chunk_topics)
        score += 1.6 * topic_overlap

        if wanted_sports:
            if wanted_sports & chunk_sports:
                score += 1.2
            elif "general" in chunk_sports or chunk.audience == "shared":
                score += 0.4

        # Safety guidance stays reachable even for vague questions.
        if "safety" in chunk_topics or "red-flags" in chunk_topics:
            score += 0.3

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    results = []
    for score, chunk in scored[:k]:
        source = sources.get(chunk.source_id)
        results.append(
            {
                "chunk_id": chunk.id,
                "score": round(score, 3),
                "heading": chunk.heading,
                "body": chunk.body,
                "audience": chunk.audience,
                "sport_tags": _split_tags(chunk.sport_tags),
                "topic_tags": _split_tags(chunk.topic_tags),
                "citation": {
                    "slug": source.slug if source else None,
                    "title": source.title if source else None,
                    "authors": source.authors if source else None,
                    "year": source.year if source else None,
                    "publisher": source.publisher if source else None,
                    "license": source.license if source else None,
                    "url": source.url if source else None,
                },
            }
        )
    return results


def format_science_for_prompt(hits: list[dict]) -> str:
    """Render retrieved chunks with stable [S1..Sn] labels for citation."""
    if not hits:
        return "No retrieved evidence. Do not invent citations."
    lines = []
    for index, hit in enumerate(hits, start=1):
        citation = hit["citation"]
        origin = ", ".join(
            str(part)
            for part in [citation.get("title"), citation.get("year")]
            if part is not None
        )
        lines.append(f"[S{index}] {hit['heading']} — {origin}\n{hit['body']}")
    return "\n\n".join(lines)


def citation_slugs(hits: list[dict]) -> list[str]:
    slugs = []
    for hit in hits:
        slug = hit["citation"].get("slug")
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs
