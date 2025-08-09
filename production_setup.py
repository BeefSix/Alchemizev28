#!/usr/bin/env python3
"""
Production setup script for Alchemize
This script prepares the application for production deployment
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

def create_production_env():
    """Create production environment file"""
    env_content = f"""# Production Environment Configuration
# Database
DATABASE_URL=postgresql://alchemize_user:alchemize_password@localhost:5432/alchemize_db

# Security
SECRET_KEY={secrets.token_urlsafe(32)}
JWT_SECRET_KEY={secrets.token_urlsafe(32)}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["https://yourdomain.com", "https://www.yourdomain.com"]
TRUSTED_HOSTS=["yourdomain.com", "www.yourdomain.com"]

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Stripe
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=100MB
ALLOWED_VIDEO_TYPES=mp4,avi,mov,wmv,flv,webm,mkv

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true

# Production Settings
DEBUG=false
ENVIRONMENT=production
ENABLE_CORS=true
ENABLE_RATE_LIMITING=true
ENABLE_SECURITY_HEADERS=true
"""
    
    with open('.env.production', 'w') as f:
        f.write(env_content)
    print("✅ Created .env.production file")

def create_docker_compose_production():
    """Create production Docker Compose file"""
    docker_content = """version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: alchemize_postgres
    environment:
      POSTGRES_DB: alchemize_db
      POSTGRES_USER: alchemize_user
      POSTGRES_PASSWORD: alchemize_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U alchemize_user -d alchemize_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis for Celery
  redis:
    image: redis:7-alpine
    container_name: alchemize_redis
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # FastAPI Backend
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: alchemize_backend
    environment:
      - DATABASE_URL=postgresql://alchemize_user:alchemize_password@postgres:5432/alchemize_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs

  # Celery Worker
  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: alchemize_celery
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://alchemize_user:alchemize_password@postgres:5432/alchemize_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs

  # Next.js Frontend
  frontend:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: alchemize_frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8001
    depends_on:
      - backend
    restart: unless-stopped

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: alchemize_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
"""
    
    with open('docker-compose.production.yml', 'w') as f:
        f.write(docker_content)
    print("✅ Created docker-compose.production.yml")

def create_production_start_script():
    """Create production start script"""
    script_content = """@echo off
echo 🚀 Starting Alchemize Production Environment...

echo 📦 Building and starting services...
docker-compose -f docker-compose.production.yml up -d --build

echo ⏳ Waiting for services to be ready...
timeout /t 30 /nobreak > nul

echo 🔍 Checking service health...
docker-compose -f docker-compose.production.yml ps

echo 🌐 Services should be available at:
echo    - Frontend: http://localhost:3000
echo    - Backend API: http://localhost:8001
echo    - API Docs: http://localhost:8001/docs
echo    - Nginx: http://localhost:80

echo ✅ Production environment started!
pause
"""
    
    with open('start_production.bat', 'w') as f:
        script_content
    print("✅ Created start_production.bat")

def create_database_init():
    """Create database initialization script"""
    init_sql = """-- Database initialization for Alchemize
CREATE DATABASE IF NOT EXISTS alchemize_db;
\\c alchemize_db;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The tables will be created by SQLAlchemy/Alembic
"""
    
    with open('init.sql', 'w') as f:
        init_sql
    print("✅ Created init.sql")

def create_frontend_dockerfile():
    """Create Dockerfile for Next.js frontend"""
    dockerfile_content = """FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
"""
    
    frontend_dockerfile = Path('web/Dockerfile')
    frontend_dockerfile.parent.mkdir(exist_ok=True)
    with open(frontend_dockerfile, 'w') as f:
        f.write(dockerfile_content)
    print("✅ Created web/Dockerfile")

def create_production_nginx():
    """Create production Nginx configuration"""
    nginx_content = """events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8001;
    }

    upstream frontend {
        server frontend:3000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=upload:10m rate=2r/s;

    server {
        listen 80;
        server_name localhost;

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Backend API
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # File uploads
        location /upload/ {
            limit_req zone=upload burst=5 nodelay;
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            client_max_body_size 100M;
        }

        # Health checks
        location /health {
            proxy_pass http://backend;
            proxy_set_header Host $host;
        }
    }
}
"""
    
    with open('nginx.production.conf', 'w') as f:
        nginx_content
    print("✅ Created nginx.production.conf")

def create_production_guide():
    """Create production deployment guide"""
    guide_content = """# Alchemize Production Deployment Guide

## 🚀 Quick Start

1. **Environment Setup**
   ```bash
   python production_setup.py
   ```

2. **Start Production Environment**
   ```bash
   start_production.bat
   ```

## 📋 Prerequisites

- Docker and Docker Compose installed
- PostgreSQL 15+ (or use the included container)
- Redis 7+ (or use the included container)
- Valid OpenAI API key
- Stripe account (for payments)

## 🔧 Configuration

### Environment Variables
Edit `.env.production` and update:
- `OPENAI_API_KEY`: Your OpenAI API key
- `STRIPE_SECRET_KEY`: Your Stripe secret key
- `CORS_ORIGINS`: Your domain(s)
- `TRUSTED_HOSTS`: Your domain(s)

### Database
The setup includes PostgreSQL with:
- Database: `alchemize_db`
- User: `alchemize_user`
- Password: `alchemize_password`

### SSL/HTTPS
For production, add SSL certificates to `./ssl/` directory and update nginx configuration.

## 🐳 Docker Services

- **PostgreSQL**: Database (port 5432)
- **Redis**: Message broker and cache (port 6379)
- **Backend**: FastAPI application (port 8001)
- **Celery Worker**: Background task processing
- **Frontend**: Next.js application (port 3000)
- **Nginx**: Reverse proxy and load balancer (port 80/443)

## 📊 Monitoring

- Health checks: `http://localhost:8001/health/detailed`
- API documentation: `http://localhost:8001/docs`
- Frontend: `http://localhost:3000`

## 🔒 Security Features

- Rate limiting on API endpoints
- CORS protection
- Security headers
- File upload validation
- JWT authentication
- Database connection pooling

## 📈 Scaling

- Add more Celery workers: `docker-compose -f docker-compose.production.yml up -d --scale celery_worker=3`
- Use external Redis cluster
- Implement database read replicas
- Add CDN for static files

## 🚨 Troubleshooting

### Check service status
```bash
docker-compose -f docker-compose.production.yml ps
```

### View logs
```bash
docker-compose -f docker-compose.production.yml logs -f [service_name]
```

### Restart services
```bash
docker-compose -f docker-compose.production.yml restart [service_name]
```

## 🔄 Updates

1. Pull latest code
2. Rebuild and restart:
   ```bash
   docker-compose -f docker-compose.production.yml down
   docker-compose -f docker-compose.production.yml up -d --build
   ```

## 📞 Support

For issues, check:
- Application logs in `./logs/`
- Docker container logs
- Health check endpoints
- Database connectivity
"""
    
    with open('PRODUCTION_DEPLOYMENT.md', 'w') as f:
        f.write(guide_content)
    print("✅ Created PRODUCTION_DEPLOYMENT.md")

def main():
    """Main setup function"""
    print("🚀 Setting up Alchemize for Production...")
    
    try:
        create_production_env()
        create_docker_compose_production()
        create_production_start_script()
        create_database_init()
        create_frontend_dockerfile()
        create_production_nginx()
        create_production_guide()
        
        print("\n🎉 Production setup complete!")
        print("\n📋 Next steps:")
        print("1. Edit .env.production with your API keys and domain")
        print("2. Run: start_production.bat")
        print("3. Check PRODUCTION_DEPLOYMENT.md for detailed instructions")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
