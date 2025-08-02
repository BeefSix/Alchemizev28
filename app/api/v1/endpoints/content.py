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
import logging

# Set up logging
logger = logging.getLogger(__name__)
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
    request: Request,
    repurpose_data: RepurposeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts text or a URL and starts a background job to repurpose content,
    including tone, style, and additional instructions.
    """
    logger.info(f"Content repurpose request from user {current_user.id} for platforms: {repurpose_data.platforms}")
    
    # Validate content
    if not repurpose_data.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    
    # Validate platforms
    valid_platforms = ["LinkedIn", "Twitter", "Instagram", "TikTok", "Facebook", "YouTube"]
    invalid_platforms = [p for p in repurpose_data.platforms if p not in valid_platforms]
    if invalid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platforms: {invalid_platforms}")
    
    job_id = str(uuid.uuid4())
    
    try:
        crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="content")
        
        tasks.run_content_repurpose_job.delay(
            job_id=job_id,
            user_id=current_user.id,
            content_input=repurpose_data.content,
            platforms=repurpose_data.platforms,  # Fixed: was request.platforms
            tone=repurpose_data.tone,            # Fixed: was request.tone
            style=repurpose_data.style,          # Fixed: was request.style
            additional_instructions=repurpose_data.additional_instructions  # Fixed: was request.additional_instructions
        )
        
    except Exception as e:
        logger.error(f"Failed to create content repurpose job: {e}")
        raise HTTPException(status_code=500, detail="Failed to start content repurposing")
    
    return {"job_id": job_id, "message": "Content repurposing job has been accepted."}

class ThumbnailRequest(models.BaseModel):
    content_job_id: str

@router.post("/generate-thumbnail", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def generate_thumbnail_job(
    thumbnail_request: ThumbnailRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Starts a background job to generate a thumbnail based on a completed content job.
    """
    content_job = crud.get_job(db, job_id=thumbnail_request.content_job_id)
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
    
    try:
        crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="thumbnail")
        
        tasks.generate_thumbnail_job.delay(
            job_id=job_id,
            user_id=current_user.id,
            prompt_text=prompt_for_thumbnail
        )
    except Exception as e:
        logger.error(f"Failed to create thumbnail job: {e}")
        raise HTTPException(status_code=500, detail="Failed to start thumbnail generation")

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