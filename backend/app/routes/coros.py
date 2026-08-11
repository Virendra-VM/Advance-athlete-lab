"""COROS OAuth + metrics API routes (JWT-bound)."""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import (
    Activity,
    AthleteProfile,
    CorosCycleSnapshot,
    CorosDevice,
    CorosOAuthPending,
    CorosScheduleItem,
    DailyHealthMetric,
    FitnessAssessment,
    ProviderConnection,
    TrainingLoadSnapshot,
    User,
)
from app.schemas import (
    CorosAuthUrlResponse,
    CorosCallbackRequest,
    CorosConnectionRead,
    CorosConnectionStatus,
    CorosDeviceRead,
    CorosFitnessRead,
    CorosHealthMetricRead,
    CorosHistoryBackfillRequest,
    CorosOverviewResponse,
    CorosScheduleItemRead,
    CorosTrainingLoadRead,
    ImportStartResponse,
    ImportStatusResponse,
    MetricSeriesResponse,
)
from app.services.coros_mcp import (
    CorosMcpError,
    build_authorization_url,
    discover_mcp_auth,
    ensure_oauth_client,
    exchange_code_for_tokens,
    generate_pkce_pair,
)
from app.services.coros_metrics import (
    backfill_metric_history,
    ensure_metric_series,
)
from app.services.coros_sync import (
    get_coros_connection,
    get_sync_status,
    sync_in_background,
)
from app.services.schedule_completion import match_schedule_completions

router = APIRouter(prefix="/coros", tags=["coros"])


