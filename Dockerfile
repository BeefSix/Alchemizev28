# ---- Builder Stage ----
FROM python:3.10-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ build-essential libpq-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ---- Final Stage ----
FROM python:3.10-slim as final

WORKDIR /app

# Install runtime dependencies including a stable version of Chrome and necessary tools
RUN apt-get update && apt-get install -y \
    libpq5 ffmpeg curl wget gnupg unzip ca-certificates apt-transport-https jq \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN adduser --system --group appuser
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache/huggingface
RUN mkdir -p /home/appuser/.config/undetected_chromedriver && chown -R appuser:appuser /home/appuser
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# --- Target Stages ---
FROM final as web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM final as worker
CMD ["celery", "-A", "app.workers.tasks", "worker", "--loglevel=info"]

FROM final as beat
CMD ["celery", "-A", "app.workers.tasks", "beat", "--loglevel=info"]

FROM final as frontend
CMD ["streamlit", "run", "app.py"]