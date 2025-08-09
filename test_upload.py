import requests
import os

# Test video upload with authentication
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzU0Nzg0OTI3fQ.s8zGmbdV7tykFH1m-hXzrvXXXiTmn7lQ-IApGzBJCVo"

headers = {
    'Authorization': f'Bearer {token}'
}

files = {
    'file': ('test_video.mp4', open('test_video.mp4', 'rb'), 'video/mp4')
}

data = {
    'add_captions': 'true',
    'aspect_ratio': '16:9',
    'platforms': 'youtube,tiktok'
}

try:
    print("Uploading video...")
    response = requests.post(
        'http://localhost:8000/api/v1/video/upload-and-clip',
        headers=headers,
        files=files,
        data=data,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Job ID: {result.get('job_id')}")
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Exception occurred: {e}")
finally:
    files['file'][1].close()