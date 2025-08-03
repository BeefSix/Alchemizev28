# debug_upload.py - Save this file and run it to test the API directly

import requests
import os

# Configuration
BASE_URL = "http://localhost:8000"
EMAIL = "test@example.com"
PASSWORD = "testpassword123"
FULL_NAME = "Test User"

def test_upload():
    print("🧪 Testing Alchemize Upload API...")
    
    # Step 1: Register/Login
    print("\n1. Registering user...")
    register_response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": FULL_NAME}
    )
    
    if register_response.status_code in [200, 400]:  # 400 if already exists
        print("✅ User registration OK")
    else:
        print(f"❌ Registration failed: {register_response.text}")
        return

    print("\n2. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/token",
        data={"username": EMAIL, "password": PASSWORD}
    )
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print("✅ Login successful")
    else:
        print(f"❌ Login failed: {login_response.text}")
        return

    # Step 2: Create a tiny test video file
    print("\n3. Creating test video...")
    
    # Use FFmpeg to create a 5-second test video
    import subprocess
    test_video_path = "test_video.mp4"
    
    try:
        subprocess.run([
            "docker", "exec", "alchemize_worker", "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=1",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
            "-c:v", "libx264", "-t", "5", f"/app/data/static/generated/{test_video_path}"
        ], check=True, capture_output=True)
        print("✅ Test video created")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create test video: {e}")
        return

    # Step 3: Upload the video
    print("\n4. Uploading video with captions...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Read the test video
    with open(f"data/static/generated/{test_video_path}", "rb") as f:
        files = {"file": ("test_video.mp4", f, "video/mp4")}
        data = {
            "add_captions": "true",  # This should be the string "true"
            "aspect_ratio": "16:9"
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/v1/video/upload-and-clip",
            headers=headers,
            files=files,
            data=data
        )

    if upload_response.status_code == 202:
        job_data = upload_response.json()
        job_id = job_data["job_id"]
        print(f"✅ Upload successful! Job ID: {job_id}")
        print(f"📝 Message: {job_data['message']}")
        
        # Monitor the job
        print("\n5. Monitoring job progress...")
        import time
        
        for i in range(30):  # Wait up to 30 seconds
            status_response = requests.get(
                f"{BASE_URL}/api/v1/video/jobs/{job_id}",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data["status"]
                progress = status_data.get("progress_details", {})
                
                print(f"⏳ Status: {status} - {progress.get('description', 'Processing...')}")
                
                if status == "COMPLETED":
                    print("🎉 Job completed successfully!")
                    results = status_data.get("results", {})
                    clips = results.get("clips_by_platform", {}).get("all", [])
                    print(f"📹 Generated {len(clips)} clips")
                    print(f"🎤 Captions added: {results.get('captions_added', False)}")
                    return
                elif status == "FAILED":
                    print(f"❌ Job failed: {status_data.get('error_message')}")
                    return
                    
            time.sleep(2)
            
        print("⏰ Job is still running after 60 seconds")
        
    else:
        print(f"❌ Upload failed: {upload_response.status_code}")
        print(f"Response: {upload_response.text}")

if __name__ == "__main__":
    test_upload()