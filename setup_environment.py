#!/usr/bin/env python3
"""
Environment Setup Script for Video Function
Creates .env file with required configuration
"""

import os
import secrets
import string

def generate_secret_key(length=32):
    """Generate a secure secret key"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_env_file():
    """Create .env file with required environment variables"""
    
    env_content = f"""# Database Configuration
DATABASE_URL=sqlite:///./alchemize.db

# Security
SECRET_KEY={generate_secret_key()}

# OpenAI API - SET YOUR ACTUAL API KEY HERE
OPENAI_API_KEY=your-openai-api-key-here

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Video Processing
VIDEO_PROCESSING_MAX_FILE_SIZE_MB=500
VIDEO_PROCESSING_MAX_CLIP_DURATION=60
VIDEO_PROCESSING_ENABLE_GPU=true

# Storage Configuration
STORAGE_BACKEND=local
UPLOAD_DIR=uploads
STATIC_GENERATED_DIR=static/generated

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:8501,http://localhost:3000

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file with required environment variables")
    print("⚠️  IMPORTANT: Set your actual OPENAI_API_KEY in the .env file")

def main():
    print("Setting up environment for video function...")
    
    if os.path.exists('.env'):
        print("⚠️  .env file already exists. Backing up to .env.backup")
        os.rename('.env', '.env.backup')
    
    create_env_file()
    
    print("\n🔧 Next steps:")
    print("1. Edit .env file and set your OPENAI_API_KEY")
    print("2. Run: python fix_video_issues.py")
    print("3. Start your services:")
    print("   - Backend: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("   - Frontend: streamlit run app.py")
    print("   - Redis: redis-server")
    print("   - Worker: celery -A app.celery_app worker --loglevel=info")

if __name__ == "__main__":
    main()
