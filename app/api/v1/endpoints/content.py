# app/api/v1/endpoints/content.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import logging
import uuid
from datetime import datetime

from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.services.payment import payment_service
from app.core.config import settings
from app.workers import tasks

logger = logging.getLogger(__name__)
router = APIRouter()

class RepurposeRequest(models.BaseModel):
    content: str
    platforms: list[str] = ["LinkedIn", "Twitter", "Instagram"]
    tone: str = "Professional"
    style: str = "Concise"
    additional_instructions: str = ""

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
        
        # Run synchronously instead of using Celery for now
        from app.workers.tasks import run_content_repurpose_job_sync
        run_content_repurpose_job_sync(
            job_id=job_id,
            user_id=current_user.id,
            content_input=repurpose_data.content,
            platforms=repurpose_data.platforms,
            tone=repurpose_data.tone,
            style=repurpose_data.style,
            additional_instructions=repurpose_data.additional_instructions
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

class ContentGenerationRequest(BaseModel):
    job_id: str
    platforms: List[str]

class ContentGenerationResponse(BaseModel):
    platform: str
    content: str
    character_count: int
    hashtags: List[str]
    estimated_engagement: float
    clip_reference: str
    generated_at: str

@router.post("/generate", response_model=List[ContentGenerationResponse])
def generate_content_from_transcript(
    request: ContentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Generate platform-specific content from video transcript"""
    
    # Check payment limits
    if not payment_service.check_usage_limits(db, current_user.id, "content_generation"):
        user_plan = payment_service.get_user_plan(db, current_user.id)
        raise HTTPException(
            status_code=402,
            detail=f"Content generation limit reached. You have {user_plan['content_generations_remaining']} generations remaining."
        )
    
    # Get the video job
    job = crud.get_job(db, job_id=request.job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video job not found")
    
    if job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Video job must be completed to generate content")
    
    # Extract transcript from job results
    results = job.results
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except:
            results = {}
    
    # Get transcript data
    transcript_data = results.get("transcript", {})
    if not transcript_data:
        raise HTTPException(
            status_code=400, 
            detail="No transcript data found. Please ensure the video has captions enabled."
        )
    
    # Generate content for each platform
    generated_content = []
    
    for platform in request.platforms:
        try:
            content = generate_platform_content(platform, transcript_data, results, current_user.id)
            generated_content.append(content)
        except Exception as e:
            logger.error(f"Failed to generate content for {platform}: {e}")
            continue
    
    # Deduct usage
    payment_service.deduct_usage(db, current_user.id, "content_generation", len(request.platforms))
    
    return generated_content

def generate_platform_content(platform: str, transcript_data: Dict, job_results: Dict, user_id: int) -> ContentGenerationResponse:
    """Generate platform-specific content using AI"""
    
    # Extract key information from transcript
    words = transcript_data.get("words", [])
    text = " ".join([word.get("word", "") for word in words if word.get("word")])
    
    # Get video metadata
    video_duration = job_results.get("video_duration", 60)
    total_clips = job_results.get("total_clips", 5)
    
    # Platform-specific content generation
    if platform == "LinkedIn":
        content = generate_linkedin_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#professional", "#business", "#growth"]
        engagement = 8.5
    elif platform == "Twitter":
        content = generate_twitter_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#viral", "#trending", "#socialmedia"]
        engagement = 12.3
    elif platform == "Instagram":
        content = generate_instagram_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#instagram", "#reels", "#viral"]
        engagement = 15.7
    elif platform == "TikTok":
        content = generate_tiktok_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#tiktok", "#viral", "#fyp"]
        engagement = 18.2
    elif platform == "YouTube":
        content = generate_youtube_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#youtube", "#shorts", "#viral"]
        engagement = 9.8
    elif platform == "Facebook":
        content = generate_facebook_content(text, video_duration, total_clips, user_id)
        hashtags = ["#content", "#video", "#facebook", "#viral", "#socialmedia"]
        engagement = 11.4
    else:
        content = f"Generated content for {platform} based on video transcript: {text[:100]}..."
        hashtags = ["#content", "#video", "#socialmedia"]
        engagement = 7.0
    
    return ContentGenerationResponse(
        platform=platform,
        content=content,
        character_count=len(content),
        hashtags=hashtags,
        estimated_engagement=engagement,
        clip_reference=f"Clip {1 + hash(platform) % total_clips}",
        generated_at=datetime.utcnow().isoformat()
    )

def generate_linkedin_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate LinkedIn-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create a professional LinkedIn post based on this video content. The post should:
    - Be engaging and professional
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 2-3 key insights from the content
    - Use relevant emojis sparingly
    - Include relevant hashtags
    - Be around 200-300 words
    - End with a call-to-action question
    
    Video content: {text[:1500]}
    
    Return only the LinkedIn post content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=400, temperature=0.7)
    
    if ai_content:
        return ai_content.strip()
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""🎬 Just processed a {duration}s video into {clips} optimized clips!

Key insights from the content:
• {key_points[0] if key_points else 'Engaging content that drives results'}
• {key_points[1] if len(key_points) > 1 else 'Professional quality that stands out'}

The AI-powered editing process identified the most impactful moments and created platform-optimized content. Perfect for professional networking and thought leadership.

What's your experience with AI-powered content creation? Share your thoughts below! 👇

#ContentCreation #AI #ProfessionalDevelopment #VideoMarketing"""

def generate_twitter_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate Twitter-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create an engaging Twitter post based on this video content. The post should:
    - Be under 280 characters
    - Be engaging and conversational
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 1-2 key insights from the content
    - Use relevant emojis
    - Include 2-3 relevant hashtags
    - End with a call-to-action or question
    
    Video content: {text[:1200]}
    
    Return only the Twitter post content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=300, temperature=0.8)
    
    if ai_content:
        content = ai_content.strip()
        # Ensure it's under 280 characters
        if len(content) > 280:
            content = content[:277] + "..."
        return content
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""🚀 Just turned a {duration}s video into {clips} viral clips using AI!

Key takeaways:
• {key_points[0] if key_points else 'Engaging content that gets shared'}
• {key_points[1] if len(key_points) > 1 else 'Optimized for maximum reach'}

AI identified the most shareable moments automatically. The future of content creation is here! 

What do you think about AI-powered video editing? 🤔"""

def generate_instagram_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate Instagram-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create an engaging Instagram post based on this video content. The post should:
    - Be visually appealing and Instagram-friendly
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 2-3 key insights from the content
    - Use relevant emojis throughout
    - Include 5-8 relevant hashtags
    - Be around 150-250 words
    - Include calls-to-action like "double tap", "save this post", "comment below"
    - Have an inspirational/motivational tone
    
    Video content: {text[:1500]}
    
    Return only the Instagram post content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=500, temperature=0.7)
    
    if ai_content:
        return ai_content.strip()
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""✨ AI Magic: {duration}s → {clips} viral clips!

The AI analyzed every frame and found the most engaging moments. Each clip is optimized for Instagram's algorithm.

Key highlights:
• {key_points[0] if key_points else 'Visual storytelling that captivates'}
• {key_points[1] if len(key_points) > 1 else 'Perfect timing for maximum engagement'}

This is how you create content that actually performs! 📈

What's your favorite type of video content? Drop a comment! 👇"""

def generate_tiktok_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate TikTok-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create an engaging TikTok caption based on this video content. The caption should:
    - Be energetic and attention-grabbing
    - Use TikTok-style language ("This is INSANE!", "Wait for it", etc.)
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 1-2 key insights from the content
    - Use relevant emojis generously
    - Include 5-8 trending hashtags
    - Be around 100-150 words
    - Include calls-to-action like "like if you agree", "follow for more", "comment below"
    - Have a viral, shareable tone
    
    Video content: {text[:1200]}
    
    Return only the TikTok caption content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=400, temperature=0.9)
    
    if ai_content:
        return ai_content.strip()
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""🔥 AI just created {clips} viral TikTok clips from a {duration}s video!

