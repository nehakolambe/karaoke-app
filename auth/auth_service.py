from flask import Flask, redirect, url_for, session, request, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import os
import requests

# Load client secrets JSON file (download from Google Developer Console)
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/userinfo.email", 
          "https://www.googleapis.com/auth/userinfo.profile", 
          "openid"]
REDIRECT_URI = "http://localhost:5000/callback"

app = Flask(__name__)
app.secret_key = "abcd"  # Change this to a secure key

# Configure OAuth 2.0 flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI,
)

@app.route("/login")
def login():
    """Redirect user to Google's OAuth 2.0 server."""
    auth_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state
    return redirect(auth_url)

@app.route("/callback")
def callback():
    """Handle the response from Google's OAuth 2.0 server."""
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)
    return redirect(url_for("profile"))

@app.route("/profile")
def profile():
    """Fetch user info from Google."""
    if "credentials" not in session:
        return redirect(url_for("login"))

    credentials = Credentials(**session["credentials"])
    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {credentials.token}"}
    user_info = requests.get(user_info_url, headers=headers).json()

    return jsonify(user_info)

def credentials_to_dict(credentials):
    """Convert credentials object to a dictionary."""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

if __name__ == "__main__":
    app.run(debug=True)
