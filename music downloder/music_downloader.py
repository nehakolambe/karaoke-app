import json
import os
import traceback
import yt_dlp
import pika
from shared.gcs_utils import upload_file_to_gcs, gcs_file_exists, get_instrumental_url, get_vocals_url  # Fixed import

# Constants
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

RABBITMQ_HOST = "rabbitmq"  
DOWNLOAD_QUEUE_NAME = "download_jobs"
MUSIC_SPLITTER_QUEUE_NAME = "music_splitter_queue"
BUCKET_NAME = "bda-media-bucket"

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

    # Publish to Music Splitter Queue after successful upload
    publish_to_music_splitter_queue(song_id, song_name, artist_name)

def publish_to_music_splitter_queue(song_id, song_name, artist_name):
    # Connect to RabbitMQ and publish the message to the Music Splitter Queue
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()

        channel.queue_declare(queue=MUSIC_SPLITTER_QUEUE_NAME)

        message = {
            "song_id": song_id,
            "song_name": song_name,
            "artist_name": artist_name,
            "status": "ready_for_split"
        }
        channel.basic_publish(
            exchange='',
            routing_key=MUSIC_SPLITTER_QUEUE_NAME,
            body=json.dumps(message)
        )
        print(f"Published to Music Splitter Queue: {song_id}")
        connection.close()
    except Exception as e:
        print(f"Error publishing to Music Splitter Queue: {e}")
        traceback.print_exc()

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        song_id = message["song_id"]
        song_name = message["song_name"]
        artist_name = message["artist_name"]

        print(f"Received job: {song_id}")

        try:
            download_song_to_gcs(song_id, song_name, artist_name)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as processing_error:
            print(f"Error processing songId {song_id}: {processing_error}")
            traceback.print_exc()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("Unexpected error:", e)
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=DOWNLOAD_QUEUE_NAME)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(DOWNLOAD_QUEUE_NAME, callback)

    print(f"Downloader Service is listening on queue: {DOWNLOAD_QUEUE_NAME}")
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
