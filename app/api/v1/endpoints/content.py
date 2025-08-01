# app/api/v1/endpoints/content.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks
from app.core.limiter import limiter
import uuid
import json

router = APIRouter()

class RepurposeRequest(models.BaseModel):
    content: str
    platforms: list[str] = ["LinkedIn", "Twitter", "Instagram"]
    tone: str = "Professional"
    style: str = "Concise"
    additional_instructions: str = ""

@limiter.limit("20/hour")
@router.post("/repurpose", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def create_repurpose_job(
    request: RepurposeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts text or a URL and starts a background job to repurpose content,
    including tone, style, and additional instructions.
    """
    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="content")
    
    tasks.run_content_repurpose_job.delay(
        job_id=job_id,
        user_id=current_user.id,
        content_input=request.content,
        platforms=request.platforms,
        tone=request.tone,
        style=request.style,
        additional_instructions=request.additional_instructions
    )
    
    return {"job_id": job_id, "message": "Content repurposing job has been accepted."}

class ThumbnailRequest(models.BaseModel):
    content_job_id: str

@router.post("/generate-thumbnail", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def generate_thumbnail_job(
    request: ThumbnailRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Starts a background job to generate a thumbnail based on a completed content job.
    """
    content_job = crud.get_job(db, job_id=request.content_job_id)
    if not content_job or content_job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Content job not found.")
    if content_job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Content job must be completed.")

    prompt_for_thumbnail = ""
    if content_job.results:
        try:
            results = json.loads(content_job.results) if isinstance(content_job.results, str) else content_job.results
            prompt_for_thumbnail = results.get("analysis", "") or results.get("posts", "")
            if not prompt_for_thumbnail:
                raise ValueError("No valid content for thumbnail prompt found.")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=500, detail=f"Could not retrieve content for thumbnail: {e}")

    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="thumbnail")
    
    tasks.generate_thumbnail_job.delay(
        job_id=job_id,
        user_id=current_user.id,
        prompt_text=prompt_for_thumbnail
    )

    return {"job_id": job_id, "message": "Thumbnail generation job accepted."}

@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_content_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the status of a content generation job."""
    job = crud.get_job(db, job_id=job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found or not authorized.")
    
    return {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": job.results,
        "progress_details": job.progress_details
    }