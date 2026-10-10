# ========================================================
# Drishti LiveKit Voice Agent Worker Dockerfile
# Production 24/7 Agent Worker for Multi-Modal Assistance
# ========================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for WebRTC audio processing, Pillow, and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for caching layers
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source application
COPY . .

# Run agent worker in production 'start' mode
CMD ["python", "drishti_agent.py", "start"]
