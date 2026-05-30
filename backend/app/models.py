from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
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
    __tablename__ = "strava_connections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(Integer, ForeignKey("athlete_profiles.id"), nullable=True)
    strava_athlete_id = Column(Integer, nullable=False, unique=True)
    access_token = Column(String(512), nullable=False)
    refresh_token = Column(String(512), nullable=False)
    expires_at = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint(
            "athlete_profile_id",
            "strava_activity_id",
            name="uq_athlete_strava_activity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_profile_id = Column(
        Integer, ForeignKey("athlete_profiles.id"), nullable=False, index=True
    )
    strava_activity_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(512), nullable=False)
    activity_date = Column(DateTime, nullable=False, index=True)
    distance_m = Column(Float, nullable=False, default=0.0)
    moving_time_s = Column(Integer, nullable=False, default=0)
    average_heartrate = Column(Float, nullable=True)
    max_heartrate = Column(Float, nullable=True)
    sport_type = Column(String(128), nullable=True)
    points_file_path = Column(String(1024), nullable=True)
    source_fit_file = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
