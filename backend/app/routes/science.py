from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import ScienceChunk, ScienceSource, User
from app.schemas import (
    ScienceSearchResponse,
    ScienceSourceRead,
    ScienceSourceListResponse,
)
from app.services.science_kb import ingest_corpus, retrieve_science

router = APIRouter(prefix="/science", tags=["science"])


@router.get("/sources", response_model=ScienceSourceListResponse)
def list_sources(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sources = db.query(ScienceSource).order_by(ScienceSource.title.asc()).all()
    counts = {}
    for source in sources:
        counts[source.id] = (
            db.query(ScienceChunk.id).filter(ScienceChunk.source_id == source.id).count()
        )
    return ScienceSourceListResponse(
        items=[
            ScienceSourceRead(
                slug=source.slug,
                title=source.title,
                authors=source.authors,
                year=source.year,
                publisher=source.publisher,
                license=source.license,
                url=source.url,
                source_type=source.source_type,
                chunk_count=counts.get(source.id, 0),
            )
            for source in sources
        ]
    )


@router.get("/search", response_model=ScienceSearchResponse)
def search_science(
    q: str = Query(min_length=2, max_length=500),
    sport: list[str] | None = Query(default=None),
    topic: list[str] | None = Query(default=None),
    k: int = Query(default=6, ge=1, le=20),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hits = retrieve_science(db, q, sports=sport, topics=topic, k=k)
    return ScienceSearchResponse(query=q, hits=hits)


@router.post("/reindex", response_model=ScienceSearchResponse)
def reindex_science(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-read the on-disk corpus. Safe to call repeatedly; upserts by slug."""
    ingest_corpus(db)
    return ScienceSearchResponse(query="reindex", hits=retrieve_science(db, "training plan", k=3))
