import pika
import json
from datetime import datetime

# RabbitMQ setup
connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()

queue_name = "job_status_events"
channel.queue_declare(queue=queue_name, durable=True)

# --- Test Case 1: New job created from frontend ---
frontend_message = {
    "source": "frontend",
    "job_id": "ijk123-job",
    "song_id": "song456",
    "created_timestamp": datetime.utcnow().isoformat() + "Z"
}

# --- Test Case 2: Downloader service completed ---
download_message = {
    "source": "downloader",
    "job_id": "abc123-job",
    "song_id": "song456",
    "status": "Completed",
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

# --- Test Case 3: Vocals splitter failed ---
vocals_message = {
    "source": "splitter",
    "job_id": "abc123-job",
    "song_id": "song456",
    "status": "Failed",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "error_message": "Could not separate vocals"
}

# --- Test Case 4: Lyrics syncer completed ---
lyrics_message = {
    "source": "lyrics_syncer",
    "job_id": "wer123-job",
    "song_id": "song456",
    "status": "Completed",
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

# Send messages
for message in [frontend_message, download_message, vocals_message, lyrics_message]:
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  # make message persistent
    )
    print(f"[x] Sent: {message['source']} update")

connection.close()
