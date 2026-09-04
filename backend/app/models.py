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
    # Soft email verification: never blocks onboarding or app access.
    email_verified_at = Column(DateTime, nullable=True)
    email_verify_token_hash = Column(String(255), nullable=True)
    email_verify_sent_at = Column(DateTime, nullable=True)
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

    # --- Profile v2: body + demographics ---
    height_cm = Column(Float, nullable=True)
    sex = Column(String(32), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    # Optional and sensitive; never required to finish onboarding.
    blood_type = Column(String(8), nullable=True)

    # --- Profile v2: fitness snapshot ---
    training_history_months = Column(Integer, nullable=True)
    current_weekly_volume = Column(Text, nullable=True)  # JSON keyed by sport
    longest_recent_session = Column(String(255), nullable=True)
    race_prs = Column(Text, nullable=True)

    # --- Profile v2: time budget + sports + goal event ---
    weekly_minutes_budget = Column(Integer, nullable=True)
    primary_sports = Column(Text, nullable=True)  # JSON list
    secondary_sports = Column(Text, nullable=True)  # JSON list
    goal_event_name = Column(String(255), nullable=True)
    goal_event_date = Column(Date, nullable=True)
    goal_metric = Column(String(255), nullable=True)

    # --- Profile v2: presentation ---
    units = Column(String(16), nullable=False, default="metric")
    baseline_confirmed_at = Column(DateTime, nullable=True)

    # --- Physiology anchors (cycling/run intensity) ---
    ftp_watts = Column(Float, nullable=True)
    lthr_bpm = Column(Float, nullable=True)
    max_hr_bpm = Column(Float, nullable=True)
    ftp_source = Column(String(32), nullable=True)  # manual | estimated
    ftp_estimated_watts = Column(Float, nullable=True)
    ftp_estimated_at = Column(DateTime, nullable=True)


class AthleteInjury(Base):
    """Structured injury history so plan generation can filter contraindications."""

    __tablename__ = "athlete_injuries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    body_region = Column(String(64), nullable=False)
    condition = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="past")  # active | past
    severity = Column(String(32), nullable=True)  # mild | moderate | severe
    onset_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AthleteSport(Base):
    __tablename__ = "athlete_sports"
    __table_args__ = (
        UniqueConstraint("athlete_profile_id", "sport", name="uq_athlete_sport"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    sport = Column(String(64), nullable=False)
    priority = Column(String(16), nullable=False, default="primary")  # primary | secondary
    experience_level = Column(String(64), nullable=True)
    weekly_preference_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AthleteConsent(Base):
    __tablename__ = "athlete_consents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer,
        ForeignKey("athlete_profiles.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_coaching = Column(Boolean, nullable=False, default=False)
    health_data = Column(Boolean, nullable=False, default=False)
    research = Column(Boolean, nullable=False, default=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    # Normalized COROS/Strava detail (laps, exercises, zones, summary extras).
    detail_json = Column(Text, nullable=True)
    detail_fetched_at = Column(DateTime, nullable=True)
    # Optional COROS numeric sport type code for getActivityDetail.
    sport_type_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActivityNote(Base):
    __tablename__ = "activity_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id"), nullable=False, index=True
    )
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
    deep_sleep_min = Column(Float, nullable=True)
    light_sleep_min = Column(Float, nullable=True)
    rem_sleep_min = Column(Float, nullable=True)
    awake_min = Column(Float, nullable=True)
    awake_count = Column(Float, nullable=True)
    main_sleep_min = Column(Float, nullable=True)
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


class ScienceSource(Base):
    """Citable provenance for every knowledge chunk fed to the AI coach."""

    __tablename__ = "science_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    authors = Column(String(512), nullable=True)
    year = Column(Integer, nullable=True)
    publisher = Column(String(255), nullable=True)
    license = Column(String(128), nullable=True)
    url = Column(String(1024), nullable=True)
    source_type = Column(String(64), nullable=False, default="guideline")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScienceChunk(Base):
    __tablename__ = "science_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_key", name="uq_science_source_chunk"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("science_sources.id"), nullable=False, index=True)
    chunk_key = Column(String(128), nullable=False)
    heading = Column(String(512), nullable=True)
    body = Column(Text, nullable=False)
    sport_tags = Column(String(512), nullable=True)  # comma separated
    topic_tags = Column(String(512), nullable=True)  # comma separated
    audience = Column(String(64), nullable=True)  # endurance | strength | shared
    # Reserved for pgvector migration; lexical retrieval works without it.
    embedding_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingPlan(Base):
    """AI-generated training week persisted so Schedule can render it."""

    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    week_start = Column(Date, nullable=False, index=True)
    title = Column(String(512), nullable=True)
    summary = Column(Text, nullable=True)
    focus = Column(String(255), nullable=True)
    provider = Column(String(32), nullable=True)
    model = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")  # active | superseded
    published_at = Column(DateTime, nullable=True)  # set when the athlete adds the week to Schedule
    safety_notes = Column(Text, nullable=True)  # JSON list from validator
    citations = Column(Text, nullable=True)  # JSON list of science source slugs
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlannedWorkout(Base):
    __tablename__ = "planned_workouts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    training_plan_id = Column(
        Integer, ForeignKey("training_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    workout_date = Column(Date, nullable=False, index=True)
    sport = Column(String(64), nullable=True)
    title = Column(String(512), nullable=True)
    session_type = Column(String(64), nullable=True)  # easy | tempo | intervals | strength | rest
    duration_min = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)
    intensity = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    structure_json = Column(Text, nullable=True)
    completed_activity_id = Column(
        Integer, ForeignKey("activities.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoachMessage(Base):
    """Persistent coach chat so the AI keeps cross-session memory."""

    __tablename__ = "coach_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)
    provider = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DailyAdviceSnapshot(Base):
    """One saved Today brief per athlete per local date.

    Regenerated only when the athlete hits Refresh, or when health / recovery /
    training signals that feed the brief have changed.
    """

    __tablename__ = "daily_advice_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "advice_date",
            name="uq_athlete_advice_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    advice_date = Column(Date, nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    provider = Column(String(32), nullable=True)
    model = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeeklyAdviceSnapshot(Base):
    """One saved Week brief per athlete per Monday week-start per topic.

    Topics: ``volume`` (distance ACWR) and ``load`` (COROS effort). Regenerated
    on Refresh, or when that topic's signals / recovery / plan change.
    """

    __tablename__ = "weekly_advice_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "week_start",
            "topic",
            name="uq_athlete_week_brief_topic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    week_start = Column(Date, nullable=False, index=True)
    topic = Column(String(32), nullable=False, default="volume")
    fingerprint = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    provider = Column(String(32), nullable=True)
    model = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
