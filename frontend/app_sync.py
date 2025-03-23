from flask import Flask, render_template, send_from_directory
import json

app = Flask(__name__)

@app.route('/')
def index():
    with open("lyrics1.json", "r") as f:
        words = json.load(f)
    return render_template("index_sync.html", words=words)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)