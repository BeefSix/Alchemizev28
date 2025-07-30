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

# =================== FIX START ===================
# Install system dependencies, but REMOVE the basic ffmpeg from this line
RUN apt-get update && apt-get install -y \
    libpq5 curl wget gnupg unzip ca-certificates apt-transport-https jq \
    fonts-dejavu-core fonts-liberation xvfb \
    # Chrome dependencies
    libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libxss1 libgtkextra-dev libgconf2-dev \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install a full-featured, static build of FFmpeg
RUN wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz && \
    tar -xf ffmpeg-git-amd64-static.tar.xz && \
    mv ffmpeg-git-*/ffmpeg /usr/local/bin/ && \
    mv ffmpeg-git-*/ffprobe /usr/local/bin/ && \
    rm -rf ffmpeg-git-*
# =================== FIX END ===================

# Verify Chrome installation and create symlink
RUN google-chrome --version
RUN ln -sf /usr/bin/google-chrome /usr/bin/google-chrome-stable

# Create user and directories
RUN adduser --system --group appuser
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache/huggingface
RUN mkdir -p /app/.cache/selenium && chown -R appuser:appuser /app/.cache/selenium
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads
RUN mkdir -p /app/static/generated && chown -R appuser:appuser /app/static/generated
RUN mkdir -p /home/appuser/.local/share/undetected_chromedriver && chown -R appuser:appuser /home/appuser/.local/share/undetected_chromedriver
RUN mkdir -p /tmp/chrome-user-data && chown -R appuser:appuser /tmp/chrome-user-data
RUN mkdir -p /tmp/chrome-data && chown -R appuser:appuser /tmp/chrome-data

COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV CHROME_BIN=/usr/bin/google-chrome-stable
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