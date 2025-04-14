import requests
from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
import re
import datetime
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import uuid
import pika
import json
from shared import constants

app = Flask(__name__)
load_dotenv()

# ---------- CONFIGURATION ----------
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
GENIUS_API_KEY = os.getenv("GENIUS_API_KEY")
GENIUS_SEARCH_URL = os.getenv("GENIUS_SEARCH_URL")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH")
app.secret_key = os.getenv("FLASK_SECRET")
RABBITMQ_HOST = constants.RABBITMQ_HOST
BUCKET_NAME = constants.GCS_BUCKET_NAME
DOWNLOAD_QUEUE_NAME = constants.DOWNLOAD_QUEUE_NAME
EVENT_TRACKER_QUEUE_NAME = constants.EVENT_TRACKER_QUEUE_NAME
DATA_READER_URL = constants.DATA_READER_URL
AUTH_URL = constants.AUTH_URL

# ---------- RABBITMQ CONNECTION SETUP ----------
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

# Declare queues once during startup
channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
channel.queue_declare(queue=DOWNLOAD_QUEUE_NAME, durable=True)


@app.route('/set_user')
def set_user():
    name = request.args.get('name')
    email = request.args.get('email')
    picture = request.args.get('picture')

    if name:
        session['name'] = name
    if email:
        session['email'] = email
    if picture:
        session['picture'] = picture

    return redirect('/')

@app.context_processor
def inject_user():
    return {
        "name": session.get("name", "Guest"),
        "email": session.get("email"),
        "picture": session.get("picture"),
    }

def generate_signed_url(bucket_name, blob_name, expiration_minutes=10):
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
    storage_client = storage.Client(credentials=credentials)

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="GET",
    )
    return url

def get_title_artist_from_genius(song_id):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    response = requests.get(f"https://api.genius.com/songs/{song_id}", headers=headers)
    if response.status_code == 200:
        song = response.json().get("response", {}).get("song", {})
        return song.get("title"), song.get("primary_artist", {}).get("name")
    return None, None


@app.route('/')
def home():
    if "email" not in session:
        return render_template('home.html', history_songs=[], similar_by_history=[])
    
    user_email = session["email"]
    user_doc = requests.get(f"{DATA_READER_URL}/users/{user_email}").json()

    history_songs = []
    similar_by_history = []

    if user_doc.get("email"):
        song_ids = user_doc.get("downloaded_songs", [])[-8:]
        print(song_ids)
        for song_id in song_ids:
            # Get song title/artist from Genius
            title, artist = get_title_artist_from_genius(song_id)
            if not title or not artist:
                continue
            image = get_genius_thumbnail(title, artist)

            history_songs.append({
                "song_id": song_id,
                "title": title,
                "artist": artist,
                "image": image or "https://via.placeholder.com/150"
            })
            similar = get_similar_songs_from_lastfm(artist, title)
            for s in similar:
                s["source_song_id"] = song_id  # for grouping if needed
            similar_by_history.extend(similar)

    return render_template('home.html',
                        history_songs=history_songs,
                        similar_by_history=similar_by_history)

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect({AUTH_URL})

@app.route('/error')
def error_page():
    return render_template('error.html')

@app.route('/search')
def search():
    query = request.args.get("q")
    if not query:
        return jsonify([])

    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": query}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)

    if response.status_code == 200:
        return jsonify(response.json()["response"]["hits"])

    print("Genius error:", response.status_code, response.text)
    return jsonify([])


def clean_song_title(full_title):
    full_title = re.sub(r"\s+by\s+.*", "", full_title, flags=re.IGNORECASE)
    full_title = re.sub(r"\(.*?\)", "", full_title)
    full_title = full_title.split(" - ")[0]
    return full_title.strip()

def get_artist_from_song_name(song_name):
    search_url = "http://ws.audioscrobbler.com/2.0/"
    search_params = {
        'method': 'track.search',
        'track': song_name,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': 1
    }

    res = requests.get(search_url, params=search_params).json()
    results = res.get('results', {}).get('trackmatches', {}).get('track', [])
    
    if results:
        top_result = results[0]
        return top_result['artist'], top_result['name']
    return None, None

def get_genius_thumbnail(title, artist):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": f"{title} {artist}"}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)

    if response.status_code == 200:
        hits = response.json()["response"]["hits"]
        if hits:
            return hits[0]["result"]["song_art_image_thumbnail_url"]
    return None

def get_genius_song_id(title, artist):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": f"{title} {artist}"}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)

    if response.status_code == 200:
        hits = response.json()["response"]["hits"]
        if hits:
            return hits[0]["result"]["id"]  # ← Genius song ID
    return None

def get_similar_songs_from_lastfm(artist, track):
    # track = track.strip().lower().title()
    # artist = artist.strip().lower().title()
    # print(f"[song_page-b] title={track}, artist={artist}")
    similar_url = "http://ws.audioscrobbler.com/2.0/"
    similar_params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': track,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': 8
    }

    response = requests.get(similar_url, params=similar_params).json()
    similar_tracks = response.get('similartracks', {}).get('track', [])

    # Attach Genius image to each
    for t in similar_tracks:
        title = t['name']
        artist = t['artist']['name']
        genius_img = get_genius_thumbnail(title, artist)
        t['genius_image'] = genius_img or 'https://via.placeholder.com/150'
        genius_id = get_genius_song_id(title, artist)
        t['song_id'] = genius_id

    return similar_tracks

