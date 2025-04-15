FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sox \
    libsox-dev \
    libsox-fmt-all \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV NLTK_DATA=/app/nltk_data
ENV TORCH_HOME=/app/torch_cache

WORKDIR /app/sync_lyrics

COPY sync_lyrics/requirements.txt /app/sync_lyrics/

RUN pip install --upgrade pip && \
    pip install numpy typing_extensions && \
    pip install --no-cache-dir -r /app/sync_lyrics/requirements.txt


RUN mkdir -p /app/nltk_data/taggers && \
    curl -L -o /app/nltk_data/taggers/averaged_perceptron_tagger.zip \
        https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/taggers/averaged_perceptron_tagger.zip && \
    curl -L -o /app/nltk_data/taggers/averaged_perceptron_tagger_eng.zip \
        https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/taggers/averaged_perceptron_tagger_eng.zip && \
    unzip /app/nltk_data/taggers/averaged_perceptron_tagger.zip -d /app/nltk_data/taggers/ && \
    unzip /app/nltk_data/taggers/averaged_perceptron_tagger_eng.zip -d /app/nltk_data/taggers/ && \
    rm /app/nltk_data/taggers/*.zip

RUN chmod -R 755 /app/nltk_data

COPY sync_lyrics /app/sync_lyrics/
COPY shared /app/shared/

RUN python -c "\
import nltk; \
nltk.data.path.append('/app/nltk_data'); \
nltk.data.find('taggers/averaged_perceptron_tagger'); \
nltk.data.find('taggers/averaged_perceptron_tagger_eng')"


# Run the worker
CMD ["python", "sync_lyrics.py"]
