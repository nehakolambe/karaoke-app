import datetime
import json
import os
import traceback
import re

import requests
from bs4 import BeautifulSoup
import pika
from forcealign import ForceAlign

from shared import gcs_utils
from shared import constants

RABBITMQ_HOST = constants.RABBITMQ_HOST
LYRICS_QUEUE_NAME = constants.LYRICS_QUEUE_NAME
EVENT_TRACKER_QUEUE_NAME = constants.EVENT_TRACKER_QUEUE_NAME

# Queue functions
def notify_event_tracker(ch, status, job_id="", song_id="", error_message=None):
    event_tracker_message = {
        "job_id": job_id,
        "song_id": str(song_id),
        "source" : "lyrics_syncer",
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
    print(f"[EventTracker] Notified event tracker about lyrics syncing status for job: {job_id}")

def build_azlyrics_url(artist, title):
    """Build a URL to AZLyrics using only the main artist."""
    artist = re.split(r'\s*(?:ft\.?|feat\.?|featuring|&|,|/|\+|x)\s*', artist, flags=re.IGNORECASE)[0]

    def clean(string):
        return re.sub(r'[^a-z0-9]', '', string.lower())

    artist = clean(artist)
    title = clean(title)
    return f"https://www.azlyrics.com/lyrics/{artist}/{title}.html"

def scrape_azlyrics(url):
    """Scrape and clean lyrics from AZLyrics page."""
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        raise Exception(f"Failed to fetch AZLyrics page: {res.status_code}")

    soup = BeautifulSoup(res.text, "html.parser")
    divs = soup.find_all("div", attrs={"class": None, "id": None})

    for div in divs:
        if div.text.strip():
            raw_lyrics = div.text.strip()
            lines = raw_lyrics.splitlines()

            cleaned_lines = []
            for line in lines:
                stripped = line.strip()

                # Skip lines starting with [Explicit:]
                if stripped.startswith("[Explicit:]"):
                    continue

                # Remove [Clean and radio:] or similar
                stripped = re.sub(r"^\[\s*clean[^\]]*\]\s*:? ?", "", stripped, flags=re.IGNORECASE)

                cleaned_lines.append(stripped)

            return "\n".join(cleaned_lines)

    raise Exception("AZLyrics: No valid lyrics div found.")

def get_lyrics_from_azlyrics(artist, title):
    try:
        az_url = build_azlyrics_url(artist, title)
        print(f"[AZLyrics Scraper] Trying AZLyrics: {az_url}")
        lyrics = scrape_azlyrics(az_url)
        return lyrics
    except Exception as e:
        print(f"[AZLyrics Scraper] Failed for {artist} - {title}: {e}")
        return None

# Core functionality
def get_genius_url(song_id):
    return f"https://genius.com/songs/{song_id}"


def download_and_store_lyrics(song_id, song_name, artist_name):
    print(f"[Lyrics Scraper] Attempting AZLyrics for: {artist_name} - {song_name}")
    lyrics_text = get_lyrics_from_azlyrics(artist_name, song_name)

    if not lyrics_text:
        print(f"[Lyrics Scraper] Falling back to Genius for: {song_id}")
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
        except Exception as e:
            print(f"[Lyrics Scraper] Unexpected error while fetching Genius for {song_id}: {e}")
            traceback.print_exc()
            return False

    # Save lyrics to disk and GCS
    try:
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
        print(f"[Lyrics Scraper] Failed to save lyrics for {song_id}: {e}")
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
            # Shift both start and end backward by 0.2s, clamp to >= 0
            shifted_start = max(0, start - 0.3)
            shifted_end = max(0, end - 0.3)

            result.append({
                "line": " ".join(line_words),
                "start": shifted_start,
                "end": shifted_end
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
        job_id = message["job_id"]
        song_id = message["song_id"]
        song_name = message["song_name"]
        artist_name = message["artist_name"]
        print(f"[Lyrics Worker] Received message for song_id: {song_id}")

        try:
            # Step 1: Download lyrics. If it fails, skip alignment.
            if not download_and_store_lyrics(song_id, song_name, artist_name):
                print(f"[Lyrics Worker] Lyrics download failed for {song_id}, skipping.")
                # Notify event tracker about failure.
                notify_event_tracker(ch, "Failed", job_id, song_id,
                                     f"Lyrics download failed for job {job_id}, song {song_id}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Step 2: Align
            align_lyrics(song_id)

            # Notify event tracker about success
            notify_event_tracker(ch, "Completed", job_id, song_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as processing_error:
            print(f"[Lyrics Worker] Error processing song_id {song_id}: {processing_error}")
            traceback.print_exc()
            notify_event_tracker(ch, "Failed", job_id, song_id,
                                 f"Internal error while syncing lyrics for job: {job_id}, song ID: {song_id}-->\n{processing_error}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print("[Lyrics Worker] Unexpected error:", e)
        traceback.print_exc()
        notify_event_tracker(ch, "Failed", error_message=f"Malformed message received: {body}, error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

    channel.queue_declare(queue=LYRICS_QUEUE_NAME)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(LYRICS_QUEUE_NAME, callback)

    print(f"[Lyrics Worker] Listening on queue: {LYRICS_QUEUE_NAME}")
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
