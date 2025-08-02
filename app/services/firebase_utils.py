# app/services/firebase_utils.py
import os
import logging
import firebase_admin
from firebase_admin import credentials, storage
from app.core.config import settings
import json

logger = logging.getLogger(__name__)

# Global flag to track Firebase initialization status
_firebase_initialized = False

def initialize_firebase():
    """Initialize Firebase with proper error handling"""
    global _firebase_initialized
    
    if _firebase_initialized or firebase_admin._apps:
        return True
        
    try:
        creds_json_str = settings.FIREBASE_CREDENTIALS_JSON
        if not creds_json_str or creds_json_str == "{}":
            logger.warning("Firebase credentials not provided - file uploads will use local storage only")
            return False
            
        if not settings.FIREBASE_STORAGE_BUCKET:
            logger.warning("Firebase storage bucket not configured - file uploads will use local storage only")
            return False
            
        creds_json = json.loads(creds_json_str)
        cred = credentials.Certificate(creds_json)
        firebase_admin.initialize_app(cred, {
            'storageBucket': settings.FIREBASE_STORAGE_BUCKET
        })
        
        _firebase_initialized = True
        logger.info("✅ Firebase initialized successfully")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid Firebase credentials JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        return False

def upload_to_storage(local_file_path: str, destination_blob_name: str) -> str | None:
    """
    Uploads a file to Firebase Cloud Storage and returns its public URL.
    Falls back gracefully if Firebase is not configured.
    """
    # Try to initialize Firebase if not already done
    if not initialize_firebase():
        logger.info(f"Firebase not available - keeping file local: {local_file_path}")
        return None
        
    if not os.path.exists(local_file_path):
        logger.error(f"Local file does not exist: {local_file_path}")
        return None
        
    try:
        bucket = storage.bucket()
        blob = bucket.blob(destination_blob_name)
        
        blob.upload_from_filename(local_file_path)
        blob.make_public()
        
        logger.info(f"✅ Uploaded {local_file_path} to Firebase: {destination_blob_name}")
        return blob.public_url
        
    except Exception as e:
        logger.error(f"Firebase upload failed for {local_file_path}: {e}")
        return None

def is_firebase_available() -> bool:
    """Check if Firebase is properly configured and available"""
    return initialize_firebase()

# Initialize Firebase on module import (but don't fail if it doesn't work)
initialize_firebase()