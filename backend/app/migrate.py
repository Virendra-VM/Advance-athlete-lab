from sqlalchemy import inspect, text

from app.database import engine


def run_migrations() -> None:
    """Add new columns/tables for auth and onboarding without Alembic."""
    with engine.connect() as conn:
        inspector = inspect(engine)

        if "users" not in inspector.get_table_names():
            conn.execute(
                text(
                    """
                    CREATE TABLE users (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        athlete_profile_id INTEGER UNIQUE REFERENCES athlete_profiles(id),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"))

        profile_columns = {col["name"] for col in inspector.get_columns("athlete_profiles")}
        additions = [
            ("avatar_letter", "VARCHAR(8)"),
            ("onboarding_completed", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("strava_onboarding_done", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("primary_goal", "TEXT"),
            ("secondary_goal", "TEXT"),
            ("equipment", "TEXT"),
            ("days_per_week", "INTEGER"),
            ("workout_duration_minutes", "INTEGER"),
            ("preferred_workout_time", "VARCHAR(64)"),
            ("injuries_limitations", "TEXT"),
            ("fitness_level", "VARCHAR(64)"),
            ("exercises_hate", "TEXT"),
            ("exercises_love", "TEXT"),
        ]
        for column_name, column_type in additions:
            if column_name not in profile_columns:
                conn.execute(
                    text(
                        f"ALTER TABLE athlete_profiles ADD COLUMN {column_name} {column_type}"
                    )
                )

        conn.commit()
