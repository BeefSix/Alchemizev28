# app/api/v1/endpoints/content.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import crud, models # Ensure models has your Job ORM model and JobResponse
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks # Assuming tasks.py is available
import uuid
import json # For parsing if content results are stored as JSON string

@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_content_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the status of a content generation job"""
    job = crud.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    
    # Parse the JSON fields
    results = None
    progress_details = None
    
    try:
        if job.results:
            results = json.loads(job.results) if isinstance(job.results, str) else job.results
    except json.JSONDecodeError:
        results = {"error": "Could not parse results"}
        
    try:
        if job.progress_details:
            progress_details = json.loads(job.progress_details) if isinstance(job.progress_details, str) else job.progress_details
    except json.JSONDecodeError:
        progress_details = {"error": "Could not parse progress details"}
    
    return {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": results,
        "progress_details": progress_details
    }
router = APIRouter()

# Example: Content Repurposing Endpoint (UNCOMMENTED)
class RepurposeRequest(models.BaseModel):
    content: str
    platforms: list[str] = ["LinkedIn", "Facebook", "Twitter", "Instagram"]
    tone: str = "Professional"  # New field
    style: str = "Concise"  # New field
    additional_instructions: str = ""  # New field

# Update the create_repurpose_job function to pass these new parameters

@router.post("/repurpose", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def create_repurpose_job(
    request: RepurposeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts text or a URL and starts a background job to repurpose content.
    Now includes tone, style, and additional instructions.
    """
    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="content")
    
    # Pass the new parameters to the Celery task
    tasks.run_content_repurpose_job.delay(
        job_id=job_id,
        user_id=current_user.id,
        content_input=request.content,
        platforms=request.platforms,
        tone=request.tone,
        style=request.style,
        additional_instructions=request.additional_instructions
    )
    
    return {"job_id": job_id, "message": "Content repurposing job has been accepted and is processing."}


# ADDED: Pydantic model for the request to generate a thumbnail
class ThumbnailRequest(models.BaseModel):
    content_job_id: str # The ID of the completed content generation job

@router.post("/generate-thumbnail", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def generate_thumbnail_job(
    request: ThumbnailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts a content job ID and starts a background job to generate a thumbnail.
    """
    # Validate that the content job exists and belongs to the user
    content_job = crud.get_job(db, job_id=request.content_job_id)
    if not content_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content job not found.")
    if content_job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this content job.")
    if content_job.status != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content job must be completed to generate a thumbnail.")

    # Extract relevant data from the completed content job's results
    # The 'analysis' field is typically what's used for the thumbnail prompt.
    prompt_for_thumbnail = ""
    if content_job.results:
        try:
            # Safely parse the results, which are stored as a JSON string
            parsed_results = json.loads(content_job.results) if isinstance(content_job.results, str) else content_job.results
            prompt_for_thumbnail = parsed_results.get("analysis", "")
            if not prompt_for_thumbnail:
                 # Fallback to posts if analysis is empty, or raise error
                posts_content = parsed_results.get("posts", "")
                if posts_content:
                    prompt_for_thumbnail = posts_content.split('\n')[0].strip() # Take first line of posts as prompt
                else:
                    raise ValueError("No valid content for thumbnail prompt found in content job results.")

        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            print(f"Warning: Could not parse content job results for thumbnail generation (job_id: {request.content_job_id}). Error: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve content analysis for thumbnail generation.")

    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="thumbnail")

    # Delegate the thumbnail generation to the Celery worker
    tasks.generate_thumbnail_job.delay(
        job_id=job_id,
        user_id=current_user.id, # Pass user_id as int
        prompt_text=prompt_for_thumbnail # Use analysis/posts for the thumbnail prompt
    )

    return {"job_id": job_id, "message": "Thumbnail generation job has been accepted and is processing."}