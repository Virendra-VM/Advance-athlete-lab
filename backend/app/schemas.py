from datetime import date as Date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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
    sport_type_code: str | None = None
    points_file_path: str | None = None
    source_fit_file: str
    notes: str | None = None
    detail: dict | None = None
    sport_family: str | None = None
    detail_fetched_at: datetime | None = None
    created_at: datetime | None = None


class ActivityNotesUpdate(BaseModel):
    notes: str | None = None


class ActivityNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ActivityNoteUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ActivityNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    athlete_profile_id: int
    body: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ActivityNoteListResponse(BaseModel):
    items: list[ActivityNoteRead]


class ActivityEnrichResponse(BaseModel):
    ok: bool
    skipped: bool = False
    reason: str | None = None
    activity_id: int
    detail: dict | None = None
    errors: list[str] = []
    sources: list[str] = []
    activity: ActivityRead | None = None


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
    acute_load: float | None = None
    chronic_load: float | None = None
    load_acwr: float | None = None
    acwr_source: str | None = None
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
    metric_date: Date
    sleep_score: float | None = None
    sleep_duration_min: float | None = None
    deep_sleep_pct: float | None = None
    light_sleep_pct: float | None = None
    rem_sleep_pct: float | None = None
    deep_sleep_min: float | None = None
    light_sleep_min: float | None = None
    rem_sleep_min: float | None = None
    awake_min: float | None = None
    awake_count: float | None = None
    main_sleep_min: float | None = None
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
    schedule_date: Date
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
    from_date: Date | None = None
    to_date: Date | None = None
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


class AutoregWarning(BaseModel):
    code: str
    message: str
    severity: str = "warn"
    link: str | None = None


class TodaysCallResponse(BaseModel):
    date: str
    call_level: str
    label: str
    color: str
    base_level: str | None = None
    base_source: str | None = None
    directive: str | None = None
    downgrade_reasons: list[str] = []
    warnings: list[AutoregWarning] = []
    metrics: dict = {}
    baselines: dict = {}
    acwr: dict = {}
    max_hard_sessions_today: int = 0


class CoachContextResponse(BaseModel):
    athlete_profile_id: int
    generated_at: datetime
    profile: dict
    readiness_flags: list[str]
    recent_activities: list[dict]
    coros: dict
    safety: dict = {}
    physiology: dict = {}
    focal_sessions: list[dict] = []
    season: dict | None = None
    todays_call: dict | None = None


class ScienceCitation(BaseModel):
    slug: str | None = None
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    publisher: str | None = None
    license: str | None = None
    url: str | None = None


class ScienceHit(BaseModel):
    chunk_id: int
    score: float
    heading: str | None = None
    body: str
    audience: str | None = None
    sport_tags: list[str] = []
    topic_tags: list[str] = []
    citation: ScienceCitation


class ScienceSearchResponse(BaseModel):
    query: str
    hits: list[ScienceHit] = []


class ScienceSourceRead(BaseModel):
    slug: str
    title: str
    authors: str | None = None
    year: int | None = None
    publisher: str | None = None
    license: str | None = None
    url: str | None = None
    source_type: str
    chunk_count: int = 0


class ScienceSourceListResponse(BaseModel):
    items: list[ScienceSourceRead]


# ---------------------------------------------------------------- AI coach


class SafetyIssue(BaseModel):
    level: str
    code: str
    message: str


class PlanWorkoutRead(BaseModel):
    id: int | None = None
    date: Date
    sport: str | None = None
    title: str | None = None
    session_type: str | None = None
    duration_min: float | None = None
    distance_m: float | None = None
    intensity: str | None = None
    description: str | None = None
    structure: list[dict] = []
    completed_activity_id: int | None = None


class WeekPlanRead(BaseModel):
    title: str | None = None
    summary: str | None = None
    focus: str | None = None
    week_start: Date | None = None
    workouts: list[PlanWorkoutRead] = []
    coach_notes: str | None = None
    citations: list[str] = []


class CoachPlanResponse(BaseModel):
    plan_id: int | None = None
    provider: str
    model: str
    week_start: Date
    plan: WeekPlanRead
    safety_issues: list[SafetyIssue] = []
    generation_notes: list[str] = []
    citations: list[ScienceCitation] = []
    disclaimer: str | None = None
    created_at: datetime | None = None
    on_schedule: bool = False


class PlanGenerateRequest(BaseModel):
    week_start: Date | None = None
    timezone: str | None = Field(default=None, max_length=64)


class ReadinessDirective(BaseModel):
    action: str
    max_hard_sessions_today: int
    reason: str


class DailyAdviceRead(BaseModel):
    headline: str
    recommendation: str
    session_adjustment: str | None = None
    rationale: str | None = None
    citations: list[str] = []
    escalate: bool = False
    escalation_reason: str | None = None


class CoachAdviceResponse(BaseModel):
    provider: str
    model: str
    date: Date
    readiness: ReadinessDirective
    advice: DailyAdviceRead
    citations: list[ScienceCitation] = []
    disclaimer: str | None = None
    cached: bool = False
    generated_at: datetime | None = None
    scope: str = "today"
    week_start: Date | None = None
    topic: str | None = None


class CoachChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    timezone: str | None = Field(default=None, max_length=64)
    activity_id: int | None = None


