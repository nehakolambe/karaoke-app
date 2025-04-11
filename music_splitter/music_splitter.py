import json
import os
import shutil
import traceback

import pika
from spleeter.audio.adapter import AudioAdapter
from spleeter.separator import Separator

from shared import gcs_utils
from shared import constants


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

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        song_id = message["song_id"]
        print(f"Received message for songId: {song_id}")

        try:
            split_and_upload_instrumental(song_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as processing_error:
            print(f"Error while processing songId {song_id}: {processing_error}")
            traceback.print_exc()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("Unexpected error:", e)
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    # TODO: Add a health check endpoint implementation.

    connection = pika.BlockingConnection(pika.ConnectionParameters(constants.RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=constants.SPLIT_QUEUE_NAME)
    channel.queue_declare(queue=constants.LYRICS_QUEUE_NAME)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(constants.SPLIT_QUEUE_NAME, callback)

    print("Worker listening on queue: " + constants.SPLIT_QUEUE_NAME)
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
