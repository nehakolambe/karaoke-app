FROM python:3.9-slim

# Install system dependencies including SoX
RUN apt-get update && apt-get install -y --no-install-recommends \
    sox \
    libsox-dev \
    libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/frontend

# Copy app code
COPY frontend /app/frontend
COPY shared /app/shared

ENV PYTHONPATH=/app

# Install base pip packages needed for setup-time dependencies
RUN pip install --upgrade pip
RUN pip install numpy typing_extensions

# Install all other dependencies
RUN pip install --no-cache-dir -r /app/frontend/requirements.txt

# Run your app
CMD ["python", "app_main.py"]
