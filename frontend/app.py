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
from shared.gcs_utils import upload_file_to_gcs, gcs_file_exists
import yt_dlp
from shared import constants
from urllib.parse import quote_plus
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
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
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
GKE_API_URL = "http://34.134.220.179:80"

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

    try:
        response = requests.get(f"{GKE_API_URL}/api/user-history/{user_email}")
        data = response.json()
        song_ids = data.get("downloaded_song_ids", [])
    except Exception as e:
        print(f"Error fetching downloaded songs from GKE: {e}")
        song_ids = []

    history_songs = []
    similar_by_history = []

    for song_id in song_ids:
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
            s["source_song_id"] = song_id
        similar_by_history.extend(similar)

    return render_template('home.html',
                            history_songs=history_songs,
                            similar_by_history=similar_by_history)


# @app.route('/')
# def home():
#     if "email" not in session:
#         return render_template('home.html', history_songs=[], similar_by_history=[])
    
#     user_email = session["email"]
#     user_doc = requests.get(f"{DATA_READER_URL}/users/{user_email}").json()

#     history_songs = []
#     similar_by_history = []

#     if user_doc.get("email"):
#         song_ids = user_doc.get("downloaded_songs", [])[-8:]
#         print(song_ids)
#         for song_id in song_ids:
#             # Get song title/artist from Genius
#             title, artist = get_title_artist_from_genius(song_id)
#             if not title or not artist:
#                 continue
#             image = get_genius_thumbnail(title, artist)

#             history_songs.append({
#                 "song_id": song_id,
#                 "title": title,
#                 "artist": artist,
#                 "image": image or "https://via.placeholder.com/150"
#             })
#             similar = get_similar_songs_from_lastfm(artist, title)
#             for s in similar:
#                 s["source_song_id"] = song_id  # for grouping if needed
#             similar_by_history.extend(similar)

#     return render_template('home.html',
#                         history_songs=history_songs,
#                         similar_by_history=similar_by_history)

@app.route('/profile')
def profile():
    return render_template('profile.html')

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

def build_azlyrics_url(artist, title):
    artist = re.split(r'\s*(?:ft\.?|feat\.?|featuring|&|,|/|\+|x)\s*', artist, flags=re.IGNORECASE)[0]
    def clean(string):
        return re.sub(r'[^a-z0-9]', '', string.lower())
    return f"https://www.azlyrics.com/lyrics/{clean(artist)}/{clean(title)}.html"

def scrape_azlyrics(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch AZLyrics: {res.status_code}")
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, "html.parser")
    divs = soup.find_all("div", attrs={"class": None, "id": None})

    for div in divs:
        if div.text.strip():
            lines = div.text.strip().splitlines()
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[Explicit:]"):
                    continue
                stripped = re.sub(r"^\[\s*clean[^\]]*\]\s*:? ?", "", stripped, flags=re.IGNORECASE)
                cleaned_lines.append(stripped)
            return "\n".join(cleaned_lines)

    raise Exception("No valid lyrics div found.")

def download_lyrics_and_upload(song_id, title, artist):
    print(f"[Lyrics] Attempting AZLyrics for: {artist} - {title}")
    lyrics = None
    try:
        url = build_azlyrics_url(artist, title)
        lyrics = scrape_azlyrics(url)
        print(f"[Lyrics] Scraped from AZLyrics")
    except Exception as e:
        print(f"[Lyrics] AZLyrics failed: {e}")
        print(f"[Lyrics] Trying Genius fallback...")

        # Genius fallback
        headers = {"User-Agent": "Mozilla/5.0"}
        genius_url = f"https://genius.com/songs/{song_id}"
        try:
            res = requests.get(genius_url, headers=headers)
            if res.status_code != 200:
                raise Exception(f"Genius failed: {res.status_code}")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            divs = soup.find_all("div", {"data-lyrics-container": "true"})
            if not divs:
                raise Exception("No Genius lyrics found")

            lyrics = "\n".join([
                elem.get_text(separator="\n").strip()
                for div in divs
                for elem in div.children
                if (elem.name is None or elem.name == "a")
            ])
        except Exception as gerr:
            print(f"[Lyrics] Genius fallback also failed: {gerr}")
            return None

    if not lyrics or not lyrics.strip():
        print(f"[Lyrics] Both AZLyrics and Genius returned empty.")
        return None

    local_path = os.path.join(DOWNLOAD_FOLDER, f"{song_id}_lyrics.txt")
    with open(local_path, "w") as f:
        f.write(lyrics)

    gcs_path = f"songs/{song_id}/lyrics.txt"
    upload_file_to_gcs(f"gs://{BUCKET_NAME}/{gcs_path}", local_path)
    os.remove(local_path)
    print(f"[Lyrics] Uploaded lyrics.txt to GCS: {gcs_path}")
    return True


