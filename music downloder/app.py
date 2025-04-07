from flask import Flask, request, render_template, redirect, url_for
import os
import uuid
import yt_dlp

app = Flask(__name__)

# Path where songs will be downloaded
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get data from the form
        song_name = request.form["song_name"]
        artist_name = request.form["artist_name"]
        song_uuid = request.form["song_uuid"]
        
        # Call the function to download the song
        download_path = download_song(song_name, artist_name, song_uuid)
        
        # Redirect to a new route to show download status
        return render_template("download_status.html", song_name=song_name, download_path=download_path)
    
    return render_template("index.html")

def download_song(song_name, artist_name, song_uuid):
    # Construct the YouTube search query
    query = f"{song_name} {artist_name}"
    download_path = os.path.join(DOWNLOAD_FOLDER, f"{song_uuid}.mp3")

    # Use yt-dlp to download the song from YouTube
    ydl_opts = {
        'outtmpl': download_path,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',  
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_url = f"ytsearch:{query}"
        ydl.download([search_url])

    return download_path


@app.route("/download-status")
def download_status():
    return render_template("download_status.html")

if __name__ == "__main__":
    app.run(debug=True)
