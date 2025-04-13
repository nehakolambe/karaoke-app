import json
import pika
import shared.constants as constants

# Use same constants as your worker
RABBITMQ_HOST = "localhost"  # or cluster IP
SPLIT_QUEUE_NAME = constants.SPLIT_QUEUE_NAME

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()

channel.queue_declare(queue=SPLIT_QUEUE_NAME)

mock_job = {
    "job_id": "test-job-001",
    "song_id": "138406",
    "song_name": "Imagine",
    "artist_name": "John Lennon"
}

channel.basic_publish(
    exchange='',
    routing_key=SPLIT_QUEUE_NAME,
    body=json.dumps(mock_job)
)

print("Test job sent.")
channel.close()
