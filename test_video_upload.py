#!/usr/bin/env python3
"""
Test video upload and job creation process
"""

import requests
import json
import io

def create_test_video_file():
    """Create a minimal test video file in memory"""
    # Create a larger test file (minimum 1024 bytes as required)
    test_content = b"fake video content for testing " * 50  # Make it larger
    return io.BytesIO(test_content)

def test_video_upload():
    """Test the complete video upload and job creation process"""
    print("🎬 Testing Video Upload Process")
    print("=" * 50)
    
    # API configuration
    base_url = "http://localhost:8000/api/v1"
    
    # Test credentials
    login_data = {
        "username": "testuser@example.com",
        "password": "ValidPassword2024!"
    }
    
    try:
        # Step 1: Login
        print("1️⃣ Logging in...")
        login_response = requests.post(
            f"{base_url}/auth/token",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return
            
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print(f"✅ Login successful!")
        
        # Step 2: Test video upload
        print("\n2️⃣ Testing video upload...")
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # Create test file
        test_file = create_test_video_file()
        
        # Prepare upload data
        files = {
            'file': ('test_video.mp4', test_file, 'video/mp4')
        }
        
        data = {
            "add_captions": "true",
            "aspect_ratio": "9:16",
            "platforms": "TikTok,Instagram"
        }
        
        print(f"   Uploading to: {base_url}/video/upload-and-clip")
        
        upload_response = requests.post(
            f"{base_url}/video/upload-and-clip",
            headers=headers,
            files=files,
            data=data
        )
        
        print(f"   Upload status: {upload_response.status_code}")
        
        if upload_response.status_code == 202:
            response_data = upload_response.json()
            job_id = response_data.get('job_id')
            print(f"   ✅ Upload successful!")
            print(f"   Job ID: {job_id}")
            
            # Step 3: Test job status retrieval
            print("\n3️⃣ Testing job status retrieval...")
            
            job_status_url = f"{base_url}/video/jobs/{job_id}"
            print(f"   Checking: {job_status_url}")
            
            status_response = requests.get(job_status_url, headers=headers)
            print(f"   Status check result: {status_response.status_code}")
            
            if status_response.status_code == 200:
                job_data = status_response.json()
                print(f"   ✅ Job status retrieved successfully!")
                print(f"   Job status: {job_data.get('status')}")
                print(f"   Job ID: {job_data.get('id')}")
                return True
            else:
                print(f"   ❌ Job status retrieval failed")
                print(f"   Response: {status_response.text}")
                return False
                
        else:
            print(f"   ❌ Upload failed")
            print(f"   Response: {upload_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_video_upload()
    print("\n" + "=" * 50)
    if success:
        print("🎉 Video upload and job status test completed successfully!")
    else:
        print("❌ Video upload test failed.")