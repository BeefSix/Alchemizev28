"""Test configuration and fixtures."""

import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db, Base
from app.core.config import settings
from app.models.user import User
from app.models.file_upload import FileUpload
from app.core.security import get_password_hash

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after each test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict:
    """Get authentication headers for test user."""
    login_data = {
        "username": test_user.email,
        "password": "testpassword123"
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client: TestClient, admin_user: User) -> dict:
    """Get authentication headers for admin user."""
    login_data = {
        "username": admin_user.email,
        "password": "adminpassword123"
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_file_upload(db_session: Session, test_user: User) -> FileUpload:
    """Create a sample file upload record."""
    file_upload = FileUpload(
        user_id=test_user.id,
        filename="test_video.mp4",
        file_path="/uploads/test_video.mp4",
        file_size=1024000,  # 1MB
        content_type="video/mp4",
        upload_status="completed"
    )
    db_session.add(file_upload)
    db_session.commit()
    db_session.refresh(file_upload)
    return file_upload


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "choices": [{
            "message": {
                "content": "This is a test AI response for content generation."
            }
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    }


@pytest.fixture
def mock_video_file():
    """Create a mock video file for testing."""
    import io
    
    # Create a minimal MP4-like file content
    content = b"\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom\x00\x00\x00\x08free"
    return io.BytesIO(content)


@pytest.fixture
def mock_audio_file():
    """Create a mock audio file for testing."""
    import io
    
    # Create a minimal MP3-like file content
    content = b"\xff\xfb\x90\x00" + b"\x00" * 100  # MP3 header + some data
    return io.BytesIO(content)


# Test settings override
@pytest.fixture(autouse=True)
def override_settings():
    """Override settings for testing."""
    original_values = {}
    
    # Override specific settings for testing
    test_overrides = {
        'ENVIRONMENT': 'testing',
        'DEBUG': True,
        'RATE_LIMIT_ENABLED': False,
        'OPENAI_API_KEY': 'sk-test-fake-key',
        'MAX_FILE_SIZE_MB': 10,
        'MAX_VIDEO_DURATION_MINUTES': 5,
    }
    
    # Store original values and apply overrides
    for key, value in test_overrides.items():
        if hasattr(settings, key):
            original_values[key] = getattr(settings, key)
            setattr(settings, key, value)
    
    yield
    
    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)