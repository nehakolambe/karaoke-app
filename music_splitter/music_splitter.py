import datetime
import json
import os
import shutil
import threading
import traceback

import pika
from spleeter.audio.adapter import AudioAdapter
from spleeter.separator import Separator

from shared import gcs_utils as default_gcs_utils
from shared import constants

RABBITMQ_HOST = constants.RABBITMQ_HOST
LYRICS_QUEUE_NAME = constants.LYRICS_QUEUE_NAME
SPLIT_QUEUE_NAME = constants.SPLIT_QUEUE_NAME
EVENT_TRACKER_QUEUE_NAME = constants.EVENT_TRACKER_QUEUE_NAME

separator = Separator('spleeter:2stems')  # heavy TF model loaded once
audio_loader = AudioAdapter.default()

# Queue functions
def notify_event_tracker(ch, status, job_id="", song_id="", error_message=None):
    event_tracker_message = {
        "job_id": job_id,
        "song_id": str(song_id),
        "source": "splitter",
        "status": status,
        "timestamp": str(datetime.datetime.now(datetime.timezone.utc).isoformat())
    }

    if error_message:
        event_tracker_message["error_message"] = error_message

    ch.basic_publish(
        exchange="",
        routing_key=EVENT_TRACKER_QUEUE_NAME,
        body=json.dumps(event_tracker_message),
        properties=pika.BasicProperties()
    )
    print(f"[EventTracker] Notified event tracker about music splitting status for job: {job_id}")

def publish_to_lyrics_syncer_queue(ch, job_id, song_id, song_name, artist_name):
    splitter_message = {
        "job_id": job_id,
        "song_id": song_id,
        "song_name": song_name,
        "artist_name": artist_name,
    }
    ch.basic_publish(
        exchange='',
        routing_key=LYRICS_QUEUE_NAME,
        body=json.dumps(splitter_message)
    )
    print(f"Published to lyrics syncer queue for job_id: {job_id}, song_id: {song_id}")

# Core functionality
def upload_file_safe(url, local_path, label, errors, gcs_utils):
    try:
        print(f"Uploading {label} to: {url}")
        gcs_utils.upload_file_to_gcs(url, local_path)
    except Exception as e:
        print(f"Failed to upload {label}: {e}")
        errors[label] = str(e)

def split_and_upload_instrumental(job_id: str, song_id: str, audio_loader, separator, gcs_utils):
    print(f"Processing song ID: {song_id}")

    instrumental_url = gcs_utils.get_instrumental_url(song_id)
    vocals_url = gcs_utils.get_vocals_url(song_id)

    if gcs_utils.gcs_file_exists(instrumental_url) and gcs_utils.gcs_file_exists(vocals_url):
        print(f"Instrumental and vocals files already exist, skipping processing for job_id: {job_id}, song_id: {song_id}")
        return

    working_dir = os.path.join("downloads", song_id)
    os.makedirs(working_dir, exist_ok=True)

    original_path = os.path.join(working_dir, "original.wav")
    instrumental_wav_path = os.path.join(working_dir, "instrumental.wav")
    vocal_wav_path = os.path.join(working_dir, "vocal.wav")

    try:
        # Download original.wav
        original_url = gcs_utils.get_artifact_url(song_id, "original.wav")
        print(f"Downloading original.wav from: {original_url}")
        gcs_utils.download_file_from_gcs(original_url, original_path)

        # Separate stems
        print("Running Spleeter...")
        waveform, sample_rate = audio_loader.load(original_path)
        separated = separator.separate(waveform)

        # Save files
        print("Saving instrumental.wav locally...")
        audio_loader.save(instrumental_wav_path, separated['accompaniment'], sample_rate=sample_rate)
        print("Saving vocals.wav locally...")
        audio_loader.save(vocal_wav_path, separated['vocals'], sample_rate=sample_rate)

        # Upload in parallel
        errors = {}
        threads = [
            threading.Thread(
                target=upload_file_safe,
                args=(instrumental_url, instrumental_wav_path, "instrumental", errors, gcs_utils)
            ),
            threading.Thread(
                target=upload_file_safe,
                args=(vocals_url, vocal_wav_path, "vocals", errors, gcs_utils)
            )
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise RuntimeError(f"Failed to upload: {', '.join(errors.keys())} — {errors}")

        print(f"Done processing {song_id}")

    finally:
        shutil.rmtree(working_dir, ignore_errors=True)

# Message handler logic (split out of callback for testability)
def handle_message(message, ch, audio_loader, separator, gcs_utils):
    job_id = message["job_id"]
    song_id = message["song_id"]
    song_name = message["song_name"]
    artist_name = message["artist_name"]
    print(f"Received message for songId: {song_id}")

    try:
        split_and_upload_instrumental(job_id, song_id, audio_loader, separator, gcs_utils)
        # Notify event tracker
        notify_event_tracker(ch, "Completed", job_id, song_id)
        # Publish a job to lyrics syncer
        publish_to_lyrics_syncer_queue(ch, job_id, song_id, song_name, artist_name)
        # Send ack to rabbitmq broker.
        ch.basic_ack(delivery_tag=message['delivery_tag'])
    except Exception as processing_error:
        print(f"Error while processing songId {song_id}: {processing_error}")
        # TODO: Notify event tracker about failure
        traceback.print_exc()
        notify_event_tracker(ch, "Failed", job_id, song_id,
                             f"Internal error while splitting music for job: {job_id}, song ID: {song_id}")
        ch.basic_nack(delivery_tag=message['delivery_tag'], requeue=False)

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        message['delivery_tag'] = method.delivery_tag
        handle_message(message, ch, audio_loader, separator, default_gcs_utils)
    except Exception as e:
        # TODO: Notify event tracker about failure
        print("Unexpected error:", e)
        traceback.print_exc()
        notify_event_tracker(ch, "Failed", error_message=f"Malformed message received: {body}, error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_worker():
    # TODO: Add a health check endpoint implementation.
    print("Starting music splitter worker...")
    credentials = pika.PlainCredentials(constants.RABBITMQ_USER, constants.RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        heartbeat=600,
        blocked_connection_timeout=300,
        connection_attempts=3,
        retry_delay=5,
        socket_timeout=600,
        credentials=credentials
    ))

    channel = connection.channel()

    channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
    channel.queue_declare(queue=LYRICS_QUEUE_NAME)
    channel.queue_declare(queue=SPLIT_QUEUE_NAME)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(SPLIT_QUEUE_NAME, callback)

    print("Worker listening on queue: " + SPLIT_QUEUE_NAME)
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