The algorithm found the most trending moments and optimized them for TikTok's FYP algorithm.

Viral factors:
• {key_points[0] if key_points else 'Trending content that gets shared'}
• {key_points[1] if len(key_points) > 1 else 'Perfect timing and pacing'}

This is how you go viral on TikTok! The AI knows what works. 

What's your secret to TikTok success? Share below! 👇"""

def generate_youtube_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate YouTube-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create an engaging YouTube post based on this video content. The post should:
    - Be informative and engaging
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 2-3 key insights from the content
    - Use relevant emojis appropriately
    - Include 3-5 relevant hashtags
    - Be around 200-300 words
    - Include calls-to-action like "subscribe", "like this video", "comment below"
    - Focus on educational/entertainment value
    - Mention YouTube Shorts optimization
    
    Video content: {text[:1500]}
    
    Return only the YouTube post content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=500, temperature=0.7)
    
    if ai_content:
        return ai_content.strip()
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""🎥 AI-Powered Video Processing: {duration}s → {clips} optimized clips!

The AI analyzed the content and created multiple formats:
• Short-form clips for YouTube Shorts
• Engaging thumbnails and titles
• SEO-optimized descriptions

Key insights:
• {key_points[0] if key_points else 'Content that drives views and engagement'}
• {key_points[1] if len(key_points) > 1 else 'Optimized for YouTube algorithm'}

