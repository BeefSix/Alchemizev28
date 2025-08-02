"""
FastAPI endpoints that handle video uploads and dispatch GPU-accelerated
clip-generation jobs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4
from typing import List

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud, models
from app.dependencies import get_current_user, get_db
from app.workers.video_tasks import run_videoclip_upload_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/upload-and-clip", status_code=status.HTTP_202_ACCEPTED)
async def upload_and_clip_video(
    file: UploadFile = File(...),
    add_captions: bool = Form(False),
    aspect_ratio: str = Form("9:16"),
    platforms: str = Form("tiktok,instagram"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    """Stream-upload a video, register a DB job, and queue GPU processing."""
    # -------- validation ---------------------------------------------------
    platforms_list: List[str] = [
        p.strip().lower() for p in platforms.split(",") if p.strip()
    ]
    if not platforms_list:
        raise HTTPException(400, detail="At least one platform must be provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mkv", ".mov"}:
        raise HTTPException(400, detail="Unsupported video format")

    # -------- paths --------------------------------------------------------
    job_id = str(uuid4())
    upload_dir = Path(settings.STATIC_GENERATED_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"{job_id}{ext}"

    # -------- write file to the *shared* volume ---------------------------
    try:
        async with aiofiles.open(video_path, "wb") as out_file:
            while chunk := await file.read(1_048_576):  # 1 MiB
                await out_file.write(chunk)
    except Exception as exc:
        logger.exception("Failed saving upload")
        raise HTTPException(500, detail="Could not save upload") from exc

    # -------- DB record ----------------------------------------------------
    try:
        crud.create_job(
            db, job_id=job_id, user_id=current_user.id, job_type="videoclip"
        )
    except Exception as exc:
        logger.exception("DB insert failed")
        raise HTTPException(500, detail="Could not create job") from exc

    # -------- enqueue Celery task on the GPU queue ------------------------
    run_videoclip_upload_job.apply_async(
        kwargs=dict(
            job_id=job_id,
            user_id=current_user.id,
            video_path=str(video_path),
            add_captions=add_captions,
            aspect_ratio=aspect_ratio,
            platforms=platforms_list,
        ),
        queue="gpu",
    )

    return {"job_id": job_id, "status": "queued"}