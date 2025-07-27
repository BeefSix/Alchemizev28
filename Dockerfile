# ---- Builder Stage ----
# This stage installs dependencies into a temporary location
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
# This stage builds the final, lean image for the application
FROM python:3.10-slim as final

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    ffmpeg \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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
# These are referenced in the docker-compose.yml file

# Target for the FastAPI web server
FROM final as web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Target for the Celery worker
FROM final as worker
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "-P", "eventlet"]

# Target for the Celery beat scheduler
FROM final as beat
CMD ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]

# Target for the Streamlit frontend
FROM final as frontend
# CORRECTED COMMAND: Use the 'streamlit run' command
CMD ["streamlit", "run", "app.py"]
