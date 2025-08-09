#!/usr/bin/env python3
"""
Test frontend authentication flow
"""

import requests
import json

def test_complete_auth_flow():
    """Test the complete authentication flow"""
    base_url = "http://localhost:8000/api/v1"
    
    print("🔐 Testing Complete Authentication Flow\n")
    
    # Step 1: Try to register a test user (this might fail if user exists)
    print("1️⃣ Testing user registration...")
    try:
        register_data = {
            "email": "testuser@example.com",
            "password": "ValidPassword2024!",
            "full_name": "Test User"
        }
        
        response = requests.post(
            f"{base_url}/auth/register",
            json=register_data,
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ User registration successful")
        elif response.status_code == 400 and "already registered" in response.text:
            print("ℹ️  User already exists (this is fine for testing)")
        else:
            print(f"⚠️  Registration response: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"❌ Registration test failed: {e}")
    
    # Step 2: Test login with correct credentials
    print("\n2️⃣ Testing login with test credentials...")
    try:
        login_data = {
            "username": "testuser@example.com",
            "password": "ValidPassword2024!"
        }
        
        response = requests.post(
            f"{base_url}/auth/token",
            data=login_data,
            timeout=5
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            print("✅ Login successful!")
            print(f"   Token type: {token_data.get('token_type')}")
            print(f"   User email: {token_data.get('user_email')}")
            print(f"   Token preview: {access_token[:20]}...")
            
            # Step 3: Test authenticated upload
            print("\n3️⃣ Testing authenticated upload...")
            test_authenticated_upload(access_token)
            
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")

def test_authenticated_upload(token):
    """Test upload with authentication token"""
    try:
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        # Use the real video file we created with FFmpeg
        with open('test_video_real.mp4', 'rb') as f:
            test_content = f.read()
        
        print(f"   Test file size: {len(test_content)} bytes")
        files = {'file': ('test_video_real.mp4', test_content, 'video/mp4')}
        data = {
            'add_captions': 'true',
            'aspect_ratio': '16:9',
            'platforms': 'youtube'
        }
        
        response = requests.post(
            "http://localhost:8000/api/v1/video/upload-and-clip",
            files=files,
            data=data,
            headers=headers,
            timeout=10
        )
        
        print(f"   Upload status: {response.status_code}")
        
        if response.status_code == 202:
            result = response.json()
            print("✅ Upload accepted for processing!")
            print(f"   Job ID: {result.get('job_id')}")
        elif response.status_code == 422:
            print("⚠️  Validation error (expected with fake file):")
            try:
                error_data = response.json()
                print(f"   Details: {error_data.get('detail', 'Unknown validation error')}")
            except:
                print(f"   Raw response: {response.text[:200]}")
        else:
            print(f"❌ Unexpected upload response: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Authenticated upload test failed: {e}")

def main():
    print("🧪 Frontend Authentication Flow Test\n")
    test_complete_auth_flow()
    
    print("\n" + "="*50)
    print("📋 DIAGNOSIS SUMMARY")
    print("="*50)
    print("\nIf the tests above show:")
    print("✅ Registration/Login working → The issue is frontend session state")
    print("✅ Authenticated upload working → Backend is functioning correctly")
    print("\n🔧 SOLUTION:")
    print("The 'Failed to connect to API server' error occurs when:")
    print("1. User is not logged in (no token in session)")
    print("2. Session state is corrupted")
    print("3. Frontend API client can't reach backend")
    print("\n💡 USER ACTIONS:")
    print("1. Make sure you're logged in to the application")
    print("2. If logged in, try logging out and back in")
    print("3. Check browser console for any JavaScript errors")
    print("4. Refresh the page to reset session state")

if __name__ == "__main__":
    main()