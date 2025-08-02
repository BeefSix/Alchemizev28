# save this as scripts/upload_video.py in your project

import requests
import sys

BASE_URL = "http://localhost:8000"  # adjust if running on a different host/port

EMAIL = "yourname@example.com"
PASSWORD = "yourpassword"
NAME = "Your Name"

VIDEO_PATH = "C:/Users/merli/OneDrive/Desktop/Alchemize/static/sample.mkv"  # change to the path of your MKV/MP4 file
ADD_CAPTIONS = False
ASPECT_RATIO = "16:9"
PLATFORMS = "tiktok,instagram"

def main():
    # 1. Register user (ignore failure if user already exists)
    reg_resp = requests.post(
    f"{BASE_URL}/api/v1/auth/register",
    json={"email": EMAIL, "password": PASSWORD, "full_name": NAME},
)
    if reg_resp.status_code in (200, 201):
        print("✔️  Registered user")
    elif reg_resp.status_code == 400 and "already exists" in reg_resp.text.lower():
        print("ℹ️  User already exists, continuing")
    else:
        print("❌ Registration failed:", reg_resp.text)
        return

    # 2. Log in to get a token
    login_resp = requests.post(
    f"{BASE_URL}/api/v1/auth/token",
    data={"username": EMAIL, "password": PASSWORD},
)
    if login_resp.status_code != 200:
        print("❌ Login failed:", login_resp.text)
        return
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Upload the video
    with open(VIDEO_PATH, "rb") as f:
        files = {"file": (VIDEO_PATH.split("/")[-1], f, "video/x-matroska")}
        data = {
            "add_captions": str(ADD_CAPTIONS).lower(),
            "aspect_ratio": ASPECT_RATIO,
            "platforms": PLATFORMS,
        }
        upload_resp = requests.post(
            f"{BASE_URL}/api/v1/video/upload-and-clip",
            headers=headers,
            files=files,
            data=data,
        )
    if upload_resp.status_code == 202:
        print("✔️  Upload accepted. Job ID:", upload_resp.json()["job_id"])
    else:
        print("❌ Upload failed:", upload_resp.status_code, upload_resp.text)

if __name__ == "__main__":
    main()
