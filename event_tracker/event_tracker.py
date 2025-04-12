import json
import pika
from google.cloud import firestore
from datetime import datetime

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
            "download_status": "inProcess",
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
        "downloader": "download_status",
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

# RabbitMQ message callback
def callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode())
        job_id = data.get("job_id")
        song_id = data.get("song_id")
        timestamp = data.get("timestamp")
        source = data.get("source")

        if not all([job_id, song_id, timestamp, source]):
            raise ValueError("Missing required fields in message")

        if source == "frontend":
            update_firestore_new_job(job_id, song_id, timestamp)

        elif source in ["downloader", "splitter", "lyrics_syncer"]:
            status = data.get("status")
            error_message = data.get("error_message", "NULL")

            if status not in ["Completed", "Failed"]:
                raise ValueError(f"Invalid status: {status}. Must be 'Completed' or 'Failed'.")

            update_firestore(job_id, song_id, source, status, timestamp, error_message)

        else:
            raise ValueError(f"Unknown source: {source}")

    except Exception as e:
        print(f"Error processing message: {e}")

# RabbitMQ setup
def start_event_tracker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    queue_name = "job_status_events"
    channel.queue_declare(queue=queue_name, durable=True)

    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

    print("Event Tracker is listening for messages...")
    channel.start_consuming()

if __name__ == "__main__":
    start_event_tracker()
