import os
import magic
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from fastapi import UploadFile, HTTPException
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class FileSecurityValidator:
    """Comprehensive file upload security validation"""
    
    # Allowed MIME types for video files
    ALLOWED_VIDEO_MIMES = {
        'video/mp4',
        'video/quicktime',  # .mov
        'video/x-msvideo',  # .avi
        'video/x-matroska', # .mkv
        'video/webm',
        'video/x-ms-wmv',   # .wmv
        'video/3gpp',       # .3gp
        'video/x-flv',      # .flv
        'video/mp4v-es',    # .m4v
        'video/ogg',        # .ogv
        'video/mp2t',       # .ts, .mts, .m2ts
        'video/x-ms-asf',   # .asf
        'video/vnd.rn-realvideo',  # .rm, .rmvb
        'video/dvd',        # .vob
        'video/mpeg',       # .mpg, .mpeg, .m2v
        'video/x-mpeg',     # additional mpeg variants
    }
    
    # Dangerous file extensions to always reject
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
        '.jar', '.app', '.deb', '.pkg', '.dmg', '.iso', '.msi', '.dll',
        '.so', '.dylib', '.php', '.asp', '.jsp', '.py', '.rb', '.pl',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.psm1'
    }
    
    # Maximum file sizes by type (in bytes) - Enhanced security limits
    MAX_SIZES = {
        'video': 2 * 1024 * 1024 * 1024,  # 2GB max for video processing
        'audio': 500 * 1024 * 1024,       # 500MB for audio
        'image': 50 * 1024 * 1024,        # 50MB for images
        'text': 1 * 1024 * 1024,          # 1MB for text files
    }
    
    # Maximum video duration (in seconds)
    MAX_VIDEO_DURATION = 3600  # 1 hour
    
    # Minimum file sizes to prevent empty/corrupted uploads
    MIN_SIZES = {
        'video': 1024,  # 1KB minimum
        'audio': 512,   # 512B minimum
        'image': 256,   # 256B minimum
        'text': 64,     # 64B minimum
    }
    
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)
    
    async def validate_upload(self, file: UploadFile, user_id: Optional[str] = None, file_type: str = 'video', skip_mime_validation: bool = False, skip_user_limits: bool = False) -> Dict[str, Any]:
        """Enhanced comprehensive file validation with security checks
        
        Returns:
            Dict[str, Any]: Validation result with detailed information
        """
        try:
            # 1. Basic file checks
            if not file.filename:
                return {'valid': False, 'error': 'No filename provided'}
            
            # 2. Enhanced filename sanitization and validation
            sanitized_filename = self._sanitize_filename(file.filename)
            if not sanitized_filename:
                return {'valid': False, 'error': 'Invalid filename after sanitization'}
            
            # 3. Check file extension
            file_ext = Path(sanitized_filename).suffix.lower()
            if file_ext in self.DANGEROUS_EXTENSIONS:
                return {'valid': False, 'error': f'File type {file_ext} is not allowed for security reasons'}
            
            # 4. File type specific validation
            if file_type == 'video':
                allowed_extensions = settings.ALLOWED_VIDEO_EXTENSIONS
                max_size = self.MAX_SIZES['video']
                min_size = self.MIN_SIZES['video']
            elif file_type == 'image':
                allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
                max_size = self.MAX_SIZES['image']
                min_size = self.MIN_SIZES['image']
            elif file_type == 'audio':
                allowed_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.ogg']
                max_size = self.MAX_SIZES['audio']
                min_size = self.MIN_SIZES['audio']
            else:
                return {'valid': False, 'error': f'Unsupported file type: {file_type}'}
            
            if file_ext not in allowed_extensions:
                return {
                    'valid': False, 
                    'error': f'Invalid file extension. Allowed: {", ".join(allowed_extensions)}'
                }
            
            # 5. Enhanced file size validation
            content = await file.read()
            file_size = len(content)
            
            if file_size == 0:
                return {'valid': False, 'error': 'File is empty'}
            
            if file_size < min_size:
                return {
                    'valid': False, 
                    'error': f'File too small. Minimum size: {min_size} bytes'
                }
            
            if file_size > max_size:
                max_mb = max_size / (1024 * 1024)
                return {
                    'valid': False, 
                    'error': f'File too large: {file_size / (1024*1024):.1f}MB. Max allowed: {max_mb:.1f}MB'
                }
            
            # 6. Enhanced MIME type validation
            mime_type = 'unknown'
            if not skip_mime_validation:
                try:
                    mime_type = magic.from_buffer(content[:2048], mime=True)
                    
                    # Strict MIME type validation
                    if file_type == 'video':
                        if mime_type not in self.ALLOWED_VIDEO_MIMES:
                            return {'valid': False, 'error': f'Invalid video MIME type: {mime_type}'}
                    elif file_type == 'image':
                        if not mime_type.startswith('image/'):
                            return {'valid': False, 'error': f'Invalid image MIME type: {mime_type}'}
                            
                except Exception as e:
                    logger.warning(f"MIME type detection failed: {e}")
                    # Fallback to extension-based validation
                    pass
            
            # 7. Enhanced content validation
            if file_type == 'video' and not skip_mime_validation:
                if not self._validate_video_headers(content[:1024]):
                    return {'valid': False, 'error': 'Invalid or corrupted video file format'}
            
            # 8. Malware/suspicious content detection
            if self._contains_suspicious_content(content[:8192]):
                return {'valid': False, 'error': 'File contains suspicious content'}
            
            # 9. Path traversal protection
            if self._has_path_traversal(file.filename):
                return {'valid': False, 'error': 'Filename contains invalid path characters'}
            
            # 10. User-specific rate limiting (if user_id provided and not skipped)
            if user_id and not skip_user_limits and not await self._check_user_limits(user_id, file_size):
                return {'valid': False, 'error': f'Upload limit exceeded. Max {settings.MAX_FILES_PER_USER_PER_DAY} files per day.'}
            
            # Reset file position for subsequent reads
            await file.seek(0)
            
            return {
                'valid': True,
                'filename': sanitized_filename,
                'original_filename': file.filename,
                'size': file_size,
                'mime_type': mime_type,
                'file_type': file_type
            }
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return {'valid': False, 'error': f'Validation failed: {str(e)}'}
    
    def _validate_video_headers(self, content: bytes) -> bool:
        """Validate video file headers/magic numbers"""
        if len(content) < 12:
            return False
        
        # Common video file signatures
        video_signatures = [
            b'\x00\x00\x00\x18ftypmp4',  # MP4
            b'\x00\x00\x00\x20ftypmp4',  # MP4 variant
            b'\x00\x00\x00\x1cftypisom', # MP4 ISO
            b'\x00\x00\x00\x20ftypisom', # MP4 ISO variant
            b'moov',                      # QuickTime
            b'mdat',                      # QuickTime data
            b'RIFF',                      # AVI (RIFF container)
            b'\x1aE\xdf\xa3',            # Matroska/WebM EBML header
            b'\x1a\x45\xdf\xa3',        # Alternative Matroska EBML header
            b'FLV\x01',                   # FLV
            b'\x00\x00\x01\xba',         # MPEG
            b'\x00\x00\x01\xb3',         # MPEG video
        ]
        
        # Check for any matching signature in first 512 bytes
        for signature in video_signatures:
            if signature in content[:512]:  # Increased search range
                return True
        
        # Special handling for Matroska/MKV files - check for EBML signature
        if len(content) >= 4 and content[:4] == b'\x1a\x45\xdf\xa3':
            return True
            
        # Additional MKV/WebM checks - look for "matroska" or "webm" strings
        content_lower = content[:1024].lower()
        if b'matroska' in content_lower or b'webm' in content_lower:
            return True
        
        return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Enhanced filename sanitization to prevent directory traversal and other attacks"""
        import re
        
        # Remove path separators and dangerous characters
        filename = os.path.basename(filename)
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)  # Remove control characters
        
        # Prevent reserved names on Windows
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
        name_without_ext = Path(filename).stem.upper()
        if name_without_ext in reserved_names:
            filename = f"file_{filename}"
        
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        
        # Ensure filename is not empty
        if not filename:
            filename = "upload"
        
        # Limit filename length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename
    
    def _has_path_traversal(self, filename: str) -> bool:
        """Check for path traversal attempts"""
        dangerous_patterns = [
            '..',
            '/',
            '\\',
            ':',
            '~',
        ]
        
        return any(pattern in filename for pattern in dangerous_patterns)
    
    async def _check_user_limits(self, user_id: str, file_size: int) -> bool:
        """Check user upload limits (daily files and total size)"""
        try:
            # Check user's subscription plan from database
            from app.db.base import get_db
            from app.db import crud
            
            db = next(get_db())
            try:
                user = crud.get_user(db, user_id=int(user_id))
                if user and user.subscription_plan == 'enterprise':
                    # Enterprise users have unlimited uploads
                    return True
            except Exception as db_error:
                logger.error(f"Error checking user subscription: {db_error}")
            finally:
                db.close()
            
            # For non-enterprise users, check file-based limits
            from datetime import datetime, timedelta
            import json
            
            limits_file = self.upload_dir / f"limits_{user_id}.json"
            today = datetime.now().date().isoformat()
            
            if limits_file.exists():
                with open(limits_file, 'r') as f:
                    limits_data = json.load(f)
                
                # Clean old entries
                limits_data = {
                    date: data for date, data in limits_data.items()
                    if datetime.fromisoformat(date).date() >= datetime.now().date() - timedelta(days=1)
                }
            else:
                limits_data = {}
            
            # Check today's limits
            today_data = limits_data.get(today, {'files': 0, 'total_size': 0})
            
            if today_data['files'] >= settings.MAX_FILES_PER_USER_PER_DAY:
                return False
            
            # Update limits
            today_data['files'] += 1
            today_data['total_size'] += file_size
            limits_data[today] = today_data
            
            # Save updated limits
            with open(limits_file, 'w') as f:
                json.dump(limits_data, f)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking user limits: {e}")
            return True  # Allow upload if limit check fails
    
    def generate_secure_filename(self, original_filename: str, user_id: Optional[str] = None) -> str:
        """Generate a secure, unique filename"""
        # Sanitize original filename
        safe_name = self._sanitize_filename(original_filename)
        name, ext = os.path.splitext(safe_name)
        
        # Generate unique identifier
        import time
        import uuid
        
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        # Create secure filename
        if user_id:
            secure_name = f"{user_id}_{timestamp}_{unique_id}_{name}{ext}"
        else:
            secure_name = f"{timestamp}_{unique_id}_{name}{ext}"
        
        return secure_name
    
    def get_safe_upload_path(self, filename: str, user_id: Optional[str] = None) -> Path:
        """Get safe upload path with directory traversal protection"""
        secure_filename = self.generate_secure_filename(filename, user_id)
        
        # Create user-specific subdirectory if user_id provided
        if user_id:
            user_dir = self.upload_dir / user_id[:2] / user_id  # Two-level directory structure
            user_dir.mkdir(parents=True, exist_ok=True)
            return user_dir / secure_filename
        
        return self.upload_dir / secure_filename
    
    async def save_upload(self, file: UploadFile, user_id: Optional[str] = None, file_type: str = 'video') -> Dict[str, Any]:
        """Enhanced secure file saving with atomic operations
        
        Returns:
            Dict[str, Any]: Upload result with detailed information
        """
        temp_path = None
        try:
            # Validate file first
            validation = await self.validate_upload(file, user_id, file_type)
            if not validation['valid']:
                return validation
            
            # Get secure file path
            file_path = self.get_safe_upload_path(validation['filename'], user_id)
            temp_path = f"{file_path}.tmp"
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to temporary file first (atomic operation)
            content = await file.read()
            with open(temp_path, 'wb') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Verify file integrity
            saved_size = os.path.getsize(temp_path)
            if saved_size != validation['size']:
                raise ValueError("File corruption during save")
            
            # Atomic move to final location
            os.rename(temp_path, file_path)
            temp_path = None  # Successfully moved
            
            # Set secure file permissions (read-only for group/others)
            os.chmod(file_path, 0o644)
            
            logger.info(f"File uploaded successfully: {file_path}")
            
            return {
                'valid': True,
                'message': 'File uploaded successfully',
                'file_path': str(file_path),
                'filename': validation['filename'],
                'original_filename': validation['original_filename'],
                'size': saved_size,
                'mime_type': validation.get('mime_type', 'unknown')
            }
            
        except Exception as e:
            # Clean up temporary file if it exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            logger.error(f"File upload error: {e}")
            return {'valid': False, 'error': f'Upload failed: {str(e)}'}
    
    async def save_upload_securely(self, file: UploadFile, file_path: Path) -> Tuple[Path, float]:
        """Securely save uploaded file with size tracking
        
        Returns:
            Tuple[Path, float]: (saved_file_path, file_size_mb)
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file with size tracking
            total_size = 0
            chunk_size = 8192  # 8KB chunks
            max_size = self.MAX_SIZES['video']
            
            with open(file_path, 'wb') as f:
                while chunk := await file.read(chunk_size):
                    total_size += len(chunk)
                    
                    # Check size during upload to prevent DoS
                    if total_size > max_size:
                        f.close()
                        if file_path.exists():
                            file_path.unlink()
                        raise HTTPException(
                            status_code=400,
                            detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB"
                        )
                    
                    f.write(chunk)
            
            # Final size check
            if total_size < 1024:  # 1KB minimum
                if file_path.exists():
                    file_path.unlink()
                raise HTTPException(status_code=400, detail="File too small")
            
            # Set secure file permissions
            os.chmod(file_path, 0o644)
            
            file_size_mb = total_size / (1024 * 1024)
            return file_path, file_size_mb
            
        except Exception as e:
            # Clean up on error
            if file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
            raise e

    def _contains_suspicious_content(self, content: bytes) -> bool:
        """Basic malware/suspicious content detection"""
        suspicious_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'<?php',
            b'<%',
            b'eval(',
            b'exec(',
            b'system(',
            b'shell_exec(',
            b'\x4d\x5a',  # PE executable header
            b'\x7f\x45\x4c\x46',  # ELF executable header
        ]
        
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in suspicious_patterns)

    async def validate_uploaded_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a completed uploaded file for security and integrity
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Dict with validation result
        """
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return {'valid': False, 'reason': 'File not found'}
            
            # Check file size
            file_size = path.stat().st_size
            if file_size < self.MIN_SIZES['video']:
                return {'valid': False, 'reason': f'File too small: {file_size} bytes'}
            
            if file_size > self.MAX_SIZES['video']:
                return {'valid': False, 'reason': f'File too large: {file_size} bytes'}
            
            # Check file extension
            file_ext = path.suffix.lower()
            if file_ext in self.DANGEROUS_EXTENSIONS:
                return {'valid': False, 'reason': f'Dangerous file type: {file_ext}'}
            
            # Read first few bytes to check MIME type
            with open(path, 'rb') as f:
                header = f.read(1024)
                
                # Check for suspicious content
                if self._contains_suspicious_content(header):
                    return {'valid': False, 'reason': 'Suspicious content detected'}
                
                # Validate video headers for video files
                if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                    if not self._validate_video_headers(header):
                        return {'valid': False, 'reason': 'Invalid video file format'}
            
            return {'valid': True, 'reason': 'File validation passed'}
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}

# Global file security validator
file_validator = FileSecurityValidator()