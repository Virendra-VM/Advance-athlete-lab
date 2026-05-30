import json

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import STRAVA_WEBHOOK_VERIFY_TOKEN

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
async def strava_webhook_event(request: Request):
    payload = await request.json()
    print("[Strava Webhook]", json.dumps(payload, indent=2))
    return {"status": "ok"}
