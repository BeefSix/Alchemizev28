# app/api/v1/endpoints/content.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import crud, models # Ensure models has your Job ORM model and JobResponse
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks # Assuming tasks.py is available
import uuid
import json # For parsing if content results are stored as JSON string

router = APIRouter()

# Example: Content Repurposing Endpoint (UNCOMMENTED)
class RepurposeRequest(models.BaseModel):
    content: str # This could be text or a URL
    platforms: list[str] = ["LinkedIn", "Facebook", "Twitter", "Instagram"] # Add platforms selection

@router.post("/repurpose", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
def create_repurpose_job(
    request: RepurposeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts text or a URL and starts a background job to repurpose content.
    """
    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="content")
    tasks.run_content_repurpose_job.delay(
        job_id=job_id,
        user_id=current_user.id, # Pass user_id as int
        content_input=request.content, # Renamed from content_text to content_input
        platforms=request.platforms
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