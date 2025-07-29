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

# Install runtime dependencies including fonts and Chrome
RUN apt-get update && apt-get install -y \
    libpq5 ffmpeg curl wget gnupg unzip ca-certificates apt-transport-https jq fonts-dejavu-core \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Verify Chrome installation
RUN google-chrome --version

RUN adduser --system --group appuser
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache/huggingface
RUN mkdir -p /app/.cache/selenium && chown -R appuser:appuser /app/.cache/selenium
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads
RUN mkdir -p /app/static/generated && chown -R appuser:appuser /app/static/generated
RUN mkdir -p /home/appuser/.local/share/undetected_chromedriver && chown -R appuser:appuser /home/appuser/.local/share/undetected_chromedriver

COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Set environment variables for HuggingFace cache
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface

# --- Target Stages ---
FROM final AS web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM final AS worker
CMD ["celery", "-A", "app.workers.tasks", "worker", "--loglevel=info"]

FROM final AS beat
CMD ["celery", "-A", "app.workers.tasks", "beat", "--loglevel=info"]

FROM final AS frontend
# Set Streamlit config to avoid the welcome screen
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]