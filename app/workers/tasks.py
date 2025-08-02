"""
Refactored tasks module for the Alchemize project.

This module collects all Celery tasks used by the backend and imports
the refactored video processing job from ``app.workers.video_tasks``.
It preserves the existing content repurposing, thumbnail generation and
cleanup tasks from the original ``app/workers/tasks.py`` while
removing the legacy ``run_videoclip_upload_job`` implementation.  By
importing the video task from ``video_tasks.py``, you centralise the
video processing logic in one place and make the tasks file easier to
navigate.

To integrate this file into your project, copy its contents into
``app/workers/tasks.py`` or rename it accordingly.  Ensure that
``video_tasks.py`` is present in ``app/workers`` and that
``refactored_video_endpoint.py`` replaces the upload endpoint in your
API as described in the integration instructions.
"""

import subprocess
import os
import json
import logging
import glob
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db_session
from app.services import video_engine, utils

# Import the refactored video processing task.  This replaces the
# monolithic implementation previously defined in this module.  See
# ``app/workers/video_tasks.py`` for implementation details.
from app.workers.video_tasks import run_videoclip_upload_job  # noqa: F401

# Configure a module-level logger.  Celery tasks will inherit this
# configuration and emit logs that include timestamps and severity.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def run_content_repurpose_job(
    self,
    job_id: str,
    user_id: int,
    content_input: str,
    platforms: list[str],
    tone: str,
    style: str,
    additional_instructions: str,
):
    """Generate repurposed content for multiple social media platforms.

    This task ingests raw text or a URL, analyses the content using
    an AI model, and then generates platform‑specific social media
    posts according to the provided tone, style and instructions.  It
    updates job progress in the database and records results when
    complete.

    Args:
        job_id: Unique identifier for the background job.
        user_id: ID of the user requesting the job.
        content_input: Raw text or URL to repurpose.
        platforms: List of social media platforms to target.
        tone: Desired tone of the generated posts.
        style: Desired writing style of the generated posts.
        additional_instructions: Custom instructions for the AI model.
    """
    try:
        logger.info(f"Starting content job {job_id} for user {user_id}")

        # Record initial status
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "IN_PROGRESS",
                progress_details={"description": "Ingesting content...", "percentage": 5},
            )

        # Ingest content (handles URLs or raw text)
        content_to_process = utils.ingest_content(content_input)
        if not content_to_process or content_to_process.startswith("Error:"):
            raise ValueError(f"Failed to ingest content: {content_to_process}")

        # Update status before analysis
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "IN_PROGRESS",
                progress_details={"description": "Analyzing content...", "percentage": 20},
            )

        # Analyse content using AI
        analysis_prompt = (
            "Analyze this content and extract key insights, tone, audience, and main themes.\n"
            "Focus on what makes it engaging and how it could be adapted for social media.\n\n"
            f"CONTENT:\n{content_to_process[:4000]}"
        )
        content_analysis = utils.run_ai_generation_sync(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis:
            raise Exception("AI content analysis failed - check your OpenAI API key and credits.")

        # Update status before generation
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "IN_PROGRESS",
                progress_details={"description": "Generating social media posts...", "percentage": 60},
            )

        # Generate content for platforms
        platform_str = ", ".join(platforms)
        generation_prompt = (
            "You are an expert social media content strategist. Transform the provided content into engaging posts for "
            f"{platform_str}.\n\n"
            f"TONE: {tone}\n"
            f"STYLE: {style}\n"
            f"ADDITIONAL INSTRUCTIONS: {additional_instructions}\n\n"
            "GUIDELINES:\n"
            "- Create platform-specific content that fits each platform's style\n"
            "- For LinkedIn: Professional, thought-provoking, use bullet points\n"
            "- For Twitter: Concise, engaging, thread-worthy\n"
            "- For Instagram: Visual storytelling, hashtag-friendly\n"
            "- For TikTok: Trend-aware, hook-focused\n"
            "- Each post should be complete and ready to publish\n"
            "- Include relevant hashtags where appropriate\n"
            "- End with engaging questions or calls-to-action\n\n"
            "SOURCE CONTENT:\n"
            f"{content_to_process[:8000]}\n\n"
            "Generate compelling posts for each platform. Use markdown headings to separate platforms (e.g., ## LinkedIn, ## Twitter)."
        )
        drafts = utils.run_ai_generation_sync(
            generation_prompt,
            user_id,
            model="gpt-4o",
            max_tokens=3000,
        )
        if not drafts:
            raise Exception("AI content generation failed - check your OpenAI API key and credits.")

        results = {
            "analysis": content_analysis,
            "posts": drafts,
            "platforms": platforms,
            "settings": {
                "tone": tone,
                "style": style,
                "additional_instructions": additional_instructions,
            },
        }

        # Record completion status
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "COMPLETED",
                progress_details={"description": "Content suite generated!", "percentage": 100},
                results=results,
            )

        logger.info(f"Content job {job_id} completed successfully")
    except Exception as e:
        logger.error(f"Content job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "FAILED",
                error_message=f"Content repurposing failed: {str(e)}",
            )
        # Re-raise to allow Celery to record the failure properly
        raise


