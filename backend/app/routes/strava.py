from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.config import (
    STRAVA_AUTHORIZE_URL,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REDIRECT_URI,
    STRAVA_SCOPES,
    STRAVA_TOKEN_URL,
)
from app.database import get_db
from app.models import AthleteProfile, StravaConnection, User
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
    try_start_strava_sync,
)

router = APIRouter(prefix="/strava", tags=["strava"])


def _require_strava_config() -> None:
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Strava OAuth is not configured. Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET.",
        )


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


@router.get("/auth", response_model=StravaAuthUrlResponse)
def strava_auth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_strava_config()
    profile = _require_athlete_profile(current_user, db)

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": STRAVA_REDIRECT_URI,
        "approval_prompt": "force",
        "scope": STRAVA_SCOPES,
        "state": str(profile.id),
    }

    authorization_url = f"{STRAVA_AUTHORIZE_URL}?{urlencode(params)}"
    return StravaAuthUrlResponse(authorization_url=authorization_url)


@router.post("/callback", response_model=StravaConnectionRead)
def strava_callback(
    payload: StravaCallbackRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_strava_config()
    profile = _require_athlete_profile(current_user, db)

    if payload.state:
        try:
            state_profile_id = int(payload.state)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state.",
            ) from exc
        if state_profile_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OAuth state does not match user.",
            )

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
    connection.athlete_profile_id = profile.id

    db.commit()
    db.refresh(connection)

    outcome = try_start_strava_sync(db, profile.id, inline=False)
    if outcome.get("started"):
        background_tasks.add_task(
            sync_activities_in_background,
            profile.id,
        )

    return connection


@router.post("/sync", response_model=ImportStartResponse)
def start_strava_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    outcome = try_start_strava_sync(db, profile.id, inline=False)
    if outcome.get("reason") == "no_connection":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Strava connection found for this athlete profile.",
        )
    if outcome.get("reason") == "already_running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Strava activity sync is already running.",
        )

    background_tasks.add_task(sync_activities_in_background, profile.id)
    return ImportStartResponse(
        status="started",
        message="Strava activity sync started in the background.",
    )


@router.get("/sync/status", response_model=ImportStatusResponse)
def strava_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    return ImportStatusResponse(**get_sync_status(profile.id))


@router.post("/backfill-streams")
def backfill_streams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retroactively fetch Strava streams for API-imported activities that have no point data."""
    from app.services.strava_api import StravaApiError as _StravaApiError

    profile = _require_athlete_profile(current_user, db)
    try:
        result = backfill_streams_for_athlete(db, profile.id)
    except _StravaApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/status", response_model=StravaConnectionStatus)
def strava_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_athlete_profile(current_user, db)
    connection = (
        db.query(StravaConnection)
        .filter(StravaConnection.athlete_profile_id == profile.id)
        .order_by(StravaConnection.id.desc())
        .first()
    )
    if connection is None:
        return StravaConnectionStatus(connected=False)

    return StravaConnectionStatus(
        connected=True,
        strava_athlete_id=connection.strava_athlete_id,
    )