This is the future of content creation! What do you think about AI-powered video editing?

If you found this valuable, please like and subscribe for more content like this! 🔔

What would you like to see next? Let me know in the comments! 👇

#YouTube #AI #ContentCreation #VideoEditing #Shorts"""

def generate_facebook_content(text: str, duration: int, clips: int, user_id: int) -> str:
    """Generate Facebook-optimized content using AI"""
    from app.services.utils import run_ai_generation_sync
    
    prompt = f"""Create an engaging Facebook post based on this video content. The post should:
    - Be conversational and community-focused
    - Mention the video was processed into {clips} clips from {duration}s duration
    - Include 2-3 key insights from the content
    - Use relevant emojis appropriately
    - Be around 150-250 words
    - Include calls-to-action like "share your thoughts", "comment below", "tag a friend"
    - Encourage discussion and engagement
    - Have a friendly, approachable tone
    
    Video content: {text[:1500]}
    
    Return only the Facebook post content, no additional formatting."""
    
    ai_content = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=400, temperature=0.7)
    
    if ai_content:
        return ai_content.strip()
    else:
        # Fallback to template-based content
        key_points = extract_key_points(text, user_id)
        return f"""📱 Just processed a {duration}s video into {clips} Facebook-optimized clips!

The AI created content perfect for:
• Facebook Feed
• Facebook Stories
• Facebook Groups

Key highlights:
• {key_points[0] if key_points else 'Community-focused content that drives engagement'}
• {key_points[1] if len(key_points) > 1 else 'Optimized for Facebook algorithm'}

What's your experience with AI-powered content creation? Let's discuss in the comments! 👇"""

def extract_key_points(text: str, user_id: int = 1) -> List[str]:
    """Extract key points from text using AI"""
    from app.services.utils import run_ai_generation_sync
    
    if len(text.split()) < 20:
        return ["Key insight from content", "Important takeaway", "Actionable advice"]
    
    prompt = f"""Extract 3-5 key points from this transcript. Return them as a JSON array of strings.
    Focus on the most important insights, takeaways, or actionable advice.
    
    Transcript: {text[:2000]}
    
    Return format: ["point 1", "point 2", "point 3"]"""
    
    response = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=300, temperature=0.3, expect_json=True)
    
    if response:
        try:
            import json
            key_points = json.loads(response)
            if isinstance(key_points, list) and len(key_points) > 0:
                return key_points[:5]
        except json.JSONDecodeError:
            pass
    
    # Fallback to simple extraction
    keywords = ["important", "key", "main", "significant", "crucial", "essential"]
    sentences = text.split('.')
    key_sentences = []
    
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in keywords):
            key_sentences.append(sentence.strip())
    
    if not key_sentences:
        return ["Main point from transcript", "Key insight shared", "Important message"]
    
    return key_sentences[:3]

@router.get("/history")
def get_content_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0
):
    """Get content generation history for the current user"""
    # This would query a content_history table in a real implementation
    return {
        "content_history": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }



