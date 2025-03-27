import requests

API_KEY = "<your-api-key>"

def get_artist_from_song_name(song_name):
    search_url = "http://ws.audioscrobbler.com/2.0/"
    search_params = {
        'method': 'track.search',
        'track': song_name,
        'api_key': API_KEY,
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

def get_similar_songs(song_name):
    artist, track = get_artist_from_song_name(song_name)
    
    if not artist or not track:
        print("Could not find artist for the song.")
        return

    print(f"Top match: {track} by {artist}")

    similar_url = "http://ws.audioscrobbler.com/2.0/"
    similar_params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': track,
        'api_key': API_KEY,
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
get_similar_songs("Duniya")