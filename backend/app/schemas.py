from datetime import date, datetime

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
    provider: str = "strava"
    external_activity_id: str | None = None
    strava_activity_id: int | None = None
    canonical_activity_id: int | None = None
    name: str
    activity_date: datetime
    distance_m: float
    moving_time_s: int
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    sport_type: str | None = None
    points_file_path: str | None = None
    source_fit_file: str
    notes: str | None = None
    created_at: datetime | None = None


class ActivityNotesUpdate(BaseModel):
    notes: str | None = None


class ActivityListResponse(BaseModel):
    items: list[ActivityRead]
    total: int
    page: int
    page_size: int


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


class CorosAuthUrlResponse(BaseModel):
    authorization_url: str


class CorosCallbackRequest(BaseModel):
    code: str
    state: str


class CorosConnectionStatus(BaseModel):
    connected: bool
    external_user_id: str | None = None
    last_synced_at: datetime | None = None


class CorosConnectionRead(BaseModel):
    id: int
    athlete_profile_id: int
    provider: str
    external_user_id: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime | None = None


class CorosHealthMetricRead(BaseModel):
    metric_date: date
    sleep_score: float | None = None
    sleep_duration_min: float | None = None
    deep_sleep_pct: float | None = None
    light_sleep_pct: float | None = None
    rem_sleep_pct: float | None = None
    awake_min: float | None = None
    bedtime: str | None = None
    wake_time: str | None = None
    nap_duration_min: float | None = None
    sleep_avg_hr: float | None = None
    steps: int | None = None
    calories: float | None = None
    avg_heart_rate: float | None = None
    resting_heart_rate: float | None = None
    stress: float | None = None
    hrv: float | None = None
    hrv_assessment: str | None = None


class CorosFitnessRead(BaseModel):
    snapshot_at: datetime
    vo2max: float | None = None
    running_performance: float | None = None
    threshold_pace: str | None = None
    race_predictions: dict = {}
    recovery_pct: float | None = None
    recovery_level: str | None = None
    recovery_full_at: str | None = None


class CorosTrainingLoadRead(BaseModel):
    snapshot_at: datetime
    short_load: float | None = None
    long_load: float | None = None
    load_ratio: float | None = None
    daily_comments: list = []


class CorosScheduleItemRead(BaseModel):
    external_id: str
    schedule_date: date
    title: str | None = None
    sport_type: str | None = None
    duration_min: float | None = None
    distance_m: float | None = None
    day_no: int | None = None
    completed_activity_id: int | None = None
    status: str = "planned"  # planned | completed
    completed_activity_name: str | None = None
    completed_activity_provider: str | None = None
    completed_distance_m: float | None = None
    completed_moving_time_s: int | None = None


class CorosOverviewResponse(BaseModel):
    connected: bool
    last_synced_at: datetime | None = None
    today_health: CorosHealthMetricRead | None = None
    health_trend: list[CorosHealthMetricRead] = []
    fitness: CorosFitnessRead | None = None
    training_load: CorosTrainingLoadRead | None = None
    schedule: list[CorosScheduleItemRead] = []
    sync_status: dict = {}


class MetricPoint(BaseModel):
    date: str
    value: float | None = None
    secondary: float | None = None
    label: str | None = None
    meta: dict = {}


class MetricSeriesResponse(BaseModel):
    metric: str
    from_date: date | None = None
    to_date: date | None = None
    points: list[MetricPoint]
    latest: dict = {}
    source: str = "cache"


class CorosDeviceRead(BaseModel):
    device_id: str | None = None
    name: str | None = None
    firmware: str | None = None
    raw: dict = {}


class CorosHistoryBackfillRequest(BaseModel):
    metric: str | None = None
    range: str = "3m"


class CoachContextResponse(BaseModel):
    athlete_profile_id: int
    generated_at: datetime
    profile: dict
    readiness_flags: list[str]
    recent_activities: list[dict]
    coros: dict