@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    """Generate thumbnail images based on content.

    This task first uses an AI model to generate image prompts from the
    provided text, then invokes a stable diffusion engine to create
    thumbnail images.  It records progress updates and stores the
    resulting URLs in the job record.

    Args:
        job_id: Unique identifier for the background job.
        user_id: ID of the user requesting the job.
        prompt_text: Text on which to base thumbnail prompts.
    """
    try:
        logger.info(f"Starting thumbnail job {job_id} for user {user_id}")

        # Initial progress update
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "IN_PROGRESS",
                progress_details={"description": "Generating thumbnail prompts...", "percentage": 10},
            )

        # Prompt generation loop: attempt up to 3 times to obtain valid JSON prompts
        prompt_gen_prompt = (
            "Based on the following content, generate 3 striking visual prompts for thumbnail images.\n"
            "Return them as a JSON array of strings. Each prompt should be vivid, specific, and thumbnail-worthy.\n\n"
            f"CONTENT: {prompt_text[:2000]}\n\n"
            'Return format: ["prompt1", "prompt2", "prompt3"]'
        )

        image_prompts = []
        for attempt in range(3):
            response_str = utils.run_ai_generation_sync(
                prompt_gen_prompt,
                user_id,
                "gpt-4o-mini",
                500,
                expect_json=True,
            )
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts:
                        image_prompts = prompts
                        break
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse prompts on attempt {attempt + 1}: {e}")
        if not image_prompts:
            raise Exception("Failed to generate valid image prompts after 3 attempts.")

        # Generate images
        urls: list[str] = []
        for i, prompt in enumerate(image_prompts):
            # Update progress per thumbnail
            with get_db_session() as db:
                progress = 20 + int(((i + 1) / len(image_prompts)) * 75)
                crud.update_job_full_status(
                    db,
                    job_id,
                    "IN_PROGRESS",
                    progress_details={
                        "description": f"Generating thumbnail {i + 1}/{len(image_prompts)}...",
                        "percentage": progress,
                    },
                )

            # Generate an image for the prompt
            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, "thumbnail", custom_cost=0.0)
            else:
                logger.warning(f"Failed to generate image for prompt: {prompt}")
        if not urls:
            raise Exception("No thumbnails were successfully generated.")

        # Record completion status with results
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "COMPLETED",
                progress_details={"description": f"Generated {len(urls)} thumbnails!", "percentage": 100},
                results={"thumbnail_urls": urls, "prompts_used": image_prompts},
            )

        logger.info(f"Thumbnail job {job_id} completed with {len(urls)} images")
    except Exception as e:
        logger.error(f"Thumbnail job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "FAILED",
                error_message=f"Thumbnail generation failed: {str(e)}",
            )
        raise


@celery_app.task
def cleanup_old_files():
    """Clean up old files to prevent disk space issues.

    This daily maintenance task scans the uploads and temporary clips
    directories for files older than a configured cutoff (default one
    day) and deletes them.  It frees up disk space and logs details
    about the cleanup.
    """
    logger.info("Starting daily cleanup of old files...")
    try:
        # Lazy import settings to avoid circular dependencies
        from app.core.config import settings

        cleanup_age_days = 1
        cutoff = datetime.now() - timedelta(days=cleanup_age_days)

        upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
        temp_clips_dir = settings.STATIC_GENERATED_DIR

        patterns = [
            os.path.join(upload_dir, "*"),
            os.path.join(temp_clips_dir, "temp_*.mp4"),
            os.path.join(temp_clips_dir, "final_*.mp4"),
            os.path.join(temp_clips_dir, "captions_*.srt"),
            os.path.join(temp_clips_dir, "captions_*.ass"),
            os.path.join(temp_clips_dir, "*_audio.mp3"),
        ]

        files_removed = 0
        total_size_freed = 0
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mod_time < cutoff:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        files_removed += 1
                        total_size_freed += file_size
                        logger.info(f"Removed old file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")

        # Convert bytes to MB for logging
        size_mb = total_size_freed / (1024 * 1024)
        logger.info(
            f"✅ Daily cleanup finished. Removed {files_removed} files, freed {size_mb:.1f}MB"
        )
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
