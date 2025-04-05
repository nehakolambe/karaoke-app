import requests
from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

GENIUS_API_KEY = "<enter_genius_api_key>"
LASTFM_API_KEY = "<enter_lastfm_api_key>"
GENIUS_SEARCH_URL = "https://api.genius.com/search"

@app.context_processor
def inject_user():
    return dict(name="John") # Replace it with person name call

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/logout')
def logout():
    return "<h2>Logged out (dummy action)</h2><a href='/'>Go to Home</a>"

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

def search_genius_songs(query):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": query}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)
    if response.status_code == 200:
        hits = response.json()["response"]["hits"]
        if hits:
            return hits[0]["result"]
    return None

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

def get_similar_songs_from_lastfm(artist, track):
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

    return similar_tracks


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

    return render_template("song.html",
                        song_title=raw_title,
                        song_artist=raw_artist,
                        song_id=song_id,
                        similar_songs=similar_songs)

if __name__ == '__main__':
    app.run(debug=True)