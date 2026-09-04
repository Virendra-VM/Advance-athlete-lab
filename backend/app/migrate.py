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

        if "users" in tables:
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            user_additions = [
                ("email_verified_at", "TIMESTAMP"),
                ("email_verify_token_hash", "VARCHAR(255)"),
                ("email_verify_sent_at", "TIMESTAMP"),
            ]
            for column_name, column_type in user_additions:
                if column_name not in user_columns:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                    )

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
                # Profile v2
                ("height_cm", "DOUBLE PRECISION"),
                ("sex", "VARCHAR(32)"),
                ("date_of_birth", "DATE"),
                ("blood_type", "VARCHAR(8)"),
                ("training_history_months", "INTEGER"),
                ("current_weekly_volume", "TEXT"),
                ("longest_recent_session", "VARCHAR(255)"),
                ("race_prs", "TEXT"),
                ("weekly_minutes_budget", "INTEGER"),
                ("primary_sports", "TEXT"),
                ("secondary_sports", "TEXT"),
                ("goal_event_name", "VARCHAR(255)"),
                ("goal_event_date", "DATE"),
                ("goal_metric", "VARCHAR(255)"),
                ("units", "VARCHAR(16) NOT NULL DEFAULT 'metric'"),
                ("baseline_confirmed_at", "TIMESTAMP"),
                ("ftp_watts", "DOUBLE PRECISION"),
                ("lthr_bpm", "DOUBLE PRECISION"),
                ("max_hr_bpm", "DOUBLE PRECISION"),
                ("ftp_source", "VARCHAR(32)"),
                ("ftp_estimated_watts", "DOUBLE PRECISION"),
                ("ftp_estimated_at", "TIMESTAMP"),
                ("cycle_tracking_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("cycle_length_manual", "INTEGER"),
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

            # Blank/NULL external ids collide under UNIQUE; give each row a stable unique value.
            conn.execute(
                text(
                    """
                    UPDATE activities
                    SET external_activity_id = 'legacy-' || id::text
                    WHERE external_activity_id IS NULL
                       OR BTRIM(external_activity_id) = ''
                    """
                )
            )

            conn.execute(
                text("ALTER TABLE activities DROP CONSTRAINT IF EXISTS uq_athlete_strava_activity")
            )

            # Resolve duplicate (athlete, provider, external_id) groups before UNIQUE.
            # Keep the row with stream points when possible, else the lowest id.
            has_unique = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_athlete_provider_activity'
                    LIMIT 1
                    """
                )
            ).first()
            if has_unique is None:
                conn.execute(
                    text(
                        """
                        CREATE TEMP TABLE _activity_dedupe_map ON COMMIT DROP AS
                        WITH ranked AS (
                            SELECT
                                id,
                                FIRST_VALUE(id) OVER (
                                    PARTITION BY athlete_profile_id, provider, external_activity_id
                                    ORDER BY
                                        CASE
                                            WHEN points_file_path IS NOT NULL
                                             AND points_file_path <> '' THEN 0
                                            ELSE 1
                                        END,
                                        id ASC
                                ) AS keep_id,
                                ROW_NUMBER() OVER (
                                    PARTITION BY athlete_profile_id, provider, external_activity_id
                                    ORDER BY
                                        CASE
                                            WHEN points_file_path IS NOT NULL
                                             AND points_file_path <> '' THEN 0
                                            ELSE 1
                                        END,
                                        id ASC
                                ) AS rn
                            FROM activities
                        )
                        SELECT id AS drop_id, keep_id
                        FROM ranked
                        WHERE rn > 1
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE activities AS a
                        SET canonical_activity_id = m.keep_id
                        FROM _activity_dedupe_map AS m
                        WHERE a.canonical_activity_id = m.drop_id
                        """
                    )
                )
                if "coros_schedule_items" in tables:
                    schedule_columns = {
                        col["name"]
                        for col in inspector.get_columns("coros_schedule_items")
                    }
                    if "completed_activity_id" in schedule_columns:
                        conn.execute(
                            text(
                                """
                                UPDATE coros_schedule_items AS s
                                SET completed_activity_id = m.keep_id
                                FROM _activity_dedupe_map AS m
                                WHERE s.completed_activity_id = m.drop_id
                                """
                            )
                        )
                conn.execute(
                    text(
                        """
                        UPDATE activities AS a
                        SET canonical_activity_id = NULL
                        FROM _activity_dedupe_map AS m
                        WHERE a.id = m.drop_id
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM activities AS a
                        USING _activity_dedupe_map AS m
                        WHERE a.id = m.drop_id
                        """
                    )
                )

                conn.execute(
                    text(
                        """
                        ALTER TABLE activities
                        ADD CONSTRAINT uq_athlete_provider_activity
                        UNIQUE (athlete_profile_id, provider, external_activity_id)
                        """
                    )
                )

            conn.execute(
                text(
                    "ALTER TABLE activities ALTER COLUMN external_activity_id SET NOT NULL"
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
            activity_columns = {
                col["name"] for col in inspector.get_columns("activities")
            }
            detail_additions = [
                ("detail_json", "TEXT"),
                ("detail_fetched_at", "TIMESTAMP"),
                ("sport_type_code", "VARCHAR(64)"),
            ]
            for column_name, column_type in detail_additions:
                if column_name not in activity_columns:
                    conn.execute(
                        text(
                            f"ALTER TABLE activities ADD COLUMN {column_name} {column_type}"
                        )
                    )

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
                ("deep_sleep_min", "DOUBLE PRECISION"),
                ("light_sleep_min", "DOUBLE PRECISION"),
                ("rem_sleep_min", "DOUBLE PRECISION"),
                ("awake_count", "DOUBLE PRECISION"),
                ("main_sleep_min", "DOUBLE PRECISION"),
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

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "activity_notes" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE activity_notes (
                        id SERIAL PRIMARY KEY,
                        activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        body TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_activity_notes_activity_id ON activity_notes (activity_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_activity_notes_athlete_profile_id ON activity_notes (athlete_profile_id)"
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO activity_notes (activity_id, athlete_profile_id, body, created_at, updated_at)
                    SELECT
                        a.id,
                        a.athlete_profile_id,
                        a.notes,
                        COALESCE(a.created_at, NOW()),
                        COALESCE(a.created_at, NOW())
                    FROM activities a
                    WHERE a.notes IS NOT NULL
                      AND BTRIM(a.notes) <> ''
                      AND NOT EXISTS (
                        SELECT 1 FROM activity_notes n WHERE n.activity_id = a.id
                      )
                    """
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "training_plans" in tables:
            plan_columns = {col["name"] for col in inspector.get_columns("training_plans")}
            if "published_at" not in plan_columns:
                conn.execute(text("ALTER TABLE training_plans ADD COLUMN published_at TIMESTAMP"))

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "daily_advice_snapshots" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE daily_advice_snapshots (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        advice_date DATE NOT NULL,
                        fingerprint VARCHAR(64) NOT NULL,
                        payload_json TEXT NOT NULL,
                        provider VARCHAR(32),
                        model VARCHAR(128),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_athlete_advice_date UNIQUE (athlete_profile_id, advice_date)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_daily_advice_snapshots_athlete_profile_id "
                    "ON daily_advice_snapshots (athlete_profile_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_daily_advice_snapshots_advice_date "
                    "ON daily_advice_snapshots (advice_date)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "weekly_advice_snapshots" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE weekly_advice_snapshots (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        week_start DATE NOT NULL,
                        topic VARCHAR(32) NOT NULL DEFAULT 'volume',
                        fingerprint VARCHAR(64) NOT NULL,
                        payload_json TEXT NOT NULL,
                        provider VARCHAR(32),
                        model VARCHAR(128),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_athlete_week_brief_topic UNIQUE (athlete_profile_id, week_start, topic)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_weekly_advice_snapshots_athlete_profile_id "
                    "ON weekly_advice_snapshots (athlete_profile_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_weekly_advice_snapshots_week_start "
                    "ON weekly_advice_snapshots (week_start)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "weekly_advice_snapshots" in tables:
            week_columns = {col["name"] for col in inspector.get_columns("weekly_advice_snapshots")}
            if "topic" not in week_columns:
                conn.execute(
                    text(
                        "ALTER TABLE weekly_advice_snapshots "
                        "ADD COLUMN topic VARCHAR(32) NOT NULL DEFAULT 'volume'"
                    )
                )
            unique_names = {
                item["name"] for item in inspector.get_unique_constraints("weekly_advice_snapshots")
            }
            if "uq_athlete_week_brief" in unique_names:
                conn.execute(
                    text("ALTER TABLE weekly_advice_snapshots DROP CONSTRAINT uq_athlete_week_brief")
                )
            inspector = inspect(conn)
            unique_names = {
                item["name"] for item in inspector.get_unique_constraints("weekly_advice_snapshots")
            }
            if "uq_athlete_week_brief_topic" not in unique_names:
                conn.execute(
                    text(
                        """
                        ALTER TABLE weekly_advice_snapshots
                        ADD CONSTRAINT uq_athlete_week_brief_topic
                        UNIQUE (athlete_profile_id, week_start, topic)
                        """
                    )
                )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "athlete_events" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE athlete_events (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        name VARCHAR(255) NOT NULL,
                        event_date DATE NOT NULL,
                        priority VARCHAR(1) NOT NULL DEFAULT 'E',
                        sport_type VARCHAR(32) NOT NULL DEFAULT 'run',
                        target_metric VARCHAR(255),
                        status VARCHAR(32) NOT NULL DEFAULT 'planned',
                        result_metric VARCHAR(255),
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_athlete_events_profile "
                    "ON athlete_events (athlete_profile_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_athlete_events_date "
                    "ON athlete_events (event_date)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "season_plans" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE season_plans (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        a_race_event_id INTEGER REFERENCES athlete_events(id),
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        template_key VARCHAR(64),
                        warnings_json TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_season_plans_profile "
                    "ON season_plans (athlete_profile_id)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "season_phases" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE season_phases (
                        id SERIAL PRIMARY KEY,
                        season_plan_id INTEGER NOT NULL REFERENCES season_plans(id) ON DELETE CASCADE,
                        phase_type VARCHAR(32) NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        week_count INTEGER NOT NULL DEFAULT 1,
                        intent TEXT,
                        volume_bias DOUBLE PRECISION,
                        intensity_bias VARCHAR(32),
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_season_phases_plan "
                    "ON season_phases (season_plan_id)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "athlete_biometrics" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE athlete_biometrics (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        metric_date DATE NOT NULL,
                        resting_heart_rate INTEGER,
                        heart_rate_variability DOUBLE PRECISION,
                        sleep_seconds INTEGER,
                        sleep_score DOUBLE PRECISION,
                        readiness_score DOUBLE PRECISION,
                        stress_score DOUBLE PRECISION,
                        temperature_deviation DOUBLE PRECISION,
                        source_device VARCHAR(32) NOT NULL DEFAULT 'coros',
                        raw_json TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_athlete_biometric_date UNIQUE (athlete_profile_id, metric_date)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_athlete_biometrics_profile "
                    "ON athlete_biometrics (athlete_profile_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_athlete_biometrics_date "
                    "ON athlete_biometrics (metric_date)"
                )
            )

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "cycle_period_logs" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE cycle_period_logs (
                        id SERIAL PRIMARY KEY,
                        athlete_profile_id INTEGER NOT NULL REFERENCES athlete_profiles(id),
                        period_start_date DATE NOT NULL,
                        source VARCHAR(32) NOT NULL DEFAULT 'manual',
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_cycle_period_start UNIQUE (athlete_profile_id, period_start_date)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_cycle_period_logs_profile "
                    "ON cycle_period_logs (athlete_profile_id)"
                )
            )

        inspector = inspect(conn)
        if "season_plans" in inspector.get_table_names():
            season_plan_cols = {col["name"] for col in inspector.get_columns("season_plans")}
            if "last_replan_at" not in season_plan_cols:
                conn.execute(text("ALTER TABLE season_plans ADD COLUMN last_replan_at TIMESTAMP"))
            if "last_replan_triggers_json" not in season_plan_cols:
                conn.execute(
                    text("ALTER TABLE season_plans ADD COLUMN last_replan_triggers_json TEXT")
                )
