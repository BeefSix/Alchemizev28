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

# Install all dependencies including FFmpeg from official repos
RUN apt-get update && apt-get install -y \
    libpq5 curl wget gnupg unzip ca-certificates apt-transport-https jq \
    fonts-dejavu-core fonts-liberation xvfb \
    # FFmpeg with all codecs
    ffmpeg \
    # Chrome dependencies
    libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libxss1 libgtkextra-dev libgconf2-dev \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Verify installations
RUN ffmpeg -version && ffprobe -version
RUN google-chrome --version

# Create user and directories
RUN adduser --system --group appuser
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache/huggingface
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads
RUN mkdir -p /app/static/generated/uploads && chown -R appuser:appuser /app/static
RUN mkdir -p /app/static/generated/temp_downloads && chown -R appuser:appuser /app/static

COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV DISPLAY=:99

# --- Target Stages ---
FROM final AS web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM final AS worker
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x24 & celery -A app.celery_app.celery_app worker --loglevel=info"]

FROM final AS beat
CMD ["celery", "-A", "app.celery_app.celery_app", "beat", "--loglevel=info"]

FROM final AS frontend
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]