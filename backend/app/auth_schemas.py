import json
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SEX_VALUES = {"female", "male", "other", "prefer_not"}
INJURY_STATUSES = {"active", "past"}
SPORT_PRIORITIES = {"primary", "secondary"}
RUN_HR_METHODS = {"lthr", "max_hr", "hrr"}
RUN_PACE_METHODS = {"threshold"}
BIKE_POWER_METHODS = {"coggan"}


def _parse_json_field(value):
    """Profile JSON columns are stored as TEXT; expose them as real structures."""
    if value is None or isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            return json.loads(trimmed)
        except json.JSONDecodeError:
            # Legacy comma-separated values.
            return [part.strip() for part in trimmed.split(",") if part.strip()]
    return value


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailVerifyConfirmRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class EmailVerifyStatusResponse(BaseModel):
    email: str
    email_verified: bool
    verification_sent_at: datetime | None = None
    # Present only when no mail transport is configured (local dev).
    dev_verify_token: str | None = None


class InjuryPayload(BaseModel):
    body_region: str = Field(min_length=1, max_length=64)
    condition: str | None = Field(default=None, max_length=255)
    status: str = "past"
    severity: str | None = Field(default=None, max_length=32)
    onset_date: date | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        normalized = (value or "past").strip().lower()
        return normalized if normalized in INJURY_STATUSES else "past"


class InjuryRead(InjuryPayload):
    model_config = ConfigDict(from_attributes=True)

    id: int


class SportPayload(BaseModel):
    sport: str = Field(min_length=1, max_length=64)
    priority: str = "primary"
    experience_level: str | None = Field(default=None, max_length=64)
    weekly_preference_days: int | None = Field(default=None, ge=0, le=7)

    @field_validator("priority")
    @classmethod
    def check_priority(cls, value: str) -> str:
        normalized = (value or "primary").strip().lower()
        return normalized if normalized in SPORT_PRIORITIES else "primary"


class SportRead(SportPayload):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ConsentPayload(BaseModel):
    ai_coaching: bool = False
    health_data: bool = False
    research: bool = False


class ConsentRead(ConsentPayload):
    model_config = ConfigDict(from_attributes=True)

    accepted_at: datetime | None = None


class OnboardingSubmitRequest(BaseModel):
    # Existing (v1) preference answers.
    primary_goal: str
    secondary_goal: str | None = None
    equipment: str
    days_per_week: int = Field(ge=1, le=7)
    workout_duration_minutes: int = Field(ge=15, le=180)
    preferred_workout_time: str
    injuries_limitations: str | None = None
    fitness_level: str
    exercises_hate: str | None = None
    exercises_love: str | None = None

    # Profile v2 additions — all optional so partial intake still completes.
    name: str | None = Field(default=None, max_length=255)
    sex: str | None = None
    date_of_birth: date | None = None
    age: int | None = Field(default=None, ge=13, le=100)
    height_cm: float | None = Field(default=None, ge=90, le=260)
    weight: float | None = Field(default=None, ge=25, le=350)
    blood_type: str | None = Field(default=None, max_length=8)
    units: str | None = None

    training_history_months: int | None = Field(default=None, ge=0, le=1200)
    current_weekly_volume: dict | None = None
    longest_recent_session: str | None = Field(default=None, max_length=255)
    race_prs: str | None = None

    weekly_minutes_budget: int | None = Field(default=None, ge=0, le=3000)
    goal_event_name: str | None = Field(default=None, max_length=255)
    goal_event_date: date | None = None
    goal_metric: str | None = Field(default=None, max_length=255)
    planning_notes: str | None = Field(default=None, max_length=2000)

    ftp_watts: float | None = Field(default=None, ge=50, le=500)
    lthr_bpm: float | None = Field(default=None, ge=90, le=230)
    max_hr_bpm: float | None = Field(default=None, ge=120, le=230)
    bike_lthr_bpm: float | None = Field(default=None, ge=90, le=230)
    resting_hr_bpm: float | None = Field(default=None, ge=30, le=120)
    threshold_pace: str | None = Field(default=None, max_length=32)
    lt1_pace: str | None = Field(default=None, max_length=32)
    marathon_pace: str | None = Field(default=None, max_length=32)
    css_pace: str | None = Field(default=None, max_length=32)
    threshold_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    lt1_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    marathon_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    css_sec_per_100m: float | None = Field(default=None, ge=40, le=300)
    vo2max: float | None = Field(default=None, ge=20, le=90)
    zone_run_hr_method: str | None = None
    zone_bike_power_method: str | None = None
    zone_run_pace_method: str | None = None

    sports: list[SportPayload] | None = None
    injuries: list[InjuryPayload] | None = None
    consents: ConsentPayload | None = None

    @field_validator("sex")
    @classmethod
    def check_sex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        return normalized if normalized in SEX_VALUES else "prefer_not"

    @field_validator("units")
    @classmethod
    def check_units(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return "imperial" if value.strip().lower() == "imperial" else "metric"


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    age: int | None = Field(default=None, ge=13, le=100)
    weight: float | None = Field(default=None, ge=25, le=350)
    avatar_letter: str | None = Field(default=None, min_length=1, max_length=1)
    primary_goal: str | None = None
    secondary_goal: str | None = None
    equipment: str | None = None
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    workout_duration_minutes: int | None = Field(default=None, ge=15, le=180)
    preferred_workout_time: str | None = None
    injuries_limitations: str | None = None
    fitness_level: str | None = None
    exercises_hate: str | None = None
    exercises_love: str | None = None

    # Profile v2
    sex: str | None = None
    date_of_birth: date | None = None
    height_cm: float | None = Field(default=None, ge=90, le=260)
    blood_type: str | None = Field(default=None, max_length=8)
    units: str | None = None
    training_history_months: int | None = Field(default=None, ge=0, le=1200)
    current_weekly_volume: dict | None = None
    longest_recent_session: str | None = Field(default=None, max_length=255)
    race_prs: str | None = None
    weekly_minutes_budget: int | None = Field(default=None, ge=0, le=3000)
    goal_event_name: str | None = Field(default=None, max_length=255)
    goal_event_date: date | None = None
    goal_metric: str | None = Field(default=None, max_length=255)
    planning_notes: str | None = Field(default=None, max_length=2000)
    sports: list[SportPayload] | None = None
    injuries: list[InjuryPayload] | None = None
    consents: ConsentPayload | None = None

    ftp_watts: float | None = Field(default=None, ge=50, le=500)
    lthr_bpm: float | None = Field(default=None, ge=90, le=230)
    max_hr_bpm: float | None = Field(default=None, ge=120, le=230)
    bike_lthr_bpm: float | None = Field(default=None, ge=90, le=230)
    resting_hr_bpm: float | None = Field(default=None, ge=30, le=120)
    threshold_pace: str | None = Field(default=None, max_length=32)
    lt1_pace: str | None = Field(default=None, max_length=32)
    marathon_pace: str | None = Field(default=None, max_length=32)
    css_pace: str | None = Field(default=None, max_length=32)
    threshold_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    lt1_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    marathon_pace_sec_per_km: float | None = Field(default=None, ge=120, le=900)
    css_sec_per_100m: float | None = Field(default=None, ge=40, le=300)
    vo2max: float | None = Field(default=None, ge=20, le=90)
    zone_run_hr_method: str | None = None
    zone_bike_power_method: str | None = None
    zone_run_pace_method: str | None = None
    cycle_tracking_enabled: bool | None = None
    cycle_length_manual: int | None = Field(default=None, ge=18, le=45)

    @field_validator("sex")
    @classmethod
    def check_sex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        return normalized if normalized in SEX_VALUES else "prefer_not"

    @field_validator("units")
    @classmethod
    def check_units(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return "imperial" if value.strip().lower() == "imperial" else "metric"

    @field_validator("zone_run_hr_method")
    @classmethod
    def check_run_hr_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized if normalized in RUN_HR_METHODS else "lthr"

    @field_validator("zone_bike_power_method")
    @classmethod
    def check_bike_power_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized if normalized in BIKE_POWER_METHODS else "coggan"

    @field_validator("zone_run_pace_method")
    @classmethod
    def check_run_pace_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized if normalized in RUN_PACE_METHODS else "threshold"


class ZoneBandRead(BaseModel):
    name: str
    low_w: int | None = None
    high_w: int | None = None
    low_bpm: int | None = None
    high_bpm: int | None = None
    low_pace: str | None = None
    high_pace: str | None = None
    relative_to: str | None = None


class TrainingZonesResponse(BaseModel):
    anchors: dict
    methods: dict
    power_zones: list[ZoneBandRead] = []
    hr_zones: list[ZoneBandRead] = []
    run_pace_zones: list[ZoneBandRead] = []
    swim_pace_zones: list[ZoneBandRead] = []


class TestSuggestionRead(BaseModel):
    id: str
    kind: str
    field: str
    value: float
    confidence: str
    reason: str
    activity_id: int
    activity_name: str | None = None
    activity_date: str | None = None


class AnchorNudgeRead(BaseModel):
    code: str
    severity: str = "info"
    message: str
    action: str | None = None


class PhysiologyEstimateResponse(BaseModel):
    suggestions: dict = {}
    sources: dict = {}
    skipped: dict = {}
    activity_count: int = 0
    test_suggestions: list[TestSuggestionRead] = []
    nudges: list[AnchorNudgeRead] = []
    zones: TrainingZonesResponse | None = None


class PhysiologyEstimateApplyResponse(BaseModel):
    applied: dict = {}
    sources: dict = {}
    skipped: dict = {}
    activity_count: int = 0
    test_suggestions: list[TestSuggestionRead] = []
    nudges: list[AnchorNudgeRead] = []
    zones: TrainingZonesResponse


class TestSuggestionApplyResponse(BaseModel):
    applied: dict = {}
    sources: dict = {}
    suggestion: TestSuggestionRead
    zones: TrainingZonesResponse


class AthleteProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    weight: float
    fitness_goals: str | None = None
    medical_history: str | None = None
    avatar_letter: str | None = None
    onboarding_completed: bool = False
    strava_onboarding_done: bool = False
    coros_onboarding_done: bool = False
    primary_goal: str | None = None
    secondary_goal: str | None = None
    equipment: str | None = None
    days_per_week: int | None = None
    workout_duration_minutes: int | None = None
    preferred_workout_time: str | None = None
    injuries_limitations: str | None = None
    fitness_level: str | None = None
    exercises_hate: str | None = None
    exercises_love: str | None = None

    # Profile v2
    height_cm: float | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    blood_type: str | None = None
    training_history_months: int | None = None
    current_weekly_volume: dict | list | None = None
    longest_recent_session: str | None = None
    race_prs: str | None = None
    weekly_minutes_budget: int | None = None
    primary_sports: list | None = None
    secondary_sports: list | None = None
    goal_event_name: str | None = None
    goal_event_date: date | None = None
    goal_metric: str | None = None
    planning_notes: str | None = None
    units: str = "metric"
    baseline_confirmed_at: datetime | None = None
    ftp_watts: float | None = None
    lthr_bpm: float | None = None
    max_hr_bpm: float | None = None
    bike_lthr_bpm: float | None = None
    resting_hr_bpm: float | None = None
    threshold_pace_sec_per_km: float | None = None
    threshold_pace_display: str | None = None
    lt1_pace_sec_per_km: float | None = None
    lt1_pace_display: str | None = None
    marathon_pace_sec_per_km: float | None = None
    marathon_pace_display: str | None = None
    css_sec_per_100m: float | None = None
    css_pace_display: str | None = None
    vo2max: float | None = None
    zone_run_hr_method: str = "lthr"
    zone_bike_power_method: str = "coggan"
    zone_run_pace_method: str = "threshold"
    ftp_source: str | None = None
    ftp_estimated_watts: float | None = None
    cycle_tracking_enabled: bool = False
    cycle_length_manual: int | None = None

    sports: list[SportRead] = []
    injuries: list[InjuryRead] = []
    consents: ConsentRead | None = None
    profile_completeness: int = 0

    @field_validator("current_weekly_volume", "primary_sports", "secondary_sports", mode="before")
    @classmethod
    def parse_json_columns(cls, value):
        return _parse_json_field(value)


class UserResponse(BaseModel):
    id: int
    email: str
    email_verified: bool = False
    profile: AthleteProfileResponse | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
