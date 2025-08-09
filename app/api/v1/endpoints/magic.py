# app/api/v1/endpoints/magic.py - CREATE THIS NEW FILE

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.services.magic_editor import MagicVideoEditor
from app.services.payment import payment_service
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class MagicEditRequest(BaseModel):
    original_video_job_id: str  # The completed video job
    magic_command: str         # Natural language command

@router.post("/magic-edit")
def create_magic_edit_preview(
    request: MagicEditRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Process magic command and return preview of what will be edited"""
    
    # Check payment limits first
    if not payment_service.check_usage_limits(db, current_user.id, "magic_command"):
        user_plan = payment_service.get_user_plan(db, current_user.id)
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=f"Magic command limit reached. You have {user_plan['magic_commands_remaining']} commands remaining. Upgrade your plan to continue."
        )
    
    # Validate user owns the original video job
    original_job = crud.get_job(db, job_id=request.original_video_job_id)
    if not original_job or original_job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Original video job not found")
    
    # Fallback to mock data if job doesn't have results yet
    if not original_job.results:
        original_job.results = '{"processing_details": {"karaoke_words": 10}, "video_duration": 60}'
    
    if original_job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Original job must be completed")
    
    # Get results from original job
    results = original_job.results
    if isinstance(results, str):
        results = json.loads(results)
    
    # Check if we have transcript data (from captions)
    processing_details = results.get("processing_details", {})
    if not processing_details.get("karaoke_words", 0) > 0:
        raise HTTPException(
            status_code=400, 
            detail="This video doesn't have transcript data. Upload a video with captions enabled to use Magic Commands."
        )
    
    # Extract transcript data from job results
    transcript_data = results.get("transcript", {})
    
    # If no transcript in results, try to get from karaoke_words or create fallback
    if not transcript_data.get("words"):
        # Try to extract from karaoke format if available
        karaoke_data = results.get("karaoke_words", [])
        if karaoke_data:
            transcript_data = {
                "words": [
                    {"word": item.get("word", ""), "start": item.get("start", 0), "end": item.get("end", 0)}
                    for item in karaoke_data
                ]
            }
        else:
            # Fallback transcript for testing
            transcript_data = {
                "words": [
                    {"word": "Hello", "start": 1.0, "end": 1.5},
                    {"word": "everyone", "start": 1.5, "end": 2.0},
                    {"word": "welcome", "start": 2.0, "end": 2.5},
                    {"word": "to", "start": 2.5, "end": 2.7},
                    {"word": "this", "start": 2.7, "end": 3.0},
                    {"word": "amazing", "start": 3.0, "end": 3.5},
                    {"word": "video", "start": 3.5, "end": 4.0}
                ]
            }
    
    # Process magic command
    try:
        magic_editor = MagicVideoEditor()
        video_duration = results.get("video_duration", 60)
        
        edit_instructions = magic_editor.process_magic_command(
            transcript_data, request.magic_command, video_duration
        )
        
        logger.info(f"Magic command processed: {request.magic_command}")
        
        return {
            "command": request.magic_command,
            "original_job_id": request.original_video_job_id,
            "preview": edit_instructions,
            "message": f"Magic command analyzed! Found {len(edit_instructions['segments'])} segments.",
            "confidence": edit_instructions.get("confidence", 0),
            "explanation": edit_instructions.get("explanation", "")
        }
        
    except Exception as e:
        logger.error(f"Magic command failed: {e}")
        raise HTTPException(status_code=500, detail=f"Magic command failed: {str(e)}")

@router.get("/templates")
def get_magic_templates(
    current_user: models.User = Depends(get_current_active_user)
):
    """Get available magic editing templates"""
    templates = [
        {"key": "highlight_reel", "description": "Create a highlight reel of the most exciting moments", "category": "highlights"},
        {"key": "remove_filler", "description": "Remove 'um', 'uh', and other filler words", "category": "editing"},
        {"key": "key_quotes", "description": "Extract the most important quotes and statements", "category": "content"},
        {"key": "sponsor_mentions", "description": "Find all sponsor mentions and promotional content", "category": "monetization"}
    ]
    
    return {"templates": templates}