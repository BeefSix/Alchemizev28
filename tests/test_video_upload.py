# tests/test_video_upload.py
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Make sure the project root is on sys.path so we can import 'app'
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.main import app
from app.services.auth import get_current_active_user

class DummyUser:
    def __init__(self, id=1):
        self.id = id

app.dependency_overrides[get_current_active_user] = lambda: DummyUser()

def test_upload_and_clip_route():
    client = TestClient(app)
    sample_video_path = "static/sample.mkv"  # path to your MKV file
    with open(sample_video_path, "rb") as f:
        response = client.post(
            "/api/v1/video/upload-and-clip",
            files={"file": ("sample.mkv", f, "video/x-matroska")},
            data={
                "add_captions": "false",
                "aspect_ratio": "16:9",
                "platforms": "tiktok",
            },
        )
    assert response.status_code == 202, response.text
    json_response = response.json()
    assert "job_id" in json_response
    assert json_response["message"] == "Video processing has started"