def _require_athlete_profile(user: User, db: Session) -> AthleteProfile:
    if not user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    profile = (
        db.query(AthleteProfile)
        .filter(AthleteProfile.id == user.athlete_profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    return profile


def _serialize_schedule_item(
    row: CorosScheduleItem, activity: Activity | None = None
) -> CorosScheduleItemRead:
    return CorosScheduleItemRead(
        external_id=row.external_id,
        schedule_date=row.schedule_date,
        title=row.title,
        sport_type=row.sport_type,
        duration_min=row.duration_min,
        distance_m=row.distance_m,
        day_no=row.day_no,
        completed_activity_id=row.completed_activity_id,
        status="completed" if row.completed_activity_id else "planned",
        completed_activity_name=activity.name if activity else None,
        completed_activity_provider=activity.provider if activity else None,
        completed_distance_m=float(activity.distance_m) if activity else None,
        completed_moving_time_s=int(activity.moving_time_s) if activity else None,
    )


@router.get("/auth", response_model=CorosAuthUrlResponse)
def coros_auth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    try:
        discovery = discover_mcp_auth()
        client_id = ensure_oauth_client(discovery)
        verifier, challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(24)
        pending = CorosOAuthPending(
            state=state,
            athlete_profile_id=profile.id,
            code_verifier=verifier,
            client_id=client_id,
            mcp_resource_url=discovery["resource"],
            authorization_server=discovery["authorization_server"],
            token_endpoint=discovery["token_endpoint"],
        )
        # Clean old pending rows for this athlete
        db.query(CorosOAuthPending).filter(
            CorosOAuthPending.athlete_profile_id == profile.id
        ).delete()
        db.add(pending)
        db.commit()
        authorization_url = build_authorization_url(
            auth_discovery=discovery,
            client_id=client_id,
            state=state,
            code_challenge=challenge,
        )
        return CorosAuthUrlResponse(authorization_url=authorization_url)
    except CorosMcpError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/callback", response_model=CorosConnectionRead)
def coros_callback(
    payload: CorosCallbackRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    pending = (
        db.query(CorosOAuthPending)
        .filter(CorosOAuthPending.state == payload.state)
        .first()
    )
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    if pending.athlete_profile_id != profile.id:
        raise HTTPException(status_code=403, detail="OAuth state does not match user.")

    try:
        token_data = exchange_code_for_tokens(
            token_endpoint=pending.token_endpoint,
            client_id=pending.client_id,
            code=payload.code,
            code_verifier=pending.code_verifier,
            resource=pending.mcp_resource_url,
        )
    except CorosMcpError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    connection = get_coros_connection(db, profile.id)
    if connection is None:
        connection = ProviderConnection(
            athlete_profile_id=profile.id,
            provider="coros",
        )
        db.add(connection)

    connection.access_token = token_data["access_token"]
    connection.refresh_token = token_data.get("refresh_token") or connection.refresh_token
    expires_in = token_data.get("expires_in")
    if expires_in:
        connection.expires_at = int(datetime.now(timezone.utc).timestamp()) + int(expires_in)
    connection.scopes = token_data.get("scope")
    connection.mcp_resource_url = pending.mcp_resource_url
    connection.authorization_server = pending.authorization_server
    connection.meta_json = json.dumps(
        {
            "client_id": pending.client_id,
            "token_endpoint": pending.token_endpoint,
            "token_type": token_data.get("token_type"),
        }
    )
    connection.updated_at = datetime.utcnow()

    db.query(CorosOAuthPending).filter(CorosOAuthPending.id == pending.id).delete()
    profile.coros_onboarding_done = True
    db.commit()
    db.refresh(connection)

    if not get_sync_status(profile.id).get("running"):
        background_tasks.add_task(sync_in_background, profile.id)

    return CorosConnectionRead(
        id=connection.id,
        athlete_profile_id=connection.athlete_profile_id,
        provider=connection.provider,
        external_user_id=connection.external_user_id,
        last_synced_at=connection.last_synced_at,
        created_at=connection.created_at,
    )


@router.get("/status", response_model=CorosConnectionStatus)
def coros_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    if connection is None:
        return CorosConnectionStatus(connected=False)
    return CorosConnectionStatus(
        connected=True,
        external_user_id=connection.external_user_id,
        last_synced_at=connection.last_synced_at,
    )


@router.post("/sync", response_model=ImportStartResponse)
def start_coros_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="No COROS connection found.")
    if get_sync_status(profile.id).get("running"):
        raise HTTPException(status_code=409, detail="A COROS sync is already running.")
    background_tasks.add_task(sync_in_background, profile.id)
    return ImportStartResponse(
        status="started",
        message="COROS sync started in the background.",
    )


@router.get("/sync/status", response_model=ImportStatusResponse)
def coros_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    return ImportStatusResponse(**get_sync_status(profile.id))


@router.delete("/disconnect")
def disconnect_coros(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    if connection:
        db.delete(connection)
        db.commit()
    return {"disconnected": True}


def _serialize_health(row: DailyHealthMetric) -> CorosHealthMetricRead:
    return CorosHealthMetricRead(
        metric_date=row.metric_date,
        sleep_score=row.sleep_score,
        sleep_duration_min=row.sleep_duration_min,
        deep_sleep_pct=row.deep_sleep_pct,
        light_sleep_pct=row.light_sleep_pct,
        rem_sleep_pct=row.rem_sleep_pct,
        awake_min=row.awake_min,
        bedtime=row.bedtime,
        wake_time=row.wake_time,
        nap_duration_min=row.nap_duration_min,
        sleep_avg_hr=row.sleep_avg_hr,
        steps=row.steps,
        calories=row.calories,
        avg_heart_rate=row.avg_heart_rate,
        resting_heart_rate=row.resting_heart_rate,
        stress=row.stress,
        hrv=row.hrv,
        hrv_assessment=row.hrv_assessment,
    )


def _serialize_fitness(row: FitnessAssessment | None) -> CorosFitnessRead | None:
    if row is None:
        return None
    race_preds = {}
    if row.race_preds_json:
        try:
            race_preds = json.loads(row.race_preds_json)
        except json.JSONDecodeError:
            race_preds = {}
    return CorosFitnessRead(
        snapshot_at=row.snapshot_at,
        vo2max=row.vo2max,
        running_performance=row.running_performance,
        threshold_pace=row.threshold_pace,
        race_predictions=race_preds,
        recovery_pct=row.recovery_pct,
        recovery_level=row.recovery_level,
        recovery_full_at=row.recovery_full_at,
    )


def _serialize_load(row: TrainingLoadSnapshot | None) -> CorosTrainingLoadRead | None:
    if row is None:
        return None
    comments = []
    if row.daily_comments_json:
        try:
            comments = json.loads(row.daily_comments_json)
        except json.JSONDecodeError:
            comments = []
    return CorosTrainingLoadRead(
        snapshot_at=row.snapshot_at,
        short_load=row.short_load,
        long_load=row.long_load,
        load_ratio=row.load_ratio,
        daily_comments=comments if isinstance(comments, list) else [comments],
    )


@router.get("/health", response_model=list[CorosHealthMetricRead])
def get_coros_health(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    query = db.query(DailyHealthMetric).filter(
        DailyHealthMetric.athlete_profile_id == profile.id,
        DailyHealthMetric.provider == "coros",
    )
    if from_date:
        query = query.filter(DailyHealthMetric.metric_date >= from_date)
    if to_date:
        query = query.filter(DailyHealthMetric.metric_date <= to_date)
    rows = query.order_by(DailyHealthMetric.metric_date.desc()).limit(90).all()
    return [_serialize_health(row) for row in rows]


@router.get("/fitness", response_model=CorosFitnessRead | None)
def get_coros_fitness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    row = (
        db.query(FitnessAssessment)
        .filter(
            FitnessAssessment.athlete_profile_id == profile.id,
            FitnessAssessment.provider == "coros",
        )
        .order_by(FitnessAssessment.snapshot_at.desc())
        .first()
    )
    return _serialize_fitness(row)


@router.get("/training-load", response_model=CorosTrainingLoadRead | None)
def get_coros_training_load(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    row = (
        db.query(TrainingLoadSnapshot)
        .filter(
            TrainingLoadSnapshot.athlete_profile_id == profile.id,
            TrainingLoadSnapshot.provider == "coros",
        )
        .order_by(TrainingLoadSnapshot.snapshot_at.desc())
        .first()
    )
    return _serialize_load(row)


@router.get("/schedule", response_model=list[CorosScheduleItemRead])
def get_coros_schedule(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    start = from_date or (date.today() - timedelta(days=120))
    end = to_date or (date.today() + timedelta(days=90))
    # Keep planned→completed links fresh for the requested window.
    match_schedule_completions(db, profile.id, from_date=start, to_date=end)
    rows = (
        db.query(CorosScheduleItem)
        .filter(
            CorosScheduleItem.athlete_profile_id == profile.id,
            CorosScheduleItem.schedule_date >= start,
            CorosScheduleItem.schedule_date <= end,
        )
        .order_by(CorosScheduleItem.schedule_date.asc())
        .all()
    )
    activity_ids = [row.completed_activity_id for row in rows if row.completed_activity_id]
    activities = {}
    if activity_ids:
        for activity in db.query(Activity).filter(Activity.id.in_(activity_ids)).all():
            activities[activity.id] = activity
    return [
        _serialize_schedule_item(row, activities.get(row.completed_activity_id))
        for row in rows
    ]


@router.get("/overview", response_model=CorosOverviewResponse)
def get_coros_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    connected = connection is not None

    health_rows = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == profile.id,
            DailyHealthMetric.provider == "coros",
        )
        .order_by(DailyHealthMetric.metric_date.desc())
        .limit(14)
        .all()
    )
    fitness = (
        db.query(FitnessAssessment)
        .filter(
            FitnessAssessment.athlete_profile_id == profile.id,
            FitnessAssessment.provider == "coros",
        )
        .order_by(FitnessAssessment.snapshot_at.desc())
        .first()
    )
    load = (
        db.query(TrainingLoadSnapshot)
        .filter(
            TrainingLoadSnapshot.athlete_profile_id == profile.id,
            TrainingLoadSnapshot.provider == "coros",
        )
        .order_by(TrainingLoadSnapshot.snapshot_at.desc())
        .first()
    )
    schedule = (
        db.query(CorosScheduleItem)
        .filter(
            CorosScheduleItem.athlete_profile_id == profile.id,
            CorosScheduleItem.schedule_date >= date.today() - timedelta(days=7),
            CorosScheduleItem.schedule_date <= date.today() + timedelta(days=21),
        )
        .order_by(CorosScheduleItem.schedule_date.asc())
        .all()
    )
    schedule_activity_ids = [
        row.completed_activity_id for row in schedule if row.completed_activity_id
    ]
    schedule_activities = {}
    if schedule_activity_ids:
        for activity in db.query(Activity).filter(Activity.id.in_(schedule_activity_ids)).all():
            schedule_activities[activity.id] = activity

    today_health = health_rows[0] if health_rows else None
    return CorosOverviewResponse(
        connected=connected,
        last_synced_at=connection.last_synced_at if connection else None,
        today_health=_serialize_health(today_health) if today_health else None,
        health_trend=[_serialize_health(row) for row in health_rows],
        fitness=_serialize_fitness(fitness),
        training_load=_serialize_load(load),
        schedule=[
            _serialize_schedule_item(row, schedule_activities.get(row.completed_activity_id))
            for row in schedule
        ],
        sync_status=get_sync_status(profile.id),
    )


@router.get("/metrics/{metric}", response_model=MetricSeriesResponse)
def get_metric_series(
    metric: str,
    range: str = Query(default="4w"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    try:
        series = ensure_metric_series(
            db,
            profile.id,
            metric,
            range_key=range,
            from_date=from_date,
            to_date=to_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetricSeriesResponse(**series)


@router.post("/metrics/{metric}/history", response_model=MetricSeriesResponse)
def backfill_metric(
    metric: str,
    payload: CorosHistoryBackfillRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    range_key = (payload.range if payload else None) or "3m"
    try:
        series = backfill_metric_history(db, profile.id, metric, range_key)
    except CorosMcpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetricSeriesResponse(**series)


@router.post("/backfill-fit")
def backfill_coros_fit(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download COROS FIT files for recent activities missing timeline streams."""
    from app.services.coros_fit import backfill_coros_fit_for_athlete

    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="No COROS connection found.")
    try:
        return backfill_coros_fit_for_athlete(db, profile.id, connection=connection, limit=limit)
    except CorosMcpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activities/{activity_id}/fit")
def backfill_coros_fit_for_one(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch COROS FIT streams for one activity (or its COROS twin)."""
    from app.services.coros_fit import attach_coros_fit_to_activity
    from app.services.coros_sync import _client_for_connection

    profile = _require_athlete_profile(current_user, db)
    connection = get_coros_connection(db, profile.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="No COROS connection found.")

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_profile_id == profile.id,
        )
        .first()
    )
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found.")

    try:
        client = _client_for_connection(db, connection)
        client.initialize()
        result = attach_coros_fit_to_activity(client, db, connection, activity)
    except CorosMcpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.get("ok") and result.get("reason") not in {
        "already_has_points",
        "target_already_has_points",
    }:
        # Still return payload so UI can show why; not always a hard failure.
        return result
    return result


@router.get("/devices", response_model=list[CorosDeviceRead])
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    rows = (
        db.query(CorosDevice)
        .filter(CorosDevice.athlete_profile_id == profile.id)
        .order_by(CorosDevice.updated_at.desc())
        .all()
    )
    result = []
    for row in rows:
        raw = {}
        if row.raw_json:
            try:
                raw = json.loads(row.raw_json)
            except json.JSONDecodeError:
                raw = {"text": row.raw_json}
        result.append(
            CorosDeviceRead(
                device_id=row.device_id,
                name=row.name,
                firmware=row.firmware,
                raw=raw if isinstance(raw, dict) else {"value": raw},
            )
        )
    return result


@router.get("/cycle/latest")
def latest_cycle(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    row = (
        db.query(CorosCycleSnapshot)
        .filter(CorosCycleSnapshot.athlete_profile_id == profile.id)
        .order_by(CorosCycleSnapshot.snapshot_at.desc())
        .first()
    )
    if row is None:
        return {"available": False, "data": None}
    data = row.raw_json
    try:
        data = json.loads(row.raw_json) if row.raw_json else None
    except json.JSONDecodeError:
        pass
    return {
        "available": True,
        "snapshot_at": row.snapshot_at.isoformat(),
        "data": data,
    }