class ChatReplyRead(BaseModel):
    reply: str
    citations: list[str] = []
    escalate: bool = False
    escalation_reason: str | None = None
    intent: str | None = None
    plan_id: int | None = None


class CoachMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime | None = None
    intent: str | None = None
    plan_id: int | None = None


class CoachChatResponse(BaseModel):
    provider: str
    model: str
    reply: ChatReplyRead
    citations: list[ScienceCitation] = []
    history: list[CoachMessageRead] = []
    disclaimer: str | None = None
    plan: CoachPlanResponse | None = None


class ApplyChatWeekRequest(BaseModel):
    message_id: int | None = None
    markdown: str | None = Field(default=None, max_length=20000)
    publish: bool = True
    timezone: str | None = Field(default=None, max_length=64)


class CoachChatHistoryResponse(BaseModel):
    messages: list[CoachMessageRead] = []


class CoachPlannedWorkoutRead(BaseModel):
    """Schedule-compatible view of an AI-planned workout.

    Field names deliberately mirror :class:`CorosScheduleItemRead` so the Schedule
    page can render device plans and coach plans through one code path.
    """

    external_id: str
    schedule_date: Date
    title: str | None = None
    sport_type: str | None = None
    duration_min: float | None = None
    distance_m: float | None = None
    day_no: int | None = None
    completed_activity_id: int | None = None
    status: str = "planned"
    completed_activity_name: str | None = None
    completed_activity_provider: str | None = None
    completed_distance_m: float | None = None
    completed_moving_time_s: int | None = None
    source: str = "coach"
    workout_id: int
    plan_id: int | None = None
    session_type: str | None = None
    intensity: str | None = None
    description: str | None = None


class CoachStatusResponse(BaseModel):
    providers_configured: list[str] = []
    active_provider: str | None = None
    active_model: str | None = None
    fallback_provider: str | None = None
    mode: str
    ai_consent: bool = False
    science_chunks: int = 0
    has_active_plan: bool = False
    ai_debug: dict | None = None


class AthleteEventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    date: Date
    priority: str = Field(default="E", pattern="^[ABCDE]$")
    sport_type: str = Field(default="run", max_length=32)
    target_metric: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class AthleteEventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    date: Date | None = None
    priority: str | None = Field(default=None, pattern="^[ABCDE]$")
    sport_type: str | None = Field(default=None, max_length=32)
    target_metric: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=32)
    result_metric: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class AthleteEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: Date
    priority: str
    sport_type: str
    target_metric: str | None = None
    status: str
    result_metric: str | None = None
    notes: str | None = None


class SeasonPhaseRead(BaseModel):
    id: int
    phase_type: str
    start_date: Date
    end_date: Date
    week_count: int
    intent: str | None = None
    volume_bias: float | None = None
    intensity_bias: str | None = None
    long_session_allowed_min: int | None = None
    sort_order: int


class SeasonPlanRead(BaseModel):
    id: int
    start_date: Date
    end_date: Date
    status: str
    template_key: str | None = None
    warnings: list[str] = []
    a_race: AthleteEventRead | None = None
    current_phase: SeasonPhaseRead | None = None
    week_in_phase: int | None = None
    week_intent: dict | None = None
    phases: list[SeasonPhaseRead] = []
    upcoming_events: list[AthleteEventRead] = []


class SeasonGenerateResponse(BaseModel):
    plan: SeasonPlanRead
    message: str = "Season plan generated."


class CyclePeriodLogCreate(BaseModel):
    period_start_date: Date


class CycleContextResponse(BaseModel):
    enabled: bool = False
    available: bool = False
    on_date: str | None = None
    last_period_start: str | None = None
    cycle_length: int | None = None
    day_in_cycle: int | None = None
    phase: str | None = None
    days_to_next_period: int | None = None
    late_luteal: bool = False
    training_note: str | None = None
    message: str | None = None


class EventCompleteRequest(BaseModel):
    ftp_watts: float | None = Field(default=None, ge=50, le=500)
    lthr_bpm: float | None = Field(default=None, ge=90, le=230)
    result_metric: str | None = Field(default=None, max_length=255)


class EventCompleteResponse(BaseModel):
    event_id: int
    status: str
    result_metric: str | None = None
    zones_updated: dict = {}
    protocol: dict = {}
    calibration: dict = {}


class ManualBiometricRequest(BaseModel):
    metric_date: Date
    resting_heart_rate: int | None = Field(default=None, ge=30, le=120)
    heart_rate_variability: float | None = Field(default=None, ge=0, le=300)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_score: float | None = Field(default=None, ge=0, le=100)
    readiness_score: float | None = Field(default=None, ge=0, le=100)
    stress_score: float | None = Field(default=None, ge=0, le=100)


class ManualBiometricResponse(BaseModel):
    metric_date: str
    source_device: str
    merged: dict = {}


class SeasonReplanRequest(BaseModel):
    force: bool = False
    reason: str | None = Field(default=None, max_length=500)
    new_bc_race: bool = False


class SeasonReplanTrigger(BaseModel):
    code: str
    message: str
    severity: str = "info"


class SeasonReplanResponse(BaseModel):
    replanned: bool
    message: str
    plan: SeasonPlanRead | None = None
    triggers: list[SeasonReplanTrigger] = []
    diff: list[dict] = []
    reason: str | None = None
