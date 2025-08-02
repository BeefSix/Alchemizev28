"""
Refactored FastAPI video upload endpoint.

This module defines a single route for handling video uploads.  It performs
basic file validation, streams the uploaded video to disk to avoid loading
large files into memory, creates a job record, and dispatches the
background processing task via Celery.  Replace the existing upload
endpoint in `app/api/v1/endpoints/video.py` with the implementation below.

Note: You will need to add `aiofiles` to your project dependencies (it is
included in the standard FastAPI installation) and ensure that
`app.workers.video_tasks.run_videoclip_upload_job` is available.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.core.config import settings
from app.workers.video_tasks import run_videoclip_upload_job


router = APIRouter()


@router.post(
    "/upload-and-clip",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=models.JobResponse,
)
async def upload_and_clip_video(
    file: UploadFile = File(...),
    add_captions: bool = Form(...),
    aspect_ratio: str = Form(...),
    platforms: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.JobResponse:
    """Accept a video upload and start background clip generation.

    This endpoint validates the file extension, streams the uploaded file
    to a temporary location, creates a database job record, and kicks
    off the Celery task.  It returns a `job_id` that clients can use to
    poll for status.
    """
    # Validate file type
    valid_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in valid_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Stream uploaded file to disk
    upload_dir = Path(settings.STATIC_GENERATED_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    video_path = upload_dir / f"{job_id}{ext}"

    # Read and write in chunks to avoid loading the full file into memory
    async with aiofiles.open(video_path, "wb") as out_file:
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            await out_file.write(chunk)

    # Create DB job record
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip")

    # Dispatch background task
    platform_list = [p.strip().lower() for p in platforms.split(",") if p.strip()]
    run_videoclip_upload_job.delay(
        job_id=job_id,
        user_id=current_user.id,
        video_path=str(video_path),
        add_captions=add_captions,
        aspect_ratio=aspect_ratio,
        platforms=platform_list,
    )

    return models.JobResponse(job_id=job_id, message="Video processing has started")
