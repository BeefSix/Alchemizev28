#!/usr/bin/env python3
"""
Test script to diagnose upload connection issues
"""

import requests
import json
from pathlib import Path

def test_upload_connection():
    """Test the upload connection and authentication flow"""
    base_url = "http://localhost:8000/api/v1"
    
    print("🔍 Testing Upload Connection...")
    print("=" * 50)
    
    # 1. Test API Health
    try:
        health_response = requests.get(f"http://localhost:8000/health", timeout=5)
        print(f"✅ API Health: {health_response.status_code} - {health_response.text}")
    except Exception as e:
        print(f"❌ API Health Failed: {e}")
        return
    
    # 2. Test Upload Endpoint (should require auth)
    try:
        upload_response = requests.post(f"{base_url}/video/upload-and-clip", timeout=5)
        print(f"🔒 Upload Endpoint (no auth): {upload_response.status_code}")
        if upload_response.status_code == 401:
            print("   ✅ Correctly requires authentication")
    except Exception as e:
        print(f"❌ Upload Endpoint Test Failed: {e}")
    
    # 3. Test Authentication
    try:
        # Register a test user
        register_data = {
            "email": "test@example.com",
            "password": "TestPassword123!",
            "full_name": "Test User"
        }
        
        register_response = requests.post(
            f"{base_url}/auth/register",
            json=register_data,
            timeout=5
        )
        print(f"📝 Registration: {register_response.status_code}")
        
        # Login to get token
        login_data = {
            "username": "test@example.com",
            "password": "TestPassword123!"
        }
        
        login_response = requests.post(
            f"{base_url}/auth/token",
            data=login_data,  # Use form data for OAuth2
            timeout=5
        )
        print(f"🔑 Login: {login_response.status_code}")
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            access_token = token_data.get('access_token')
            print(f"   ✅ Token obtained: {access_token[:20]}...")
            
            # 4. Test authenticated upload endpoint
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Create a small test file
            test_content = b"test video content"
            files = {'file': ('test.mp4', test_content, 'video/mp4')}
            data = {
                'add_captions': 'true',
                'aspect_ratio': '16:9',
                'platforms': 'youtube'
            }
            
            auth_upload_response = requests.post(
                f"{base_url}/video/upload-and-clip",
                files=files,
                data=data,
                headers=headers,
                timeout=10
            )
            print(f"📤 Authenticated Upload: {auth_upload_response.status_code}")
            
            if auth_upload_response.status_code != 200:
                try:
                    error_detail = auth_upload_response.json()
                    print(f"   Error details: {error_detail}")
                except:
                    print(f"   Error text: {auth_upload_response.text}")
            else:
                print("   ✅ Upload successful!")
                
        else:
            try:
                error_detail = login_response.json()
                print(f"   Login error: {error_detail}")
            except:
                print(f"   Login error text: {login_response.text}")
                
    except Exception as e:
        print(f"❌ Authentication Test Failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Diagnosis Summary:")
    print("- If API health is OK but upload fails with 'Failed to connect to API server'")
    print("- This usually means the frontend can't reach the backend")
    print("- Or the user is not properly authenticated")
    print("- Check browser console for network errors")
    print("- Ensure user is logged in before attempting upload")

if __name__ == "__main__":
    test_upload_connection()