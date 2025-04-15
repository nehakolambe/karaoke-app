FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    sox \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/music_splitter

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV SPLEETER_PRETRAINED_MODEL_PATH=/app/pretrained_models

COPY music_splitter/requirements.txt /app/music_splitter/

RUN pip install --no-cache-dir -r /app/music_splitter/requirements.txt

RUN mkdir -p /app/pretrained_models && \
    curl -L -o /tmp/2stems.tar.gz https://github.com/deezer/spleeter/releases/download/v1.4.0/2stems.tar.gz && \
    tar -xzf /tmp/2stems.tar.gz -C /app/pretrained_models && \
    rm /tmp/2stems.tar.gz

COPY music_splitter /app/music_splitter
COPY shared /app/shared

CMD ["python", "music_splitter.py"]
