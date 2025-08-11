import requests
import os
import json
from datetime import datetime

# Test configuration
API_BASE = "http://localhost:8001"
TEST_EMAIL = f"test-{int(datetime.now().timestamp())}@example.com"
TEST_PASSWORD = "TestPassword123!"

def register_user():
    """Register a test user"""
    url = f"{API_BASE}/api/v1/auth/register"
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Test User"
    }
    
    response = requests.post(url, json=data)
    print(f"Registration Status: {response.status_code}")
    if response.status_code == 400:
        print("User might already exist, continuing...")
    elif response.status_code == 200:
        print("User registered successfully")
    else:
        print(f"Registration failed: {response.text}")
        return False
    return True

def login_user():
    """Login and get access token"""
    url = f"{API_BASE}/api/v1/auth/token"
    data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(url, data=data)
    print(f"Login Status: {response.status_code}")
    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None

def test_video_upload(access_token):
    """Test video upload with authentication"""
    url = f"{API_BASE}/api/v1/video/upload-and-clip"
    
    # Check if test video exists
    if not os.path.exists("test_video.mp4"):
        print("❌ test_video.mp4 not found")
        return False
    
    files = {
        'file': ('test_video.mp4', open('test_video.mp4', 'rb'), 'video/mp4')
    }
    
    data = {
        'add_captions': 'true',
        'aspect_ratio': '9:16',
        'platforms': 'TikTok,Instagram'
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    try:
        print("🚀 Testing video upload...")
        response = requests.post(url, files=files, data=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 202
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        files['file'][1].close()

def main():
    print("=== Video Upload Test ===")
    
    # Step 1: Register user
    if not register_user():
        return
    
    # Step 2: Login
    access_token = login_user()
    if not access_token:
        return
    
    # Step 3: Test upload
    success = test_video_upload(access_token)
    if success:
        print("✅ Video upload test completed successfully!")
    else:
        print("❌ Video upload test failed")

if __name__ == "__main__":
    main()