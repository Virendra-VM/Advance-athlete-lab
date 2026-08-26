import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status

from app.config import STRAVA_WEBHOOK_VERIFY_TOKEN
from app.services.strava_sync import sync_single_activity_in_background

router = APIRouter(prefix="/strava", tags=["strava-webhook"])


@router.get("/webhook")
async def strava_webhook_validation(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    if hub_mode != "subscribe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid hub.mode for webhook validation.",
        )

    if not STRAVA_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRAVA_WEBHOOK_VERIFY_TOKEN is not configured.",
        )

    if hub_verify_token != STRAVA_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook verify token.",
        )

    if not hub_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing hub.challenge.",
        )

    return {"hub.challenge": hub_challenge}


@router.post("/webhook")
async def strava_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
):
    payload = await request.json()
    print("[Strava Webhook]", json.dumps(payload, indent=2))

    if payload.get("object_type") == "activity" and payload.get("aspect_type") in {
        "create",
        "update",
    }:
        owner_id = payload.get("owner_id")
        object_id = payload.get("object_id")
        aspect_type = payload.get("aspect_type") or "create"
        if owner_id is not None and object_id is not None:
            background_tasks.add_task(
                sync_single_activity_in_background,
                int(owner_id),
                int(object_id),
                str(aspect_type),
            )

    return {"status": "ok"}
