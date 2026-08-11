from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import (
    STRAVA_AUTHORIZE_URL,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REDIRECT_URI,
    STRAVA_SCOPES,
    STRAVA_TOKEN_URL,
)
from app.database import get_db
from app.models import StravaConnection
from app.schemas import (
    ImportStartResponse,
    ImportStatusResponse,
    StravaAuthUrlResponse,
    StravaCallbackRequest,
    StravaConnectionRead,
    StravaConnectionStatus,
)
from app.services.strava_sync import (
    backfill_streams_for_athlete,
    get_sync_status,
    sync_activities_in_background,
)

router = APIRouter(prefix="/strava", tags=["strava"])


def _require_strava_config() -> None:
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Strava OAuth is not configured. Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET.",
        )


@router.get("/auth", response_model=StravaAuthUrlResponse)
def strava_auth(
    athlete_profile_id: int | None = Query(default=None),
):
    _require_strava_config()

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": STRAVA_REDIRECT_URI,
        "approval_prompt": "force",
        "scope": STRAVA_SCOPES,
    }
    if athlete_profile_id is not None:
        params["state"] = str(athlete_profile_id)

    authorization_url = f"{STRAVA_AUTHORIZE_URL}?{urlencode(params)}"
    return StravaAuthUrlResponse(authorization_url=authorization_url)


@router.post("/callback", response_model=StravaConnectionRead)
def strava_callback(
    payload: StravaCallbackRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    _require_strava_config()

    try:
        response = httpx.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": STRAVA_REDIRECT_URI,
            },
            timeout=10.0,
        )
        if not response.is_success:
            detail = response.text[:500]
            try:
                body = response.json()
                message = body.get("message") or "Bad Request"
                errors = body.get("errors") or []
                detail = f"{message}"
                if errors:
                    detail = f"{detail}: {errors}"
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Failed to exchange Strava authorization code "
                    f"(HTTP {response.status_code}): {detail}"
                ),
            )
        token_data = response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange Strava authorization code: {exc}",
        ) from exc

    strava_athlete_id = token_data.get("athlete", {}).get("id")
    if strava_athlete_id is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Strava token response did not include athlete id.",
        )

    connection = (
        db.query(StravaConnection)
        .filter(StravaConnection.strava_athlete_id == strava_athlete_id)
        .first()
    )

    if connection is None:
        connection = StravaConnection(strava_athlete_id=strava_athlete_id)
        db.add(connection)

    connection.access_token = token_data["access_token"]
    connection.refresh_token = token_data["refresh_token"]
    connection.expires_at = token_data["expires_at"]

    if payload.state:
        try:
            connection.athlete_profile_id = int(payload.state)
        except ValueError:
            pass

    db.commit()
    db.refresh(connection)

    if connection.athlete_profile_id is not None:
        status_data = get_sync_status()
        if not status_data["running"]:
            background_tasks.add_task(
                sync_activities_in_background,
                connection.athlete_profile_id,
            )

    return connection


@router.post("/sync", response_model=ImportStartResponse)
def start_strava_sync(
    background_tasks: BackgroundTasks,
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    from app.services.strava_sync import get_connection_for_athlete

    connection = get_connection_for_athlete(db, athlete_profile_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Strava connection found for this athlete profile.",
        )

    status_data = get_sync_status()
    if status_data["running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Strava activity sync is already running.",
        )

    background_tasks.add_task(sync_activities_in_background, athlete_profile_id)
    return ImportStartResponse(
        status="started",
        message="Strava activity sync started in the background.",
    )


@router.get("/sync/status", response_model=ImportStatusResponse)
def strava_sync_status():
    return ImportStatusResponse(**get_sync_status())


@router.post("/backfill-streams")
def backfill_streams(
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Retroactively fetch Strava streams for API-imported activities that have no point data."""
    from app.services.strava_api import StravaApiError as _StravaApiError

    try:
        result = backfill_streams_for_athlete(db, athlete_profile_id)
    except _StravaApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/status", response_model=StravaConnectionStatus)
def strava_status(
    athlete_profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(StravaConnection)
    if athlete_profile_id is not None:
        query = query.filter(StravaConnection.athlete_profile_id == athlete_profile_id)
    connection = query.order_by(StravaConnection.id.desc()).first()
    if connection is None:
        return StravaConnectionStatus(connected=False)

    return StravaConnectionStatus(
        connected=True,
        strava_athlete_id=connection.strava_athlete_id,
    )
