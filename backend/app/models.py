from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), unique=True, nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    fitness_goals = Column(Text, nullable=True)
    medical_history = Column(Text, nullable=True)
    avatar_letter = Column(String(8), nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    strava_onboarding_done = Column(Boolean, nullable=False, default=False)
    coros_onboarding_done = Column(Boolean, nullable=False, default=False)
    primary_goal = Column(Text, nullable=True)
    secondary_goal = Column(Text, nullable=True)
    equipment = Column(Text, nullable=True)
    days_per_week = Column(Integer, nullable=True)
    workout_duration_minutes = Column(Integer, nullable=True)
    preferred_workout_time = Column(String(64), nullable=True)
    injuries_limitations = Column(Text, nullable=True)
    fitness_level = Column(String(64), nullable=True)
    exercises_hate = Column(Text, nullable=True)
    exercises_love = Column(Text, nullable=True)


class StravaConnection(Base):
    """Legacy Strava-only table; preferred path is ProviderConnection."""

    __tablename__ = "strava_connections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(Integer, ForeignKey("athlete_profiles.id"), nullable=True)
    strava_athlete_id = Column(Integer, nullable=False, unique=True)
    access_token = Column(String(512), nullable=False)
    refresh_token = Column(String(512), nullable=False)
    expires_at = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "provider",
            name="uq_athlete_provider_connection",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    provider = Column(String(32), nullable=False, index=True)
    external_user_id = Column(String(128), nullable=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(Integer, nullable=True)
    scopes = Column(String(512), nullable=True)
    mcp_resource_url = Column(String(512), nullable=True)
    authorization_server = Column(String(512), nullable=True)
    fit_downloads_today = Column(Integer, nullable=False, default=0)
    fit_downloads_day = Column(Date, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "provider",
            "external_activity_id",
            name="uq_athlete_provider_activity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    provider = Column(String(32), nullable=False, default="strava", index=True)
    external_activity_id = Column(String(128), nullable=False, index=True)
    # Kept for Strava backward compatibility; mirrors external_activity_id for Strava rows.
    strava_activity_id = Column(BigInteger, nullable=True, index=True)
    canonical_activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    name = Column(String(512), nullable=False)
    activity_date = Column(DateTime, nullable=False, index=True)
    distance_m = Column(Float, nullable=False, default=0.0)
    moving_time_s = Column(Integer, nullable=False, default=0)
    average_heartrate = Column(Float, nullable=True)
    max_heartrate = Column(Float, nullable=True)
    sport_type = Column(String(128), nullable=True)
    points_file_path = Column(String(1024), nullable=True)
    source_fit_file = Column(String(512), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DailyHealthMetric(Base):
    __tablename__ = "daily_health_metrics"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "provider",
            "metric_date",
            name="uq_athlete_provider_health_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    provider = Column(String(32), nullable=False, default="coros")
    metric_date = Column(Date, nullable=False, index=True)
    sleep_score = Column(Float, nullable=True)
    sleep_duration_min = Column(Float, nullable=True)
    deep_sleep_pct = Column(Float, nullable=True)
    light_sleep_pct = Column(Float, nullable=True)
    rem_sleep_pct = Column(Float, nullable=True)
    awake_min = Column(Float, nullable=True)
    bedtime = Column(String(16), nullable=True)
    wake_time = Column(String(16), nullable=True)
    nap_duration_min = Column(Float, nullable=True)
    sleep_avg_hr = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    calories = Column(Float, nullable=True)
    avg_heart_rate = Column(Float, nullable=True)
    resting_heart_rate = Column(Float, nullable=True)
    stress = Column(Float, nullable=True)
    hrv = Column(Float, nullable=True)
    hrv_assessment = Column(String(128), nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FitnessAssessment(Base):
    __tablename__ = "fitness_assessments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    provider = Column(String(32), nullable=False, default="coros")
    snapshot_at = Column(DateTime, nullable=False, index=True)
    vo2max = Column(Float, nullable=True)
    running_performance = Column(Float, nullable=True)
    threshold_pace = Column(String(64), nullable=True)
    race_preds_json = Column(Text, nullable=True)
    recovery_pct = Column(Float, nullable=True)
    recovery_level = Column(String(64), nullable=True)
    recovery_full_at = Column(String(128), nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TrainingLoadSnapshot(Base):
    __tablename__ = "training_load_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    provider = Column(String(32), nullable=False, default="coros")
    snapshot_at = Column(DateTime, nullable=False, index=True)
    short_load = Column(Float, nullable=True)
    long_load = Column(Float, nullable=True)
    load_ratio = Column(Float, nullable=True)
    daily_comments_json = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CorosScheduleItem(Base):
    __tablename__ = "coros_schedule_items"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "external_id",
            name="uq_athlete_coros_schedule_item",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    external_id = Column(String(128), nullable=False)
    schedule_date = Column(Date, nullable=False, index=True)
    title = Column(String(512), nullable=True)
    sport_type = Column(String(128), nullable=True)
    duration_min = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)
    day_no = Column(Integer, nullable=True)
    id_in_plan = Column(String(128), nullable=True)
    completed_activity_id = Column(
        Integer, ForeignKey("activities.id"), nullable=True, index=True
    )
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CorosOAuthPending(Base):
    """Short-lived PKCE state for COROS MCP OAuth."""

    __tablename__ = "coros_oauth_pending"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state = Column(String(128), unique=True, nullable=False, index=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    code_verifier = Column(String(128), nullable=False)
    client_id = Column(String(255), nullable=False)
    mcp_resource_url = Column(String(512), nullable=False)
    authorization_server = Column(String(512), nullable=False)
    token_endpoint = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CorosDevice(Base):
    __tablename__ = "coros_devices"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "device_id",
            name="uq_athlete_coros_device",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    device_id = Column(String(128), nullable=False)
    name = Column(String(255), nullable=True)
    firmware = Column(String(128), nullable=True)
    raw_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CorosCycleSnapshot(Base):
    """Opt-in menstrual cycle snapshot from COROS MCP."""

    __tablename__ = "coros_cycle_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    snapshot_at = Column(DateTime, nullable=False, index=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
