import json
import os
import traceback

import requests
from bs4 import BeautifulSoup
import pika
from forcealign import ForceAlign

from shared import gcs_utils
from shared.constants import LYRICS_QUEUE_NAME, RABBITMQ_HOST


def get_genius_url(song_id: str) -> str:
    return f"https://genius.com/songs/{song_id}"


def download_and_store_lyrics(song_id: str) -> bool:
    print(f"[Lyrics Scraper] Fetching lyrics for Genius song ID: {song_id}")
    genius_url = get_genius_url(song_id)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(genius_url, headers=headers)
        if response.status_code != 200:
            print(f"[Lyrics Scraper] Failed to fetch Genius page for {song_id}")
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
        if not lyrics_divs:
            print(f"[Lyrics Scraper] No lyrics container found for {song_id}")
            return False

        lyrics = []
        for div in lyrics_divs:
            for elem in div.children:
                if elem.name == "a":
                    text = elem.get_text(separator="\n")
                elif elem.name is None:
                    text = str(elem).strip()
                else:
                    continue

                if text.startswith("[") and text.endswith("]"):
                    continue

                lyrics.append(text)

        lyrics_text = "\n".join(filter(None, (line.strip() for line in lyrics)))

        local_dir = os.path.join("downloads", song_id)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "lyrics.txt")

        with open(local_path, "w") as f:
            f.write(lyrics_text)

        lyrics_gcs_path = gcs_utils.get_artifact_url(song_id, "lyrics.txt")
        gcs_utils.upload_file_to_gcs(lyrics_gcs_path, local_path)

        print(f"[Lyrics Scraper] Uploaded lyrics.txt to {lyrics_gcs_path}")
        return True

    except Exception as e:
        print(f"[Lyrics Scraper] Unexpected error while fetching for {song_id}: {e}")
        traceback.print_exc()
        return False


def align_lyrics(song_id: str):
    print(f"[Lyrics Worker] Processing song ID: {song_id}")

    lyrics_url = gcs_utils.get_artifact_url(song_id, "lyrics.txt")
    vocals_url = gcs_utils.get_artifact_url(song_id, "vocals.wav")
    output_url = gcs_utils.get_artifact_url(song_id, "lyrics.json")

    if gcs_utils.gcs_file_exists(output_url):
        print(f"[Lyrics Worker] lyrics.json already exists, skipping {song_id}")
        return

    working_dir = os.path.join("downloads", song_id)
    os.makedirs(working_dir, exist_ok=True)

    try:
        local_lyrics = os.path.join(working_dir, "lyrics.txt")
        local_audio = os.path.join(working_dir, "vocals.wav")
        local_output = os.path.join(working_dir, "lyrics.json")

        # Download GCS lyrics and audio
        gcs_utils.download_file_from_gcs(lyrics_url, local_lyrics)
        gcs_utils.download_file_from_gcs(vocals_url, local_audio)

        with open(local_lyrics, 'r') as f:
            raw_lines = [line.strip() for line in f.readlines()]
        lines = [line.split() for line in raw_lines]
        flat_words = [w for line in lines for w in line]

        print(f"[Lyrics Worker] Running ForceAlign...")
        align = ForceAlign(audio_file=local_audio, transcript=' '.join(flat_words))
        aligned_words = align.inference()

        result = []
        w_idx = 0
        for original_words in lines:
            if not original_words:
                continue
            start, end = None, None
            line_words = []
            for word in original_words:
                if w_idx >= len(aligned_words):
                    break
                aligned_word = aligned_words[w_idx]
                line_words.append(word)
                if start is None:
                    start = aligned_word.time_start
                end = aligned_word.time_end
                w_idx += 1
            result.append({
                "line": " ".join(line_words),
                "start": start,
                "end": end
            })

        with open(local_output, "w") as f:
            json.dump(result, f, indent=2)
        gcs_utils.upload_file_to_gcs(output_url, local_output)

        print(f"[Lyrics Worker] Uploaded lyrics.json to: {output_url}")

    finally:
        if os.path.exists(working_dir):
            for f in os.listdir(working_dir):
                os.remove(os.path.join(working_dir, f))
            os.rmdir(working_dir)
        print(f"[Lyrics Worker] Done processing {song_id}")


def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        song_id = message["song_id"]
        print(f"[Lyrics Worker] Received message for song_id: {song_id}")

        try:
            # Step 1: Download lyrics. If it fails, skip alignment.
            if not download_and_store_lyrics(song_id):
                print(f"[Lyrics Worker] Lyrics download failed for {song_id}, skipping.")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Step 2: Align
            align_lyrics(song_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as processing_error:
            print(f"[Lyrics Worker] Error processing song_id {song_id}: {processing_error}")
            traceback.print_exc()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("[Lyrics Worker] Unexpected error:", e)
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=LYRICS_QUEUE_NAME)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(LYRICS_QUEUE_NAME, callback)

    print(f"[Lyrics Worker] Listening on queue: {LYRICS_QUEUE_NAME}")
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
