from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import hashlib
import tempfile
from pathlib import Path
from app.core.config import settings
from app.services.file_security import FileSecurityValidator
# from app.core.limiter import limiter
# from slowapi import Limiter
# from slowapi.util import get_remote_address
from fastapi import Request
import logging

logger = logging.getLogger(__name__)
# Force reload trigger
router = APIRouter()
file_security = FileSecurityValidator()

# In-memory storage for upload sessions (in production, use Redis)
upload_sessions = {}

class UploadInitRequest(BaseModel):
    filename: str
    file_size: int
    chunk_size: int = 1024 * 1024  # 1MB default
    content_type: Optional[str] = None

class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int
    expires_at: str

class ChunkUploadResponse(BaseModel):
    chunk_number: int
    uploaded: bool
    progress: float
    message: str

class UploadCompleteResponse(BaseModel):
    upload_id: str
    filename: str
    file_path: str
    file_size: int
    checksum: str
    message: str

@router.post("/init", response_model=UploadInitResponse)
# @limiter.limit("10/minute")
async def initialize_upload(
    upload_request: UploadInitRequest
):
    """
    Initialize a chunked file upload session.
    """
    try:
        # Create a mock UploadFile for validation
        from io import BytesIO
        from fastapi import UploadFile as FastAPIUploadFile
        
        # Create a temporary file object for validation
        mock_file_content = BytesIO(b'0' * min(upload_request.file_size, 1024))  # Mock first 1KB
        mock_upload_file = FastAPIUploadFile(
            filename=upload_request.filename,
            file=mock_file_content,
            size=upload_request.file_size,
            headers={"content-type": upload_request.content_type or "application/octet-stream"}
        )
        
        # Validate file metadata (skip MIME validation for initialization)
        validation_result = await file_security.validate_upload(
            mock_upload_file,
            file_type='video',
            skip_mime_validation=True
        )
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {validation_result['error']}"
            )
        
        # Generate upload session
        upload_id = str(uuid.uuid4())
        total_chunks = (upload_request.file_size + upload_request.chunk_size - 1) // upload_request.chunk_size
        
        # Create upload directory
        upload_dir = Path(settings.UPLOAD_DIR) / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Store session info
        upload_sessions[upload_id] = {
            "filename": upload_request.filename,
            "file_size": upload_request.file_size,
            "chunk_size": upload_request.chunk_size,
            "total_chunks": total_chunks,
            "uploaded_chunks": set(),
            "upload_dir": str(upload_dir),
            "content_type": upload_request.content_type,
            "created_at": "2024-01-01T00:00:00Z",  # In production, use actual timestamp
            "expires_at": "2024-01-02T00:00:00Z"   # In production, use actual expiry
        }
        
        logger.info(f"Initialized upload session {upload_id} for file {upload_request.filename}")
        
        return UploadInitResponse(
            upload_id=upload_id,
            chunk_size=upload_request.chunk_size,
            total_chunks=total_chunks,
            expires_at="2024-01-02T00:00:00Z"
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize upload")

@router.post("/chunk/{upload_id}", response_model=ChunkUploadResponse)
# @limiter.limit("100/minute")
async def upload_chunk(
    request: Request,
    upload_id: str,
    chunk_number: int = Form(...),
    chunk: UploadFile = File(...)
):
    """
    Upload a single chunk of the file.
    """
    try:
        # Validate upload session
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        
        # Validate chunk number
        if chunk_number < 0 or chunk_number >= session["total_chunks"]:
            raise HTTPException(status_code=400, detail="Invalid chunk number")
        
        # Check if chunk already uploaded
        if chunk_number in session["uploaded_chunks"]:
            progress = len(session["uploaded_chunks"]) / session["total_chunks"] * 100
            return ChunkUploadResponse(
                chunk_number=chunk_number,
                uploaded=True,
                progress=progress,
                message="Chunk already uploaded"
            )
        
        # Read and save chunk
        chunk_data = await chunk.read()
        chunk_path = Path(session["upload_dir"]) / f"chunk_{chunk_number:06d}"
        
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        # Mark chunk as uploaded
        session["uploaded_chunks"].add(chunk_number)
        progress = len(session["uploaded_chunks"]) / session["total_chunks"] * 100
        
        logger.info(f"Uploaded chunk {chunk_number} for session {upload_id} ({progress:.1f}% complete)")
        
        return ChunkUploadResponse(
            chunk_number=chunk_number,
            uploaded=True,
            progress=progress,
            message=f"Chunk {chunk_number} uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to upload chunk {chunk_number} for session {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload chunk")

@router.post("/complete/{upload_id}", response_model=UploadCompleteResponse)
# @limiter.limit("10/minute")
async def complete_upload(
    request: Request,
    upload_id: str
):
    """
    Complete the chunked upload by assembling all chunks.
    """
    try:
        # Validate upload session
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        
        # Check if all chunks are uploaded
        if len(session["uploaded_chunks"]) != session["total_chunks"]:
            missing_chunks = set(range(session["total_chunks"])) - session["uploaded_chunks"]
            raise HTTPException(
                status_code=400,
                detail=f"Missing chunks: {sorted(list(missing_chunks))}"
            )
        
        # Assemble file
        upload_dir = Path(session["upload_dir"])
        final_path = Path(settings.UPLOAD_DIR) / session["filename"]
        
        # Ensure unique filename
        counter = 1
        original_path = final_path
        while final_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            final_path = original_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # Combine chunks
        with open(final_path, "wb") as output_file:
            for chunk_num in range(session["total_chunks"]):
                chunk_path = upload_dir / f"chunk_{chunk_num:06d}"
                if chunk_path.exists():
                    with open(chunk_path, "rb") as chunk_file:
                        output_file.write(chunk_file.read())
        
        # Calculate checksum
        checksum = hashlib.md5()
        with open(final_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                checksum.update(chunk)
        
        file_checksum = checksum.hexdigest()
        
        # Cleanup chunks
        for chunk_num in range(session["total_chunks"]):
            chunk_path = upload_dir / f"chunk_{chunk_num:06d}"
            if chunk_path.exists():
                chunk_path.unlink()
        upload_dir.rmdir()
        
        # Final security validation
        final_validation = await file_security.validate_uploaded_file(str(final_path))
        if not final_validation["valid"]:
            final_path.unlink()  # Delete invalid file
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {final_validation['reason']}"
            )
        
        # Clean up session
        del upload_sessions[upload_id]
        
        logger.info(f"Completed upload for session {upload_id}: {final_path}")
        
        return UploadCompleteResponse(
            upload_id=upload_id,
            filename=final_path.name,
            file_path=str(final_path),
            file_size=final_path.stat().st_size,
            checksum=file_checksum,
            message="File uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to complete upload for session {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete upload")

@router.delete("/{upload_id}")
# @limiter.limit("20/minute")
async def cancel_upload(
    request: Request,
    upload_id: str
):
    """
    Cancel an upload session and clean up chunks.
    """
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        upload_dir = Path(session["upload_dir"])
        
        # Clean up chunks
        if upload_dir.exists():
            for chunk_file in upload_dir.glob("chunk_*"):
                chunk_file.unlink()
            upload_dir.rmdir()
        
        # Clean up session
        del upload_sessions[upload_id]
        
        logger.info(f"Cancelled upload session {upload_id}")
        
        return {"message": "Upload session cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Failed to cancel upload session {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel upload")

@router.get("/{upload_id}/status")
# @limiter.limit("30/minute")
async def get_upload_status(
    request: Request,
    upload_id: str
):
    """
    Get the status of an upload session.
    """
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        progress = len(session["uploaded_chunks"]) / session["total_chunks"] * 100
        
        return {
            "upload_id": upload_id,
            "filename": session["filename"],
            "total_chunks": session["total_chunks"],
            "uploaded_chunks": len(session["uploaded_chunks"]),
            "progress": progress,
            "status": "complete" if progress == 100 else "in_progress"
        }
        
    except Exception as e:
        logger.error(f"Failed to get upload status for session {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get upload status")