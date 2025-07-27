# app/api/v1/endpoints/video.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks
import uuid
import json

router = APIRouter()

class VideoClipRequest(models.BaseModel):
    video_url: str
    add_captions: bool = True
    aspect_ratio: str = "9:16"

class JobResponse(models.BaseModel):
    job_id: str
    message: str

class ContentJobResults(models.BaseModel):
    analysis: str
    posts: str

class VideoClipJobResults(models.BaseModel):
    clip_urls: list[str]

class JobStatusResponse(models.BaseModel):
    id: str
    status: str
    progress_details: dict | None = None
    results: dict | ContentJobResults | VideoClipJobResults | None = None
    error_message: str | None = None

@router.post("/videoclips", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
def create_videoclip_job(
    request: VideoClipRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip")
    tasks.run_videoclip_job.delay(
        job_id=job_id,
        user_id=current_user.id,  # CORRECTED: Pass user_id as int
        video_url=request.video_url,
        add_captions=request.add_captions,
        aspect_ratio=request.aspect_ratio
    )
    return {"job_id": job_id, "message": "Video clipping job has been accepted and is processing."}

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    job = crud.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this job")
    
    response_data = {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": None,
        "progress_details": None
    }
    if job.results:
        try:
            response_data["results"] = json.loads(job.results) if isinstance(job.results, str) else job.results
        except json.JSONDecodeError:
            response_data["results"] = None
    if job.progress_details:
        try:
            response_data["progress_details"] = json.loads(job.progress_details) if isinstance(job.progress_details, str) else job.progress_details
        except json.JSONDecodeError:
            response_data["progress_details"] = None
            
    return response_data