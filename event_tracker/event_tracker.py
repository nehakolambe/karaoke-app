import json
import pika
from google.cloud import firestore
from datetime import datetime

from shared import constants

# Firestore client setup
db = firestore.Client()
collection_name = "job_history"  # Save everything in job_history collection

# Create new job with default values
def update_firestore_new_job(job_id, song_id, timestamp):
    doc_ref = db.collection(collection_name).document(job_id)
    doc = doc_ref.get()

    if not doc.exists:
        default_data = {
            "job_id": job_id,
            "song_id": song_id,
            "vocals_status": "inProcess",
            "lyrics_status": "inProcess",
            "last_updated_timestamp": timestamp,
            "error_message": "NULL"
        }
        doc_ref.set(default_data)
        print(f"New job initialized in Firestore for job_id: {job_id}")
    else:
        print(f"Job with job_id: {job_id} already exists.")

# Update job status from service
def update_firestore(job_id, song_id, source, status, timestamp, error_message):
    doc_ref = db.collection(collection_name).document(job_id)
    doc = doc_ref.get()

    if not doc.exists:
        print(f"Job {job_id} not found. Creating with default values.")
        update_firestore_new_job(job_id, song_id, timestamp)

    # Map service name to field
    field_map = {
        "splitter": "vocals_status",
        "lyrics_syncer": "lyrics_status"
    }

    if source not in field_map:
        raise ValueError(f"Unknown service source: {source}")

    status_field = field_map[source]

    update_data = {
        status_field: status,
        "last_updated_timestamp": timestamp,
        "error_message": error_message or "NULL"
    }

    doc_ref.update(update_data)
    print(f"Updated {status_field} to {status} for job_id: {job_id}")

# Handle "frontend" source: create new job
def handle_frontend_update(data):
    job_id = data.get("job_id")
    song_id = data.get("song_id")
    timestamp = data.get("timestamp")
    if not all([job_id, song_id, timestamp]):
        raise ValueError("Missing required fields for 'frontend'")
    update_firestore_new_job(job_id, song_id, timestamp)

# Handle "splitter", "lyrics_syncer": job status updates
def handle_job_update(data):
    job_id = data.get("job_id")
    song_id = data.get("song_id")
    timestamp = data.get("timestamp")
    status = data.get("status")
    error_message = data.get("error_message", "NULL")

    if not all([job_id, song_id, timestamp, status]):
        raise ValueError("Missing required fields for processing update")

    if status not in ["Completed", "Failed"]:
        raise ValueError(f"Invalid status: {status}. Must be 'Completed' or 'Failed'.")

    source = data.get("source")
    update_firestore(job_id, song_id, source, status, timestamp, error_message)

# Handle "history" source: track song in user history
def handle_user_history_update(data):
    song_id = data.get("song_id")
    timestamp = data.get("timestamp")
    user_email = data.get("user_email")
    if not all([song_id, timestamp, user_email]):
        raise ValueError("Missing required fields for 'history'")

    user_ref = db.collection("users").document(user_email)
    user_doc = user_ref.get()
    if user_doc.exists:
        user_ref.update({
            "downloaded_songs": firestore.ArrayUnion([song_id])
        })
    else:
        user_ref.set({
            "downloaded_songs": [song_id]
        })
    print(f"Added song {song_id} to user {user_email}'s history.")


# RabbitMQ message callback
def callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode())
        source = data.get("source")
        if not source:
            raise ValueError("Missing 'source' in message")

        if source == "frontend":
            handle_frontend_update(data)
        elif source in ["splitter", "lyrics_syncer"]:
            handle_job_update(data)
        elif source == "history":
            handle_user_history_update(data)
        else:
            raise ValueError(f"Unknown source: {source}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# RabbitMQ setup
def start_event_tracker():
    credentials = pika.PlainCredentials(constants.RABBITMQ_USER, constants.RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=constants.RABBITMQ_HOST,
        heartbeat=600,
        blocked_connection_timeout=300,
        connection_attempts=3,
        retry_delay=5,
        socket_timeout=600,
        credentials=credentials
    ))

    channel = connection.channel()

    queue_name = constants.EVENT_TRACKER_QUEUE_NAME
    channel.queue_declare(queue=queue_name)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    print("Event Tracker is listening for messages...")
    channel.start_consuming()

if __name__ == "__main__":
    start_event_tracker()
