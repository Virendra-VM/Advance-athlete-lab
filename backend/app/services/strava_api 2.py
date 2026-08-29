from __future__ import annotations

import time

import httpx
from sqlalchemy.orm import Session

from app.config import (
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_TOKEN_URL,
)
from app.models import StravaConnection

STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaApiError(Exception):
    pass


def _require_oauth_config() -> None:
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise StravaApiError(
            "Strava OAuth is not configured. Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET."
        )


def refresh_access_token(connection: StravaConnection, db: Session) -> str:
    _require_oauth_config()
    try:
        response = httpx.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": connection.refresh_token,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        token_data = response.json()
    except httpx.HTTPError as exc:
        raise StravaApiError(f"Failed to refresh Strava token: {exc}") from exc

    connection.access_token = token_data["access_token"]
    connection.refresh_token = token_data.get("refresh_token", connection.refresh_token)
    connection.expires_at = token_data["expires_at"]
    db.commit()
    db.refresh(connection)
    return connection.access_token


def get_valid_access_token(connection: StravaConnection, db: Session) -> str:
    if connection.expires_at <= int(time.time()) + 60:
        return refresh_access_token(connection, db)
    return connection.access_token


def list_athlete_activities(
    access_token: str,
    *,
    page: int = 1,
    per_page: int = 50,
    after: int | None = None,
) -> list[dict]:
    params: dict[str, int] = {"page": page, "per_page": per_page}
    if after is not None:
        params["after"] = after

    try:
        response = httpx.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise StravaApiError(f"Failed to list Strava activities: {exc}") from exc

    if not isinstance(payload, list):
        raise StravaApiError("Unexpected Strava activities response.")
    return payload


def get_activity(access_token: str, activity_id: int) -> dict:
    try:
        response = httpx.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise StravaApiError(f"Failed to fetch Strava activity {activity_id}: {exc}") from exc


def download_activity_fit(access_token: str, activity_id: int) -> bytes | None:
    try:
        response = httpx.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}/export_original",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=60.0,
            follow_redirects=True,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return None
        if not response.content:
            return None
        return response.content
    except httpx.HTTPError:
        return None
