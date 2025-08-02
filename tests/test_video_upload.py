# tests/test_video_upload.py
from fastapi.testclient import TestClient
from app.main import app

def test_upload_and_clip_route():
    client = TestClient(app)

    # Replace this with the path to a small sample video on your machine
    sample_video_path = "static/sample.mp4"

    # Open the file in binary mode
    with open(sample_video_path, "rb") as f:
        response = client.post(
            "/api/v1/upload-and-clip",
            files={"file": ("sample.mp4", f, "video/mp4")},
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
