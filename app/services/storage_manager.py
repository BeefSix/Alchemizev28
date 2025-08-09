"""Enhanced storage management service with S3 support, retention policies, and quotas."""

import os
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import hashlib

from app.core.config import settings
from app.database.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class StorageQuota:
    """Storage quota configuration"""
    max_total_size: int  # bytes
    max_files_per_user: int
    max_file_age_days: int
    cleanup_threshold: float = 0.8  # Cleanup when 80% full
    emergency_cleanup_threshold: float = 0.95  # Emergency cleanup when 95% full

class S3StorageManager:
    """S3-compatible storage manager"""
    
    def __init__(self, config: dict):
        self.bucket_name = config['s3_bucket']
        self.region = config['s3_region']
        self.endpoint_url = config.get('s3_endpoint_url')
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config['s3_access_key'],
            aws_secret_access_key=config['s3_secret_key'],
            region_name=self.region,
            endpoint_url=self.endpoint_url
        )
        
        # Test connection
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3 connection established to bucket: {self.bucket_name}")
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"❌ S3 connection failed: {e}")
            raise
    
    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """Upload file to S3"""
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            logger.info(f"✅ Uploaded {local_path} to S3: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3"""
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"✅ Downloaded S3:{s3_key} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"❌ S3 download failed: {e}")
            return False
    
    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"✅ Deleted S3 file: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ S3 delete failed: {e}")
            return False
    
    def get_file_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate presigned URL for file access"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            return None

