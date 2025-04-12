import datetime
import json
import os
import traceback
import yt_dlp
import pika

from frontend.app_main import EVENT_TRACKER_QUEUE_NAME
from shared.gcs_utils import upload_file_to_gcs, gcs_file_exists, get_instrumental_url, get_vocals_url  # Fixed import
from shared import constants

# Constants
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
RABBITMQ_HOST = constants.RABBITMQ_HOST
DOWNLOAD_QUEUE_NAME = constants.DOWNLOAD_QUEUE_NAME
MUSIC_SPLITTER_QUEUE_NAME = constants.SPLIT_QUEUE_NAME
BUCKET_NAME = constants.GCS_BUCKET_NAME

# Queue functions
def notify_event_tracker(ch, status, job_id="", song_id="", error_message=None):
    event_tracker_message = {
        "job_id": job_id,
        "song_id": str(song_id),
        "source" : "downloader",
        "status" : status,
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
    print(f"[EventTracker] Notified event tracker about music download status for job: {job_id}")

def publish_to_music_splitter_queue(ch, job_id, song_id, song_name, artist_name):
    splitter_message = {
        "job_id": job_id,
        "song_id": song_id,
        "song_name": song_name,
        "artist_name": artist_name,
    }
    ch.basic_publish(
        exchange='',
        routing_key=MUSIC_SPLITTER_QUEUE_NAME,
        body=json.dumps(splitter_message)
    )
    print(f"Published to Music Splitter Queue for job_id: {job_id}, song_id: {song_id}")

# Core functionality
def download_song_to_gcs(song_id, song_name, artist_name):
    print(f"Downloading: {song_name} by {artist_name} (ID: {song_id})")

    query = f"{song_name} {artist_name}"
    local_wav_path = os.path.join(DOWNLOAD_FOLDER, f"{song_id}.wav")
    gcs_path = f"songs/{song_id}/original.wav"

    # Skip if already uploaded
    if gcs_file_exists(f"gs://{BUCKET_NAME}/{gcs_path}"):
        print(f"File already exists in GCS: {gcs_path}")
        return

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{song_id}.%(ext)s"),
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch:{query}"])
    except Exception as e:
        print(f"Error downloading from YouTube: {e}")
        raise

    upload_file_to_gcs(f"gs://{BUCKET_NAME}/{gcs_path}", local_wav_path)
    os.remove(local_wav_path)
    print(f"Download complete for: {song_id}")

def callback(ch, method, properties, body):
    print("Callback triggered")
    try:
        message = json.loads(body)
        print(message)
        job_id = message["job_id"]
        song_id = message["song_id"]
        song_name = message["title"]
        artist_name = message["artist"]

        print(f"Received job: {song_id}")

        try:
            download_song_to_gcs(song_id, song_name, artist_name)
            # Notify the event tracker about the success
            notify_event_tracker(ch, "Completed", job_id, song_id)
            # Publish splitter job
            publish_to_music_splitter_queue(ch, job_id, song_id, song_name, artist_name)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as processing_error:
            #  Notify event tracker about failure
            print(f"Error processing job_id {job_id} songId {song_id}\n: {processing_error}")
            traceback.print_exc()
            notify_event_tracker(ch, "Failed", job_id, song_id,
                                 f"Internal error while downloading music for job: {job_id}, song ID: {song_id}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("Unexpected error:", e)
        traceback.print_exc()
        notify_event_tracker(ch, "Failed", error_message=f"Malformed message received: {body}, error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_worker():
    # TODO: Add login and heartbeat params
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
    channel.queue_declare(queue=MUSIC_SPLITTER_QUEUE_NAME)

    # TODO: Remove durability
    channel.queue_declare(queue=DOWNLOAD_QUEUE_NAME, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(DOWNLOAD_QUEUE_NAME, callback)

    print(f"Downloader Service is listening on queue: {DOWNLOAD_QUEUE_NAME}")
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
