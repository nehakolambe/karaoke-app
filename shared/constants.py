import os

# RabbitMQ related constants
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')

GCS_BUCKET_NAME = 'bda-media-bucket'
SPLIT_QUEUE_NAME = "split-jobs"
LYRICS_QUEUE_NAME = "lyrics-jobs"