"""
Refactored Celery video-processing tasks.

This module contains helper functions and a Celery task for processing
uploaded videos.  Responsibilities are split into smaller functions to
improve readability and testability.  The task extracts audio, optionally
transcribes it, generates multiple clips, updates progress in the
database, and handles cleanup.

You should replace the existing `run_videoclip_upload_job` function in
`app/workers/tasks.py` with the one provided here.  Make sure to
update your imports accordingly (e.g. import from
`app.workers.video_tasks` instead of `app.workers.tasks`).

Note: This code assumes the presence of `app.celery_app.celery_app`,
`app.db.crud`, `app.db.base.get_db_session`, and `app.services.video_engine`
as defined in your repository.  You may need to adjust import paths
based on your actual project structure.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db_session
from app.services import video_engine, utils


logger = logging.getLogger(__name__)


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract the audio track from a video file using ffmpeg.

    Raises:
        RuntimeError: if ffmpeg returns a non-zero exit status.
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "mp3",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")


def transcribe_audio(audio_path: Path, user_id: int, job_id: str) -> List[dict]:
    """Call the transcription service and return word-level data.

    If transcription fails, returns an empty list.
    """
    result = utils.transcribe_local_audio_file_sync(str(audio_path), user_id, job_id)
    if not result or not result.get("success"):
        return []
    data = result.get("data", {})
    return data.get("words", [])


def generate_clip(
    video_path: Path,
    start: float,
    duration: float,
    add_captions: bool,
    aspect_ratio: str,
    clip_id: str,
    words_data: List[dict],
) -> dict:
    """Invoke the video engine to cut a single clip.

    Returns whatever the underlying video_engine returns.  Typically this
    dictionary contains a `success` flag and either a `url` or an `error`.
    """
    moment = {"start": start, "duration": duration}
    return video_engine.process_single_clip(
        str(video_path),
        moment,
        {"add_captions": add_captions, "aspect_ratio": aspect_ratio},
        clip_id=clip_id,
        words_data=words_data,
    )


def update_progress(job_id: str, description: str, percentage: int) -> None:
    """Helper to update a job's progress status in the database."""
    with get_db_session() as db:
        crud.update_job_full_status(
            db,
            job_id,
            "IN_PROGRESS",
            progress_details={"description": description, "percentage": percentage},
        )


@celery_app.task(bind=True, name="run_videoclip_upload_job", queue="gpu")
def run_videoclip_upload_job(
    self,
    job_id: str,
    user_id: int,
    video_path: str,
    add_captions: bool,
    aspect_ratio: str,
    platforms: List[str],
) -> None:
    """Celery task: orchestrate video processing steps.

    This task validates the input video, extracts audio, optionally
    transcribes the audio, generates multiple clips evenly spaced
    throughout the original video, updates progress as it goes, and
    records the final result in the database.  On failure, it marks the
    job as FAILED and logs the error.
    """
    video = Path(video_path)
    if not video.exists():
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "FAILED",
                error_message=f"Video file not found: {video_path}",
            )
        return

    audio_path: Path | None = None
    try:
        # Step 1: extract audio
        update_progress(job_id, "Extracting audio…", 10)
        audio_path = video.with_name(f"{job_id}_audio.mp3")
        extract_audio(video, audio_path)

        # Step 2: transcribe (optional)
        words_data: List[dict] = []
        if add_captions:
            update_progress(job_id, "Transcribing audio…", 20)
            words_data = transcribe_audio(audio_path, user_id, job_id)

        # Step 3: determine clip parameters
        duration = video_engine.get_duration(str(video))
        num_clips = min(5, max(1, int(duration // 30)))
        clip_length = min(60, duration * 0.8)

        # Step 4: generate clips
        clips_created: List[str] = []
        for i in range(num_clips):
            start = (duration / (num_clips + 1)) * (i + 1) - clip_length / 2
            start = max(0.0, min(start, duration - clip_length))
            clip_id = f"{job_id}_clip_{i+1}"
            progress_pct = 30 + int((i / num_clips) * 50)
            update_progress(job_id, f"Creating clip {i+1}/{num_clips}", progress_pct)
            result = generate_clip(
                video,
                start,
                clip_length,
                add_captions,
                aspect_ratio,
                clip_id,
                words_data,
            )
            if result.get("success"):
                clips_created.append(result["url"])
            else:
                logger.warning(
                    "Clip %s failed: %s", clip_id, result.get("error", "unknown error")
                )

        if not clips_created:
            raise RuntimeError("No clips were generated successfully")

        # Step 5: mark job complete
        with get_db_session() as db:
            crud.update_job_full_status(
                db,
                job_id,
                "COMPLETED",
                progress_details={
                    "description": f"Generated {len(clips_created)} clips!",
                    "percentage": 100,
                },
                results={"clips": clips_created, "duration": duration},
            )

        logger.info("Video job %s completed successfully", job_id)

    except Exception as exc:
        logger.exception("Video job %s failed: %s", job_id, exc)
        with get_db_session() as db:
            crud.update_job_full_status(
                db, job_id, "FAILED", error_message=str(exc)
            )
    finally:
        # Clean up temporary audio file
        if audio_path is not None and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception as cleanup_err:
                logger.warning(
                    "Failed to remove temporary audio file %s: %s", audio_path, cleanup_err
                )
