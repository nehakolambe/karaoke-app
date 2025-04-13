FROM python:3.9-slim

# Install system dependencies, including SoX and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sox \
    libsox-dev \
    libsox-fmt-all \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/sync_lyrics

# Copy sync_lyrics and shared code
COPY sync_lyrics /app/sync_lyrics/
COPY shared /app/shared

# Set PYTHONPATH so 'shared' is importable
ENV PYTHONPATH=/app

# Upgrade pip
RUN pip install --upgrade pip

# Install pre-dependencies required for packages in requirements.txt
RUN pip install numpy typing_extensions

# Now install the full requirements
RUN pip install --no-cache-dir -r /app/sync_lyrics/requirements.txt

# Run the worker
CMD ["python", "sync_lyrics.py"]
