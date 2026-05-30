from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ImportStartRequest, ImportStartResponse, ImportStatusResponse
from app.services.strava_import import (
    backfill_activity_metadata,
    get_import_status,
    run_import_in_background,
    run_upload_and_import_in_background,
    save_uploaded_zip,
)

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/strava-history", response_model=ImportStartResponse)
def start_strava_history_import(
    payload: ImportStartRequest,
    background_tasks: BackgroundTasks,
):
    status_data = get_import_status()
    if status_data["running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Strava history import is already running.",
        )

    background_tasks.add_task(run_import_in_background, payload.athlete_profile_id)
    return ImportStartResponse(
        status="started",
        message="Strava bulk export import started in the background.",
    )


@router.post("/strava-history/upload", response_model=ImportStartResponse)
async def upload_strava_history_export(
    background_tasks: BackgroundTasks,
    athlete_profile_id: int = Form(...),
    file: UploadFile = File(...),
):
    status_data = get_import_status()
    if status_data["running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Strava history import is already running.",
        )

    try:
        file_bytes = await file.read()
        zip_path = save_uploaded_zip(file_bytes, file.filename or "export.zip")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(
        run_upload_and_import_in_background,
        athlete_profile_id,
        zip_path,
    )
    return ImportStartResponse(
        status="started",
        message="Upload received. Extracting and importing your Strava export.",
    )


@router.get("/strava-history/status", response_model=ImportStatusResponse)
def strava_history_import_status():
    return ImportStatusResponse(**get_import_status())


@router.post("/strava-history/backfill-metadata")
def backfill_strava_metadata(
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return backfill_activity_metadata(db, athlete_profile_id)
