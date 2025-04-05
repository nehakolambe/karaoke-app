import json
import os
import shutil
import traceback

import pika
from spleeter.audio.adapter import AudioAdapter
from spleeter.separator import Separator

from shared import gcs_utils

RABBITMQ_HOST = "localhost"  # or your RabbitMQ container/service name
QUEUE_NAME = "split-jobs"


def split_and_upload_instrumental(song_id: str):
    print(f"Processing song ID: {song_id}")

    # Use persistent working dir
    working_dir = os.path.join("downloads", song_id)
    os.makedirs(working_dir, exist_ok=True)

    original_path = os.path.join(working_dir, "original.wav")
    instrumental_wav_path = os.path.join(working_dir, "instrumental.wav")

    # Download original.wav from GCS
    original_url = gcs_utils.get_song_gcs_url(song_id, "original.wav")
    print(f"Downloading original.wav from: {original_url}")
    gcs_utils.download_file_from_gcs(original_url, original_path)

    # Split with Spleeter
    print("Running Spleeter...")
    separator = Separator('spleeter:2stems')
    audio_loader = AudioAdapter.default()

    waveform, sample_rate = audio_loader.load(original_path)
    separated = separator.separate(waveform)
    accompaniment = separated['accompaniment']

    print("Saving instrumental.wav locally...")
    audio_loader.save(instrumental_wav_path, accompaniment, sample_rate=sample_rate)

    # Upload to GCS
    instrumental_url = gcs_utils.get_instrumental_url(song_id)
    print(f"Uploading instrumental to: {instrumental_url}")
    gcs_utils.upload_file_to_gcs(instrumental_url, instrumental_wav_path)

    shutil.rmtree(working_dir)

    print("Done processing", song_id)


def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        song_id = message["song_id"]
        print(f"Received message for songId: {song_id}")
        split_and_upload_instrumental(song_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print("Unexpected error:", e)
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(QUEUE_NAME, callback)

    print("Worker listening on queue: " + QUEUE_NAME)
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
