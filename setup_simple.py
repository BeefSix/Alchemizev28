#!/usr/bin/env python3
"""
Simple setup script to get Alchemize running quickly
"""
import os
import secrets

def create_env_file():
    """Create a basic .env file"""
    env_content = f"""# Basic Configuration
ENVIRONMENT=development
DEBUG=true
APP_NAME=Zuexis AI

# Database - Using SQLite for development
DATABASE_URL=sqlite:///./zuexis.db

# Security
SECRET_KEY={secrets.token_urlsafe(32)}

# OpenAI (Required for AI features)
OPENAI_API_KEY=your-openai-api-key-here

# Redis (Optional for development)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Celery (Optional for development)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Upload
MAX_FILE_SIZE_MB=500
UPLOAD_DIR=uploads

# CORS (Development)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Trusted Hosts (Development)
TRUSTED_HOSTS=localhost,127.0.0.1

# Frontend URL
FRONTEND_URL=http://localhost:3000
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file")
    print("⚠️  IMPORTANT: Edit .env and set your OPENAI_API_KEY")

def create_simple_start_script():
    """Create a simple start script"""
    script_content = """@echo off
echo Starting Alchemize...
echo.
echo 1. Make sure you have Python 3.8+ installed
echo 2. Install dependencies: pip install -r requirements.txt
echo 3. Set your OPENAI_API_KEY in .env file
echo 4. Run: python -m uvicorn app.main:app --reload --port 8001
echo.
pause
"""
    
    with open('start_simple.bat', 'w') as f:
        f.write(script_content)
    
    print("✅ Created start_simple.bat")

def main():
    print("🚀 Setting up Alchemize for quick start...")
    print()
    
    # Create .env file
    if not os.path.exists('.env'):
        create_env_file()
    else:
        print("✅ .env file already exists")
    
    # Create start script
    create_simple_start_script()
    
    print()
    print("🎯 Next steps:")
    print("1. Edit .env file and set your OPENAI_API_KEY")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run: python -m uvicorn app.main:app --reload --port 8001")
    print("4. Open http://localhost:8001 in your browser")
    print()
    print("🌐 For the frontend:")
    print("1. cd web")
    print("2. npm install")
    print("3. npm run dev")
    print("4. Open http://localhost:3000 in your browser")

if __name__ == "__main__":
    main()
