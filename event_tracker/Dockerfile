FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    sox \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/event_tracker

# Copy event_tracker and shared code (adjusted for root context)
COPY event_tracker /app/event_tracker
COPY shared /app/shared

# Set PYTHONPATH so 'shared' is importable
ENV PYTHONPATH=/app

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/event_tracker/requirements.txt

# Run the worker
CMD ["python", "event_tracker.py"]
