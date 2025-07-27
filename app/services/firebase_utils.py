# app/services/firebase_utils.py
import os
import firebase_admin
from firebase_admin import credentials, storage
from app.core.config import settings
import json

# Initialize Firebase only if it hasn't been initialized yet
if not firebase_admin._apps:
    try:
        creds_json_str = settings.FIREBASE_CREDENTIALS_JSON
        if creds_json_str:
            creds_json = json.loads(creds_json_str)
            cred = credentials.Certificate(creds_json)
            firebase_admin.initialize_app(cred, {
                'storageBucket': settings.FIREBASE_STORAGE_BUCKET
            })
            print("✅ Firebase initialized securely from environment variable.")
        else:
            print("❌ WARNING: FIREBASE_CREDENTIALS_JSON environment variable not found. File uploads will fail.")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")

def upload_to_storage(local_file_path: str, destination_blob_name: str) -> str | None:
    """Uploads a file to Firebase Cloud Storage and returns its public URL."""
    # Ensure the app is initialized before trying to use storage
    if not firebase_admin._apps:
        print("❌ Cannot upload to storage: Firebase app not initialized.")
        return None
        
    try:
        bucket = storage.bucket()
        blob = bucket.blob(destination_blob_name)
        
        blob.upload_from_filename(local_file_path)
        
        # Make the file public so it can be viewed in the browser
        blob.make_public()
        
        print(f"✅ Uploaded {local_file_path} to {destination_blob_name}.")
        return blob.public_url
    except Exception as e:
        print(f"❌ File upload to Firebase failed: {e}")
        return None