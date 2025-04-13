# karaoke-app/music_downloader/Dockerfile

FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/music_downloader

# Copy downloader and shared code
COPY music_downloader /app/music_downloader
COPY shared /app/shared

# Set PYTHONPATH so 'shared' is importable
ENV PYTHONPATH=/app

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/music_downloader/requirements.txt

# Run the worker
CMD ["python", "music_downloader.py"]
