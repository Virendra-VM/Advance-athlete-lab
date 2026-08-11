from sqlalchemy import inspect, text

from app.database import engine


def run_migrations() -> None:
    """Add new columns/tables for auth, onboarding, and multi-provider support."""
    # Use a single short transaction so crashed startups don't leave DDL locks open.
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        if "users" not in tables:
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
            tables.add("users")

        if "athlete_profiles" in tables:
            profile_columns = {
                col["name"] for col in inspector.get_columns("athlete_profiles")
            }
            additions = [
                ("avatar_letter", "VARCHAR(8)"),
                ("onboarding_completed", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("strava_onboarding_done", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("coros_onboarding_done", "BOOLEAN NOT NULL DEFAULT FALSE"),
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

        if "activities" in tables:
            activity_columns = {col["name"] for col in inspector.get_columns("activities")}
            if "provider" not in activity_columns:
                conn.execute(
                    text(
                        "ALTER TABLE activities ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'strava'"
                    )
                )
            if "external_activity_id" not in activity_columns:
                conn.execute(
                    text("ALTER TABLE activities ADD COLUMN external_activity_id VARCHAR(128)")
                )
                conn.execute(
                    text(
                        """
                        UPDATE activities
                        SET external_activity_id = CAST(strava_activity_id AS VARCHAR)
                        WHERE external_activity_id IS NULL AND strava_activity_id IS NOT NULL
                        """
                    )
                )
            if "canonical_activity_id" not in activity_columns:
                conn.execute(
                    text(
                        "ALTER TABLE activities ADD COLUMN canonical_activity_id INTEGER REFERENCES activities(id)"
                    )
                )

            conn.execute(
                text(
                    """
                    UPDATE activities
                    SET external_activity_id = CAST(strava_activity_id AS VARCHAR)
                    WHERE (external_activity_id IS NULL OR external_activity_id = '')
                      AND strava_activity_id IS NOT NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE activities
                    SET provider = 'strava'
                    WHERE provider IS NULL OR provider = ''
                    """
                )
            )

            conn.execute(
                text("ALTER TABLE activities DROP CONSTRAINT IF EXISTS uq_athlete_strava_activity")
            )
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'uq_athlete_provider_activity'
                        ) THEN
                            ALTER TABLE activities
                            ADD CONSTRAINT uq_athlete_provider_activity
                            UNIQUE (athlete_profile_id, provider, external_activity_id);
                        END IF;
                    END $$;
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_activities_provider ON activities (provider)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_activities_external_activity_id ON activities (external_activity_id)"
                )
            )

            conn.execute(
                text("ALTER TABLE activities ALTER COLUMN strava_activity_id DROP NOT NULL")
            )

            if "notes" not in activity_columns:
                conn.execute(text("ALTER TABLE activities ADD COLUMN notes TEXT"))

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        if "daily_health_metrics" in tables:
            health_columns = {
                col["name"] for col in inspector.get_columns("daily_health_metrics")
            }
            health_additions = [
                ("bedtime", "VARCHAR(16)"),
                ("wake_time", "VARCHAR(16)"),
                ("nap_duration_min", "DOUBLE PRECISION"),
                ("sleep_avg_hr", "DOUBLE PRECISION"),
            ]
            for column_name, column_type in health_additions:
                if column_name not in health_columns:
                    conn.execute(
                        text(
                            f"ALTER TABLE daily_health_metrics ADD COLUMN {column_name} {column_type}"
                        )
                    )

        if "coros_schedule_items" in tables:
            schedule_columns = {
                col["name"] for col in inspector.get_columns("coros_schedule_items")
            }
            if "completed_activity_id" not in schedule_columns:
                conn.execute(
                    text(
                        """
                        ALTER TABLE coros_schedule_items
                        ADD COLUMN completed_activity_id INTEGER
                        REFERENCES activities(id)
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS ix_coros_schedule_items_completed_activity_id
                        ON coros_schedule_items (completed_activity_id)
                        """
                    )
                )

        if "strava_connections" in tables and "provider_connections" in tables:
            conn.execute(
                text(
                    """
                    INSERT INTO provider_connections (
                        athlete_profile_id,
                        provider,
                        external_user_id,
                        access_token,
                        refresh_token,
                        expires_at,
                        scopes,
                        fit_downloads_today,
                        created_at
                    )
                    SELECT
                        sc.athlete_profile_id,
                        'strava',
                        CAST(sc.strava_athlete_id AS VARCHAR),
                        sc.access_token,
                        sc.refresh_token,
                        sc.expires_at,
                        'read,activity:read_all',
                        0,
                        sc.created_at
                    FROM strava_connections sc
                    WHERE sc.athlete_profile_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM provider_connections pc
                        WHERE pc.athlete_profile_id = sc.athlete_profile_id
                          AND pc.provider = 'strava'
                      )
                    """
                )
            )