# def download_lyrics_and_upload(song_id, title, artist):
#     print(f"[Lyrics] Attempting AZLyrics for: {artist} - {title}")
#     lyrics = None
#     try:
#         url = build_azlyrics_url(artist, title)
#         lyrics = scrape_azlyrics(url)
#         print(f"[Lyrics] Scraped from AZLyrics")
#     except Exception as e:
#         print(f"[Lyrics] AZLyrics failed: {e}")
#         print(f"[Lyrics] Trying Genius fallback...")

#         # Genius fallback
#         headers = {"User-Agent": "Mozilla/5.0"}
#         genius_url = f"https://genius.com/songs/{song_id}"
#         try:
#             res = requests.get(genius_url, headers=headers)
#             if res.status_code != 200:
#                 raise Exception(f"Genius failed: {res.status_code}")
#             from bs4 import BeautifulSoup
#             soup = BeautifulSoup(res.text, "html.parser")
#             divs = soup.find_all("div", {"data-lyrics-container": "true"})
#             if not divs:
#                 raise Exception("No Genius lyrics found")

#             lyrics = "\n".join([
#                 elem.get_text(separator="\n").strip()
#                 for div in divs
#                 for elem in div.children
#                 if (elem.name is None or elem.name == "a")
#             ])
#         except Exception as gerr:
#             print(f"[Lyrics] Genius fallback also failed: {gerr}")
#             return False

#     # Save locally & upload
#     local_path = os.path.join(DOWNLOAD_FOLDER, f"{song_id}_lyrics.txt")
#     with open(local_path, "w") as f:
#         f.write(lyrics)

#     gcs_path = f"songs/{song_id}/lyrics.txt"
#     upload_file_to_gcs(f"gs://{BUCKET_NAME}/{gcs_path}", local_path)
#     os.remove(local_path)
#     print(f"[Lyrics] Uploaded lyrics.txt to GCS: {gcs_path}")
#     return True