class StorageManager:
    """Enhanced storage manager with S3 support and comprehensive retention policies"""
    
    def __init__(self):
        self.config = settings.STORAGE_CONFIG
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.temp_dir = Path(settings.TEMP_DIR)
        self.static_dir = Path(settings.STATIC_DIR)
        
        # Initialize storage backend
        if self.config['backend'] == 's3':
            self.s3_manager = S3StorageManager(self.config)
            self.storage_backend = 's3'
        else:
            self.s3_manager = None
            self.storage_backend = 'local'
        
        # Storage quotas
        self.quota = StorageQuota(
            max_total_size=self.config['max_total_storage_gb'] * 1024 * 1024 * 1024,
            max_files_per_user=self.config['max_files_per_user'],
            max_file_age_days=self.config['max_file_age_days'],
            cleanup_threshold=self.config['cleanup_threshold_percent'] / 100,
            emergency_cleanup_threshold=self.config['emergency_cleanup_threshold_percent'] / 100
        )
        
        # Ensure directories exist for local storage
        if self.storage_backend == 'local':
            self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        for directory in [self.upload_dir, self.temp_dir, self.static_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def get_storage_usage(self, db: Session) -> Dict[str, Union[int, float]]:
        """Get current storage usage statistics"""
        try:
            # Get total file count and size from database
            result = db.execute(
                text("""
                    SELECT 
                        COUNT(*) as file_count,
                        COALESCE(SUM(file_size), 0) as total_size,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM file_uploads 
                    WHERE deleted_at IS NULL
                """)
            ).fetchone()
            
            total_size = result.total_size or 0
            usage_percent = (total_size / self.quota.max_total_size) * 100 if self.quota.max_total_size > 0 else 0
            
            return {
                'total_files': result.file_count or 0,
                'total_size_bytes': total_size,
                'total_size_gb': total_size / (1024**3),
                'usage_percent': usage_percent,
                'unique_users': result.unique_users or 0,
                'quota_remaining_bytes': max(0, self.quota.max_total_size - total_size),
                'quota_remaining_gb': max(0, (self.quota.max_total_size - total_size) / (1024**3))
            }
            
        except Exception as e:
            logger.error(f"Error getting storage usage: {e}")
            return {
                'total_files': 0,
                'total_size_bytes': 0,
                'total_size_gb': 0,
                'usage_percent': 0,
                'unique_users': 0,
                'quota_remaining_bytes': self.quota.max_total_size,
                'quota_remaining_gb': self.quota.max_total_size / (1024**3)
            }
    
    def check_user_quota(self, db: Session, user_id: str, file_size: int) -> Tuple[bool, str]:
        """Check if user can upload file based on quotas"""
        try:
            # Check user's current usage
            user_usage = db.execute(
                text("""
                    SELECT 
                        COUNT(*) as file_count,
                        COALESCE(SUM(file_size), 0) as total_size
                    FROM file_uploads 
                    WHERE user_id = :user_id AND deleted_at IS NULL
                """),
                {"user_id": user_id}
            ).fetchone()
            
            current_files = user_usage.file_count or 0
            current_size = user_usage.total_size or 0
            
            # Check file count limit
            if current_files >= self.quota.max_files_per_user:
                return False, f"User has reached maximum file limit ({self.quota.max_files_per_user})"
            
            # Check total size limit
            if current_size + file_size > self.quota.max_total_size:
                return False, f"Upload would exceed storage quota"
            
            return True, "Quota check passed"
            
        except Exception as e:
            logger.error(f"Error checking user quota: {e}")
            return False, "Error checking quota"
    
    def cleanup_old_files(self, db: Session) -> Dict[str, int]:
        """Enhanced cleanup with multiple retention policies"""
        cleanup_stats = {
            'temp_files_deleted': 0,
            'processed_files_deleted': 0,
            'user_files_deleted': 0,
            'total_space_freed': 0
        }
        
        try:
            # Clean up temp files (24 hours)
            temp_cutoff = datetime.now() - timedelta(hours=self.config['temp_file_retention_hours'])
            temp_files = db.execute(
                text("""
                    SELECT id, file_path, file_size, s3_key
                    FROM file_uploads 
                    WHERE created_at < :cutoff_date 
                    AND file_type = 'temp' 
                    AND deleted_at IS NULL
                """),
                {"cutoff_date": temp_cutoff}
            ).fetchall()
            
            for file_record in temp_files:
                if self._delete_file_record(file_record, db):
                    cleanup_stats['temp_files_deleted'] += 1
                    cleanup_stats['total_space_freed'] += file_record.file_size or 0
            
            # Clean up processed files (7 days)
            processed_cutoff = datetime.now() - timedelta(days=self.config['processed_file_retention_days'])
            processed_files = db.execute(
                text("""
                    SELECT id, file_path, file_size, s3_key
                    FROM file_uploads 
                    WHERE created_at < :cutoff_date 
                    AND file_type = 'processed' 
                    AND deleted_at IS NULL
                """),
                {"cutoff_date": processed_cutoff}
            ).fetchall()
            
            for file_record in processed_files:
                if self._delete_file_record(file_record, db):
                    cleanup_stats['processed_files_deleted'] += 1
                    cleanup_stats['total_space_freed'] += file_record.file_size or 0
            
            # Clean up old user files (30 days)
            user_cutoff = datetime.now() - timedelta(days=self.config['user_file_retention_days'])
            user_files = db.execute(
                text("""
                    SELECT id, file_path, file_size, s3_key
                    FROM file_uploads 
                    WHERE created_at < :cutoff_date 
                    AND file_type = 'user_upload' 
                    AND deleted_at IS NULL
                """),
                {"cutoff_date": user_cutoff}
            ).fetchall()
            
            for file_record in user_files:
                if self._delete_file_record(file_record, db):
                    cleanup_stats['user_files_deleted'] += 1
                    cleanup_stats['total_space_freed'] += file_record.file_size or 0
            
            db.commit()
            logger.info(f"Cleanup completed: {cleanup_stats}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            db.rollback()
        
        return cleanup_stats
    
    def _delete_file_record(self, file_record, db: Session) -> bool:
        """Delete file record and actual file"""
        try:
            # Delete from storage
            if self.storage_backend == 's3' and file_record.s3_key:
                self.s3_manager.delete_file(file_record.s3_key)
            elif self.storage_backend == 'local' and file_record.file_path:
                file_path = Path(file_record.file_path)
                if file_path.exists():
                    file_path.unlink()
            
            # Mark as deleted in database
            db.execute(
                text("""
                    UPDATE file_uploads 
                    SET deleted_at = :now 
                    WHERE id = :file_id
                """),
                {"now": datetime.now(), "file_id": file_record.id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file record {file_record.id}: {e}")
            return False
    
    def emergency_cleanup(self, db: Session) -> Dict[str, int]:
        """Emergency cleanup when storage is critically full"""
        logger.warning("🚨 Emergency cleanup triggered - storage critically full")
        
        # Get current usage
        usage = self.get_storage_usage(db)
        
        if usage['usage_percent'] < self.quota.emergency_cleanup_threshold * 100:
            return {'deleted_files': 0, 'freed_space': 0}
        
        # Delete oldest files first until we're under threshold
        target_size = self.quota.max_total_size * self.quota.cleanup_threshold
        current_size = usage['total_size_bytes']
        
        deleted_count = 0
        freed_space = 0
        
        try:
            # Get oldest files
            old_files = db.execute(
                text("""
                    SELECT id, file_path, file_size, s3_key
                    FROM file_uploads 
                    WHERE deleted_at IS NULL
                    ORDER BY created_at ASC
                """)
            ).fetchall()
            
            for file_record in old_files:
                if current_size - freed_space <= target_size:
                    break
                
                if self._delete_file_record(file_record, db):
                    deleted_count += 1
                    freed_space += file_record.file_size or 0
            
            db.commit()
            logger.warning(f"Emergency cleanup completed: {deleted_count} files deleted, {freed_space} bytes freed")
            
        except Exception as e:
            logger.error(f"Error during emergency cleanup: {e}")
            db.rollback()
        
        return {
            'deleted_files': deleted_count,
            'freed_space': freed_space
        }
    
    def save_file(self, file_path: str, user_id: str, file_type: str = 'user_upload') -> Optional[str]:
        """Save file with proper storage backend handling"""
        try:
            if self.storage_backend == 's3':
                # Generate S3 key
                file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
                s3_key = f"uploads/{user_id}/{file_type}/{file_hash}_{Path(file_path).name}"
                
                # Upload to S3
                if self.s3_manager.upload_file(file_path, s3_key):
                    # Clean up local file after successful upload
                    os.remove(file_path)
                    return s3_key
                else:
                    return None
            else:
                # Local storage - return the local path
                return str(file_path)
                
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None
    
    def get_file_url(self, file_record) -> Optional[str]:
        """Get file URL for access"""
        try:
            if self.storage_backend == 's3' and file_record.s3_key:
                return self.s3_manager.get_file_url(file_record.s3_key)
            elif self.storage_backend == 'local' and file_record.file_path:
                return f"/static/uploads/{Path(file_record.file_path).name}"
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting file URL: {e}")
            return None

# Global storage manager instance
storage_manager = StorageManager()