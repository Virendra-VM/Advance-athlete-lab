from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.migrate import run_migrations
from app.routes import activities, athlete, athletes, auth, coach, coros, import_history, strava, strava_webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
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
app.include_router(import_history.router, prefix="/api")
app.include_router(activities.router, prefix="/api")
app.include_router(strava_webhook.router)


@app.get("/")
def root():
    return {"message": "Advance Athlete Lab API is running"}
