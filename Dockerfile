# Start from the official slim Python image to keep the container smaller.
FROM python:3.13-slim

# APP_VERSION is passed by GitHub Actions as a commit SHA or release tag.
ARG APP_VERSION=local

# Store APP_VERSION as an environment variable read by app/core/config.py.
ENV APP_VERSION=${APP_VERSION}

# Prevent Python from writing .pyc files inside the container.
ENV PYTHONDONTWRITEBYTECODE=1

# Send Python logs directly to stdout/stderr without buffering.
ENV PYTHONUNBUFFERED=1

# Use /app as the working directory inside the image.
WORKDIR /app

# Create the fixed non-root account referenced by Kubernetes securityContext.
RUN groupadd --gid 10001 rentout && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rentout

# Copy dependency list first so Docker can cache pip install when app code changes.
COPY requirements.txt .

# Install Python dependencies without keeping pip's download cache.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application package into the image.
COPY --chown=10001:10001 app ./app

# Copy operational scripts into the image for optional container-side use.
COPY --chown=10001:10001 scripts ./scripts

# Run the web process as the restricted account rather than Linux root.
USER 10001:10001

# Document that the API listens on port 8000.
EXPOSE 8000

# Ask Docker to periodically call /health and mark the container unhealthy on failure.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

# Start Uvicorn and bind to all interfaces so Docker port mapping can reach it.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