def download_song_to_gcs_and_queue_job(song_id, song_name, artist_name):
    print(f"Downloading: {song_name} by {artist_name} (ID: {song_id})")

    query = f"{song_name} {artist_name} audio"
    local_wav_path = os.path.join(DOWNLOAD_FOLDER, f"{song_id}.wav")
    gcs_audio_path = f"songs/{song_id}/original.wav"
    gcs_lyrics_path = f"songs/{song_id}/lyrics.txt"

    # Skip download if audio already exists
    if not gcs_file_exists(f"gs://{BUCKET_NAME}/{gcs_audio_path}"):
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
        upload_file_to_gcs(f"gs://{BUCKET_NAME}/{gcs_audio_path}", local_wav_path)
        os.remove(local_wav_path)
        print(f"Upload complete for: {song_id}")
    else:
        print(f"[Skip] Audio already exists in GCS for {song_id}")

    # Skip lyrics download if they already exist
    if not gcs_file_exists(f"gs://{BUCKET_NAME}/{gcs_lyrics_path}"):
        if not download_lyrics_and_upload(song_id, song_name, artist_name):
            print(f"[Lyrics] Failed to fetch lyrics for {song_id}, skipping job trigger.")
            return "LYRICS_FAILED"
    else:
        print(f"[Skip] Lyrics already exist in GCS for {song_id}")

    # Send POST request to GKE endpoint to start processing
    try:
        response = requests.post(
            f"{GKE_API_URL}/start_processing",
            json={
                "song_id": song_id,
                "title": song_name,
                "artist": artist_name
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()

        print(f"Successfully triggered processing job: {response.json()}")
    except Exception as e:
        print(f"Failed to trigger processing job: {e}")
        return None


# def download_song_to_gcs_and_queue_job(song_id, song_name, artist_name):
#     print(f"Downloading: {song_name} by {artist_name} (ID: {song_id})")

#     query = f"{song_name} {artist_name} audio"
#     local_wav_path = os.path.join(DOWNLOAD_FOLDER, f"{song_id}.wav")
#     gcs_path = f"songs/{song_id}/original.wav"

#     # Skip if already uploaded
#     if gcs_file_exists(f"gs://{BUCKET_NAME}/{gcs_path}"):
#         print(f"File already exists in GCS: {gcs_path}")
#         return

#     ydl_opts = {
#         'format': 'bestaudio/best',
#         'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{song_id}.%(ext)s"),
#         'postprocessors': [
#             {
#                 'key': 'FFmpegExtractAudio',
#                 'preferredcodec': 'wav',
#                 'preferredquality': '192',
#             }
#         ],
#     }

#     try:
#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             ydl.download([f"ytsearch:{query}"])
#     except Exception as e:
#         print(f"Error downloading from YouTube: {e}")
#         raise

#     upload_file_to_gcs(f"gs://{BUCKET_NAME}/{gcs_path}", local_wav_path)
#     os.remove(local_wav_path)
#     print(f"Download complete for: {song_id}")

#     if not download_lyrics_and_upload(song_id, song_name, artist_name):
#         print(f"[Lyrics] Failed to fetch lyrics for {song_id}, skipping job trigger.")
#         return None

    # # Send POST request to GKE endpoint to start processing
    # try:
    #     response = requests.post(
    #         f"{GKE_API_URL}/start_processing",
    #         json={
    #             "song_id": song_id,
    #             "title": song_name,
    #             "artist": artist_name
    #         },
    #         timeout=10
    #     )
    #     response.raise_for_status()
    #     print(f"Successfully triggered processing job: {response.json()}")
    # except Exception as e:
    #     print(f"Failed to trigger processing job: {e}")
    #     return None

    # # TODO: Handle unknown_job_id case in HTML.
    # return response.json()

# @app.route("/start_processing", methods=["POST"])
# def start_processing():
#     data = request.get_json() if request.is_json else request.form
#     song_id = str(data.get("song_id"))

#     if not song_id:
#         return jsonify({"error": "Missing song_id"}), 400

#     title, artist = get_title_artist_from_genius(song_id)
#     if not title or not artist:
#         return jsonify({"error": "Failed to get song metadata from Genius"}), 400

#     # job_id = str(uuid.uuid4())

#     # Launch background thread to handle downloading and processing
#     import threading
#     def background_task():
#         print(f"[Thread] Starting processing for song_id={song_id}")
#         result = download_song_to_gcs_and_queue_job(song_id, title, artist)

#         if result == "LYRICS_FAILED":
#             print(f"[Thread] Lyrics fetch failed for song_id={song_id}")
#             return

#         job_id = result.get("job_id")  # <- Pull the job_id returned by GKE
#         print(f"[Thread] Job {job_id} triggered successfully.")


#     threading.Thread(target=background_task, daemon=True).start()

#     # Immediately return redirect URL for the loading screen
#     redirect_url = url_for('processing_page', job_id=job_id, title=title, artist=artist, song=song_id)
#     return jsonify({
#         "song_id": song_id,
#         "redirect_url": redirect_url
#     }), 200


@app.route("/start_processing", methods=["POST"])
def start_processing():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    # title = data["title"]
    # artist = data["artist"]
    song_id = str(data["song_id"])
    title, artist = get_title_artist_from_genius(song_id)
    print(song_id,title,artist) 
    # Generate job ID
    # job_id = str(uuid.uuid4()

    try:
        # Download the song locally and upload to GCS, then queue the job in the remote processing cluster.
        job_id = download_song_to_gcs_and_queue_job(song_id, title, artist)
        if job_id == "LYRICS_FAILED":
            print(f"[start_processing] Lyrics download failed, redirecting to error page.")
            return redirect(url_for('error_page'))
        print(job_id)
        if request.is_json:
            return jsonify({
                "song_id": song_id,
                "redirect_url": f"/processing/{job_id}?title={title}&artist={artist}&song={song_id}"
            }), 200
        else:
            return redirect(url_for('processing_page', job_id=job_id, title=title, artist=artist, song=song_id))
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500

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
    # TODO: Move to remote frontend.
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

    # user_email = session.get("email")
    # if user_email:
    #     try:
    #         connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    #         channel = connection.channel()
    #         channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

    #         history_message = {
    #             "song_id": str(song_id),
    #             "timestamp": str(datetime.datetime.now(datetime.timezone.utc).isoformat()),
    #             "source": "history",
    #             "user_email": user_email
    #         }

    #         channel.basic_publish(
    #             exchange="",
    #             routing_key=EVENT_TRACKER_QUEUE_NAME,
    #             body=json.dumps(history_message),
    #             properties=pika.BasicProperties()
    #         )
    #         connection.close()
    #         print(f"[song_page] Logged song view for {user_email} - {song_id}")
    #     except Exception as e:
    #         print(f"Error sending play event to event tracker: {e}")


    return render_template("song.html",
                        song_title=raw_title,
                        song_artist=raw_artist,
                        song_id=song_id,
                        song_url=song_url,
                        lyrics_url=f"/get_lyrics/{song_id}/lyrics.json",
                        similar_songs=similar_songs)

# @app.route('/local_status/<job_id>')
# def local_status(job_id):
#     # These could be passed via query params or looked up locally
#     title = request.args.get("title")
#     artist = request.args.get("artist")
#     song_id = request.args.get("song_id")

#     # Pass the full GKE status check URL
#     frontend_check_url = f"https://api.voxoff.app/check_status/{job_id}"

#     return render_template("processing_local.html",
#         job_id=job_id,
#         title=title,
#         artist=artist,
#         song=song_id,
#         frontend_check_url=frontend_check_url
#     )

@app.route('/processing/<job_id>')
def processing_page(job_id):
    title = request.args.get("title", "Loading...")
    artist = request.args.get("artist", "Please wait")
    song = request.args.get("song", "Please wait")
    # frontend_check_url = f"{GKE_API_URL}/check_status/{job_id}"
    user_email = session.get("email")
    frontend_check_url = f"{GKE_API_URL}/check_status/{job_id}?email={quote_plus(user_email)}&song_id={quote_plus(song)}"
    print(f"[processing_page] job_id={job_id}, title={title}, artist={artist}, song={song}, url={frontend_check_url}")
    return render_template('processing_local.html', job_id=job_id, title=title, artist=artist, song=song, frontend_check_url=frontend_check_url)


# @app.route('/start_processing', methods=['POST'])
# def start_processing():
#     if request.is_json:
#         data = request.get_json()
#     else:
#         data = request.form

#     title = data.get("title")
#     artist = data.get("artist")
#     song_id = data.get("song_id")

#     if not title or not artist or not song_id:
#         return jsonify({"error": "Missing title, artist, or song_id"}), 400

#     job_id = str(uuid.uuid4())

#     event_tracker_message = {
#         "job_id": job_id,
#         "song_id": str(song_id),
#         "timestamp": str(datetime.datetime.now(datetime.timezone.utc).isoformat()),
#         "source": "frontend",
#     }

#     download_message = {
#         "job_id": job_id,
#         "song_id": str(song_id),
#         "title": title,
#         "artist": artist
#     }
#     print("[Queueing Job]", download_message)

#     try:
#         connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
#         channel = connection.channel()

#         # Notify the event tracker about the new job.
#         channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
#         channel.basic_publish(
#             exchange="",
#             routing_key=EVENT_TRACKER_QUEUE_NAME,
#             body=json.dumps(event_tracker_message),
#             properties=pika.BasicProperties()
#         )

#         # TODO: Remove durability
#         channel.queue_declare(queue=DOWNLOAD_QUEUE_NAME, durable=True)
#         channel.basic_publish(
#             exchange='',
#             routing_key=DOWNLOAD_QUEUE_NAME,
#             body=json.dumps(download_message),
#             properties=pika.BasicProperties(delivery_mode=2)
#         )

#         # TODO: Cleanup?
#         # Store metadata in job_status_store immediately
#         job_status_store[job_id] = {
#             "status": "pending",
#             "song_id": str(song_id),
#             "title": title,
#             "artist": artist
#         }

#     except Exception as e:
#         print("Error queuing task:", e)
#         return jsonify({"error": "Failed to queue task", "details": str(e)}), 500

#     if request.is_json:
#         return jsonify({
#             "job_id": job_id,
#             "song_id": song_id,
#             "redirect_url": f"/processing/{job_id}?title={title}&artist={artist}&song={song_id}"
#         }), 200
#     else:
#         return redirect(url_for('processing_page', job_id=job_id, title=title, artist=artist, song=song_id))

# job_status_store = {}

# @app.route('/mark_complete/<job_id>/<song_id>', methods=['POST'])
# def mark_complete(job_id, song_id):
#     job = job_status_store.get(job_id)
#     if not job:
#         return jsonify({"error": "Job ID not found"}), 404

#     job["status"] = "done"
#     print(f"Job {job_id} is now being processed.")
#     return jsonify({"message": f"Job {job_id} marked as complete for song {song_id}."})

# @app.route('/check_status/<job_id>')
# def check_status(job_id):
#     print(f"Checking status for job: {job_id}")
#     print("Current store:", job_status_store)
#     status = job_status_store.get(job_id)
#     if not status:
#         return jsonify({"status": "pending"}), 202

#     return jsonify({
#         "status": status.get("status", "pending"),
#         "song_id": status["song_id"],
#         "title": status["title"],
#         "artist": status["artist"]
#     }), 200


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5002)