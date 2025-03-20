from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

GENIUS_API_KEY = "<Enter-your-api-key>"
GENIUS_SEARCH_URL = "https://api.genius.com/search"

def get_genius_lyrics(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Failed to retrieve the webpage")
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    # Find all divs that contain lyrics
    lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
    if not lyrics_divs:
        print("Lyrics container not found")
        return None
    lyrics = []
    for div in lyrics_divs:
        # Extract text from normal text and <a> tags
        for elem in div.children:
            if elem.name == "a":  # Extract text from links
                lyrics.append(elem.get_text(separator="\n"))
            elif elem.name is None:  # Extract plain text
                lyrics.append(elem.strip())
    return "\n".join(lyrics)

def get_song_titles(query):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    params = {"q": query}
    response = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params)
    data = response.json()
    song_titles = []
    if "response" in data and "hits" in data["response"]:
        for hit in data["response"]["hits"]:
            title = hit["result"]["title"]
            url = hit["result"]["url"]
            song_titles.append({"title": title, "url": url})
    return song_titles

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    song_titles = get_song_titles(query)
    return jsonify(song_titles)

@app.route('/lyrics', methods=['GET'])
def lyrics():
    song_url = request.args.get('url', '')
    if not song_url:
        return jsonify({'lyrics': 'No URL provided.'})
    song_lyrics = get_genius_lyrics(song_url)
    if not song_lyrics:
        return jsonify({'lyrics': 'Lyrics not found.'})
    return jsonify({'lyrics': song_lyrics})

if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
