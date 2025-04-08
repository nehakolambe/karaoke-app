FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    sox \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/music_splitter

# Copy music_splitter and shared code
COPY music_splitter /app/music_splitter
COPY shared /app/shared

# Set PYTHONPATH so 'shared' is importable
ENV PYTHONPATH=/app

RUN pip install --no-cache-dir -r /app/music_splitter/requirements.txt

# Download and extract Spleeter 2stems model during build
RUN mkdir -p /app/pretrained_models && \
    curl -L -o /tmp/2stems.tar.gz https://github.com/deezer/spleeter/releases/download/v1.4.0/2stems.tar.gz && \
    tar -xzf /tmp/2stems.tar.gz -C /app/pretrained_models && \
    rm /tmp/2stems.tar.gz

# Set environment variable for Spleeter to find the model
ENV SPLEETER_PRETRAINED_MODEL_PATH=/app/pretrained_models

# Run the worker
CMD ["python", "music_splitter.py"]
