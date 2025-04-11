import os

# RabbitMQ related constants
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = 5672
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'password')

GCS_BUCKET_NAME = 'bda-media-bucket'
SPLIT_QUEUE_NAME = "split-jobs"
LYRICS_QUEUE_NAME = "lyrics-jobs"