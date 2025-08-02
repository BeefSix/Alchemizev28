# ---- Builder Stage ----
FROM python:3.10-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ build-essential libpq-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ---- Final Stage ----
FROM python:3.10-slim AS final

WORKDIR /app

# Install system dependencies including xz-utils for FFmpeg extraction
RUN apt-get update && apt-get install -y \
    libpq5 curl wget gnupg unzip ca-certificates xz-utils \
    fonts-dejavu-core fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install FFmpeg (fixed - added xz-utils above)
RUN wget -q https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
    && tar -xf ffmpeg-git-amd64-static.tar.xz \
    && mv ffmpeg-git-*/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-git-*/ffprobe /usr/local/bin/ \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-git-* ffmpeg-git-amd64-static.tar.xz

# Verify FFmpeg installation
RUN ffmpeg -version

# Create user and directories
RUN adduser --system --group appuser \
    && mkdir -p /app/.cache/huggingface /app/static/generated/uploads /app/static/generated/temp_downloads \
    && chown -R appuser:appuser /app

# Install Python packages
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface

# --- Target Stages ---
FROM final AS web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM final AS worker
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]

FROM final AS beat
CMD ["celery", "-A", "app.celery_app", "beat", "--loglevel=info"]

FROM final AS frontend
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]