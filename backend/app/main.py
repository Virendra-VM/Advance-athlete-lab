import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, SessionLocal, engine
from app.migrate import run_migrations
from app.routes import (
    activities,
    athlete,
    athletes,
    auth,
    biometrics,
    coach,
    coros,
    cycle,
    import_history,
    science,
    season,
    strava,
    strava_webhook,
)
from app.services.science_kb import ensure_corpus_loaded

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        ensure_corpus_loaded(db)
    except Exception as exc:  # noqa: BLE001 - never block boot on KB seeding
        logger.warning("Science corpus seeding skipped: %s", exc)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Advance Athlete Lab API",
    description="Personalized AI fitness coach — Phase 2",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(auth.profile_router, prefix="/api")
app.include_router(athletes.router, prefix="/api")
app.include_router(athlete.router, prefix="/api")
app.include_router(strava.router, prefix="/api")
app.include_router(coros.router, prefix="/api")
app.include_router(coach.router, prefix="/api")
app.include_router(season.router, prefix="/api")
app.include_router(biometrics.router, prefix="/api")
app.include_router(cycle.router, prefix="/api")
app.include_router(science.router, prefix="/api")
app.include_router(import_history.router, prefix="/api")
app.include_router(activities.router, prefix="/api")
app.include_router(strava_webhook.router)


@app.get("/")
def root():
    return {"message": "Advance Athlete Lab API is running"}
