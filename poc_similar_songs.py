import requests
import re

LASTFM_API_KEY = "9400d086d8cb09c8f3db5004d15d36e8"
GENIUS_API_KEY = "Su_sv_qBB0tEdQrsGa6q-W84uzxU2zMdhuvag2nq4CLF0wrKosbhCzFMToY0nsjn"

GENIUS_SEARCH_URL = "https://api.genius.com/search"

def search_genius_songs(query):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": query}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)
    if response.status_code == 200:
        hits = response.json()["response"]["hits"]
        if hits:
            top_result = hits[0]["result"]
            return top_result["full_title"]
    return None

def clean_song_title(full_title):
    # Remove ' by ARTIST' only if it appears at the end
    if re.search(r"\s+by\s+\S+$", full_title, re.IGNORECASE):
        full_title = re.sub(r"\s+by\s+\S+$", "", full_title, flags=re.IGNORECASE)

    # Remove text in parentheses (like (From "Movie"))
    full_title = re.sub(r"\(.*?\)", "", full_title)
    # Remove anything after a dash (like - Remix)
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
    else:
        return None, None

def get_similar_songs_from_input(user_input):
    genius_full_title = search_genius_songs(user_input)
    if not genius_full_title:
        print("Could not find song on Genius.")
        return

    print(f"Genius found: {genius_full_title}")
    
    cleaned_title = clean_song_title(genius_full_title)
    print(f"Using cleaned title: {cleaned_title}")

    artist, track = get_artist_from_song_name(cleaned_title)
    if not artist or not track:
        print("Could not find track info on Last.fm.")
        return

    print(f"Top match on Last.fm: {track} by {artist}")

    similar_url = "http://ws.audioscrobbler.com/2.0/"
    similar_params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': track,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': 10
    }

    response = requests.get(similar_url, params=similar_params).json()
    similar_tracks = response.get('similartracks', {}).get('track', [])

    if not similar_tracks:
        print("No similar songs found.")
        return

    print("\nSimilar songs:")
    for t in similar_tracks:
        print(f"- {t['name']} by {t['artist']['name']}")

# Example usage
get_similar_songs_from_input("Shape of You")