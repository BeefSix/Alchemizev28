# ---- Builder Stage ----
FROM python:3.10-slim as builder

WORKDIR /app

# Install build-time dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ---- Final Stage ----
FROM python:3.10-slim as final

WORKDIR /app

# Install runtime dependencies including Chrome for Selenium
RUN apt-get update && apt-get install -y \
    libpq5 \
    ffmpeg \
    curl \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Download and install the correct ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1-3) && \
    DRIVER_VERSION=$(curl -sS "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build.json" | grep -A1 "\"${CHROME_VERSION}\"" | grep '"version":' | head -n1 | cut -d '"' -f 4) && \
    wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64 && \
    chmod +x /usr/local/bin/chromedriver

# Create a non-root user to run the application
RUN adduser --system --group appuser

# Create cache directories and set permissions
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache/huggingface
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

# Copy pre-built wheels from the builder stage
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy the application code
COPY . .

# Set permissions for the entire app directory
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# --- Target Stages for Different Services ---
FROM final as web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM final as worker
CMD ["celery", "-A", "app.workers.tasks", "worker", "--loglevel=info"]

FROM final as beat
CMD ["celery", "-A", "app.workers.tasks", "beat", "--loglevel=info"]

FROM final as frontend
CMD ["streamlit", "run", "app.py"]