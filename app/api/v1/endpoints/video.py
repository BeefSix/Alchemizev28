# app/api/v1/endpoints/video.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import crud, models # Ensure models has your Job ORM model
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks
import uuid
import json # <-- Added this import

router = APIRouter()

# Pydantic models for request and response validation
class VideoClipRequest(models.BaseModel):
    video_url: str
    add_captions: bool = True
    aspect_ratio: str = "9:16"

class JobResponse(models.BaseModel):
    job_id: str
    message: str

# Define a Pydantic model for the "results" payload (e.g., for content jobs)
# You might want to define more specific result models if the structure
# of 'results' varies greatly by 'job_type' (e.g., 'videoclip' vs 'content')
class ContentJobResults(models.BaseModel):
    analysis: str
    posts: str

class VideoClipJobResults(models.BaseModel):
    clip_urls: list[str] # Assuming this is the structure for video clip results

# Updated JobStatusResponse to handle different result types more explicitly
class JobStatusResponse(models.BaseModel):
    id: str
    status: str
    progress_details: dict | None = None
    # Using 'dict | ContentJobResults | VideoClipJobResults | None'
    # allows for flexibility if you parse into a generic dict OR
    # into a more specific Pydantic model depending on job_type.
    # FastAPI will try to validate against these types.
    results: dict | ContentJobResults | VideoClipJobResults | None = None
    error_message: str | None = None

@router.post("/videoclips", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
def create_videoclip_job(
    request: VideoClipRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Accepts a video URL and starts a background job to process it.
    """
    job_id = str(uuid.uuid4())
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip")
    
    # Delegate the long-running task to the Celery worker
    tasks.run_videoclip_job.delay(
        job_id=job_id, 
        user_id=str(current_user.id),  # Pass user_id as a string
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
    """
    Retrieves the status and results of a specific job.
    """
    job = crud.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    # Ensure a user can only view their own jobs
    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this job")
        
    # --- START OF THE FIX ---
    # Prepare the response data explicitly to ensure 'results' and 'progress_details'
    # are Python dictionaries, not JSON strings.
    
    # Initialize basic response data from the job object
    response_data = {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": None,         # Initialize as None, will be parsed if present
        "progress_details": None # Initialize as None, will be parsed if present
    }

    # Handle 'results' field: parse if it's a JSON string from the database
    if job.results is not None:
        if isinstance(job.results, str): # Check if it's a string that needs parsing
            try:
                response_data["results"] = json.loads(job.results)
            except json.JSONDecodeError:
                # Log a warning if the string isn't valid JSON, and set to None
                print(f"Warning: Could not decode JSON for job results (job_id: {job_id}). Raw value: '{job.results}'")
                response_data["results"] = None
        else: # If it's already a dictionary or other non-string type (e.g., if database handles JSON directly)
            response_data["results"] = job.results
            
    # Handle 'progress_details' field: parse if it's a JSON string from the database
    if job.progress_details is not None:
        if isinstance(job.progress_details, str): # Check if it's a string that needs parsing
            try:
                response_data["progress_details"] = json.loads(job.progress_details)
            except json.JSONDecodeError:
                # Log a warning if the string isn't valid JSON, and set to None
                print(f"Warning: Could not decode JSON for progress_details (job_id: {job_id}). Raw value: '{job.progress_details}'")
                response_data["progress_details"] = None
        else: # If it's already a dictionary or other non-string type
            response_data["progress_details"] = job.progress_details

    # Return the prepared dictionary. FastAPI will then validate it against JobStatusResponse
    # and automatically serialize it to JSON.
    return response_data
    # --- END OF THE FIX ---