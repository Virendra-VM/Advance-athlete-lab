from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AthleteProfileCreate(BaseModel):
    name: str
    age: int
    weight: float
    fitness_goals: str | None = None
    medical_history: str | None = None


class AthleteProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    weight: float
    fitness_goals: str | None = None
    medical_history: str | None = None


class StravaAuthUrlResponse(BaseModel):
    authorization_url: str


class StravaCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class StravaConnectionStatus(BaseModel):
    connected: bool
    strava_athlete_id: int | None = None


class StravaConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_profile_id: int | None = None
    strava_athlete_id: int
    expires_at: int
    created_at: datetime | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_profile_id: int
    strava_activity_id: int
    name: str
    activity_date: datetime
    distance_m: float
    moving_time_s: int
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    sport_type: str | None = None
    points_file_path: str | None = None
    source_fit_file: str
    created_at: datetime | None = None


class ActivitySummaryBucket(BaseModel):
    month: str
    total_distance_km: float
    activity_count: int


class ActivitySummaryResponse(BaseModel):
    buckets: list[ActivitySummaryBucket]


class ActivityPointRead(BaseModel):
    elapsed_s: float
    distance_m: float
    speed_mps: float | None = None
    altitude_m: float | None = None
    heart_rate: float | None = None
    cadence: float | None = None
    power: float | None = None
    pace_min_per_km: float | None = None


class ActivityPointsResponse(BaseModel):
    activity_id: int
    has_points: bool
    metrics: list[str]
    points: list[ActivityPointRead]


class WeeklyVolumeBucket(BaseModel):
    week_start: str
    week_label: str
    total_distance_km: float


class AthleteStatsResponse(BaseModel):
    acute_load_km: float
    chronic_load_km: float
    acwr: float | None
    weekly_volume_history: list[WeeklyVolumeBucket]


class ImportStartRequest(BaseModel):
    athlete_profile_id: int


class ImportStartResponse(BaseModel):
    status: str
    message: str


class ImportStatusResponse(BaseModel):
    running: bool
    total: int
    processed: int
    imported: int
    skipped: int
    errors: list[str]