@app.route('/get_lyrics/<path:song_path>')
def get_lyrics(song_path):
    # Generate signed URL
    signed_url = generate_signed_url(BUCKET_NAME, f"songs/{song_path}", expiration_minutes=10)

    # Fetch content server-side
    res = requests.get(signed_url)
    if res.status_code != 200:
        return "Failed to fetch lyrics", 500

    return Response(res.content, content_type='application/json')

@app.route('/song/<song_id>')
def song_page(song_id):
    raw_title = request.args.get("title")
    raw_artist = request.args.get("artist")
    if not raw_title or not raw_artist:
        return "Missing song title or artist", 400

    cleaned_title = clean_song_title(raw_title)

    # Get artist and track name from Last.fm
    artist, track = get_artist_from_song_name(cleaned_title)
    if not artist or not track:
        artist, track = raw_artist, cleaned_title

    # Fetch similar songs
    similar_songs = get_similar_songs_from_lastfm(artist, track)

    audio_blob = f"songs/{song_id}/original.wav"
    song_url = generate_signed_url(BUCKET_NAME, audio_blob)

    user_email = session.get("email")
    if user_email:
        try:
            history_message = {
                "song_id": str(song_id),
                "timestamp": str(datetime.datetime.now(datetime.timezone.utc).isoformat()),
                "source": "history",
                "user_email": user_email
            }

            channel.basic_publish(
                exchange="",
                routing_key=EVENT_TRACKER_QUEUE_NAME,
                body=json.dumps(history_message),
                properties=pika.BasicProperties()
            )
            print(f"[song_page] Logged song view for {user_email} - {song_id}")
        except Exception as e:
            print(f"Error sending play event to event tracker: {e}")


    return render_template("song.html",
                        song_title=raw_title,
                        song_artist=raw_artist,
                        song_id=song_id,
                        song_url=song_url,
                        lyrics_url=f"/get_lyrics/{song_id}/lyrics.json",
                        similar_songs=similar_songs)

@app.route('/start_processing', methods=['POST'])
def start_processing():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    title = data.get("title")
    artist = data.get("artist")
    song_id = data.get("song_id")

    if not title or not artist or not song_id:
        return jsonify({"error": "Missing title, artist, or song_id"}), 400

    job_id = str(uuid.uuid4())

    event_tracker_message = {
        "job_id": job_id,
        "song_id": str(song_id),
        "timestamp": str(datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "source": "frontend",
    }

    download_message = {
        "job_id": job_id,
        "song_id": str(song_id),
        "title": title,
        "artist": artist
    }
    print("[Queueing Job]", download_message)

    try:
        # Notify the event tracker about the new job.
        channel.basic_publish(
            exchange="",
            routing_key=EVENT_TRACKER_QUEUE_NAME,
            body=json.dumps(event_tracker_message),
            properties=pika.BasicProperties()
        )

        # TODO: Remove durability
        channel.basic_publish(
            exchange='',
            routing_key=DOWNLOAD_QUEUE_NAME,
            body=json.dumps(download_message),
            properties=pika.BasicProperties(delivery_mode=2)
        )

        # TODO: Cleanup?
        # Store metadata in job_status_store immediately
    except Exception as e:
        print("Error queuing task:", e)
        return jsonify({"error": "Failed to queue task", "details": str(e)}), 500

    if request.is_json:
        return jsonify({
            "job_id": job_id,
            "song_id": song_id,
            "redirect_url": f"/processing/{job_id}?title={title}&artist={artist}&song={song_id}"
        }), 200
    else:
        return redirect(url_for('processing_page', job_id=job_id, title=title, artist=artist, song=song_id))

@app.route('/processing/<job_id>')
def processing_page(job_id):
    title = request.args.get("title", "Loading...")
    artist = request.args.get("artist", "Please wait")
    song = request.args.get("song", "Please wait")
    print(f"[processing_page] job_id={job_id}, title={title}, artist={artist}, song={song}")
    return render_template('processing.html', job_id=job_id, title=title, artist=artist, song=song, data_reader_url=DATA_READER_URL)

job_status_store = {}

@app.route('/mark_complete/<job_id>/<song_id>', methods=['POST'])
def mark_complete(job_id, song_id):
    job = job_status_store.get(job_id)
    if not job:
        return jsonify({"error": "Job ID not found"}), 404

    job["status"] = "done"
    print(f"Job {job_id} is now being processed.")
    return jsonify({"message": f"Job {job_id} marked as complete for song {song_id}."})

@app.route('/check_status/<job_id>')
def check_status(job_id):
    print(f"[check_status] Proxying to data-reader for job_id: {job_id}")
    try:
        resp = requests.get(f"{DATA_READER_URL}/job-history/{job_id}", timeout=5)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
    except Exception as e:
        print(f"[check_status] Error fetching status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)