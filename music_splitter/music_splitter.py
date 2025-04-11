import json
import os
import shutil
import traceback

import pika
from spleeter.audio.adapter import AudioAdapter
from spleeter.separator import Separator

from shared import gcs_utils
from shared import constants

RABBITMQ_HOST = constants.RABBITMQ_HOST
LYRICS_QUEUE_NAME = constants.LYRICS_QUEUE_NAME
SPLIT_QUEUE_NAME = constants.SPLIT_QUEUE_NAME

def split_and_upload_instrumental(song_id: str):
    print(f"Processing song ID: {song_id}")

    instrumental_url = gcs_utils.get_instrumental_url(song_id)
    vocals_url = gcs_utils.get_vocals_url(song_id)
    if gcs_utils.gcs_file_exists(instrumental_url) and gcs_utils.gcs_file_exists(vocals_url):
        print(f"Instrumental and vocals files already exist, skipping processing for {song_id}")
        return

    # Use persistent working dir
    working_dir = os.path.join("downloads", song_id)
    os.makedirs(working_dir, exist_ok=True)

    original_path = os.path.join(working_dir, "original.wav")
    instrumental_wav_path = os.path.join(working_dir, "instrumental.wav")
    vocal_wav_path = os.path.join(working_dir, "vocal.wav")

    # Download original.wav from GCS
    original_url = gcs_utils.get_artifact_url(song_id, "original.wav")
    print(f"Downloading original.wav from: {original_url}")
    gcs_utils.download_file_from_gcs(original_url, original_path)

    # Split with Spleeter
    print("Running Spleeter...")
    separator = Separator('spleeter:2stems')
    audio_loader = AudioAdapter.default()

    waveform, sample_rate = audio_loader.load(original_path)
    separated = separator.separate(waveform)
    accompaniment = separated['accompaniment']
    vocals = separated['vocals']

    print("Saving instrumental.wav locally...")
    audio_loader.save(instrumental_wav_path, accompaniment, sample_rate=sample_rate)

    print("Saving vocals.wav locally...")
    audio_loader.save(vocal_wav_path, vocals, sample_rate=sample_rate)

    # Upload to GCS
    print(f"Uploading instrumental to: {instrumental_url}")
    gcs_utils.upload_file_to_gcs(instrumental_url, instrumental_wav_path)

    print(f"Uploading vocals to: {vocals_url}")
    gcs_utils.upload_file_to_gcs(vocals_url, vocal_wav_path)

    shutil.rmtree(working_dir)
    print(f"Done processing {song_id}")
    publish_to_lyrics_queue(song_id)

def publish_to_lyrics_queue(song_id):
    # Connect to RabbitMQ and publish the message to the Sync Lyrics Queue
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=3,
            retry_delay=5,
            socket_timeout=600
        ))
        channel = connection.channel()
        channel.queue_declare(queue=LYRICS_QUEUE_NAME, durable=True)
        message = {
            "song_id": song_id,
            "status": "ready_for_sync_lyrics"
        }
        channel.basic_publish(
            exchange='',
            routing_key=LYRICS_QUEUE_NAME,
            body=json.dumps(message)
        )
        print(f"Published to Sync Lyrics Queue: {song_id}")
        connection.close()
    except Exception as e:
        print(f"Error publishing to Sync Lyrics Queue: {e}")
        traceback.print_exc()

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        song_id = message["song_id"]
        print(f"Received message for songId: {song_id}")

        try:
            split_and_upload_instrumental(song_id)
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as ack_err:
                print(f"WARNING: Failed to ACK message {song_id}: {ack_err}")
        except Exception as processing_error:
            print(f"Error while processing songId {song_id}: {processing_error}")
            traceback.print_exc()
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as nack_err:
                print(f"WARNING: Failed to NACK message {song_id}: {nack_err}")
        #     ch.basic_ack(delivery_tag=method.delivery_tag)
        # except Exception as processing_error:
        #     print(f"Error while processing songId {song_id}: {processing_error}")
        #     traceback.print_exc()
        #     ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("Unexpected error:", e)
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    # TODO: Add a health check endpoint implementation.
    print("Starting music splitter worker...")
    # credentials = pika.PlainCredentials(constants.RABBITMQ_USER, constants.RABBITMQ_PASS)
    # connection = pika.BlockingConnection(pika.ConnectionParameters(
    #     host=constants.RABBITMQ_HOST,
    #     port=constants.RABBITMQ_PORT,
    #     credentials=credentials
    # ))
    connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    heartbeat=600,
    blocked_connection_timeout=300,
    connection_attempts=3,
    retry_delay=5,
    socket_timeout=600
))

    # connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))

    channel = connection.channel()

    channel.queue_declare(queue=SPLIT_QUEUE_NAME, durable=False)
    # channel.queue_declare(queue=constants.LYRICS_QUEUE_NAME, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(SPLIT_QUEUE_NAME, callback)

    print("Worker listening on queue: " + SPLIT_QUEUE_NAME)
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
