from fastapi import FastAPI, Depends, Request
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
import os

# Load environment variables (replace with your credentials)
GOOGLE_CLIENT_ID = "your-google-client-id"
GOOGLE_CLIENT_SECRET = "your-google-client-secret"
SECRET_KEY = "random_secret_key"

# Initialize FastAPI app
app = FastAPI()

# Add session middleware to the app
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Initialize OAuth client
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={"scope": "openid email profile"},
    access_token_url="https://oauth2.googleapis.com/token",
    access_token_params=None,
    refresh_token_url=None,
    client_kwargs={"scope": "openid email profile"},
)

@app.get("/")
async def home():
    return """
    <html>
        <body>
            <h1>Welcome to the Karaoke App!</h1>
            <a href="/login">Login with Google</a>
        </body>
    </html>
    """

@app.get("/login")
async def login(request: Request):
    """Redirects user to Google's OAuth login page."""
    # Ensure the redirect URI matches what is configured in Google Cloud Console
    redirect_uri = request.url_for("auth_callback")  # http://127.0.0.1:8000/auth/callback
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handles the OAuth callback from Google and retrieves user info."""
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    
    if not user:
        return {"error": "Authentication failed"}
    
    # After successful login, redirect to the frontend app (`app.py`)
    # Assuming frontend app is served at http://localhost:8000/frontend/app.py
    return RedirectResponse(url="http://localhost:8000/frontend/app.py")

@app.get("/logout")
async def logout(request: Request):
    """Clears the session to log out the user."""
    request.session.clear()
    return RedirectResponse(url="/")
