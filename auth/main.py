from fastapi import FastAPI, Request, Depends
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from datetime import datetime
import os
from fastapi.staticfiles import StaticFiles

# Firestore setup
from google.cloud import firestore

# ---------- 🔐 CONFIGURATION ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "bb")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "cc")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")

# ---------- 🏗️ FASTAPI SETUP ----------
app = FastAPI()

# Add static files and templates directories
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")  # Set the directory for templates

# ---------- 🌐 OAUTH SETUP ----------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={"scope": "openid email"},
    access_token_url="https://oauth2.googleapis.com/token",
    client_kwargs={"scope": "openid email"},
)

# ---------- 🔥 FIRESTORE CLIENT ----------
db = firestore.Client(project="music-separation-assignment")

# ---------- 🏠 HOME ROUTE ----------
@app.get("/")
async def home(request: Request):
    print("[INFO] Home page accessed")
    return templates.TemplateResponse("home.html", {"request": request})

# ---------- 🔑 LOGIN ROUTE ----------
@app.get("/login")
async def login(request: Request):
    redirect_uri = "https://srurora.github.io/srushti/"
    print(f"[INFO] Initiating login. Redirect URI: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)

# ---------- 🎯 CALLBACK ROUTE ----------
@app.get("/auth/callback")
async def auth_callback(request: Request):
    print("[INFO] OAuth callback triggered")

    token = await oauth.google.authorize_access_token(request)
    print("[INFO] Access token received")

    user_info = await oauth.google.parse_id_token(request, token)
    print(f"[INFO] User info parsed: {user_info}")

    if not user_info:
        print("[ERROR] Authentication failed")
        return {"error": "Authentication failed"}

    user_email = user_info["email"]
    user_name = user_info.get("name", "Unknown")
    user_picture = user_info.get("picture", "")

    print(f"[INFO] Authenticated user: {user_email}, Name: {user_name}")

    user_doc = db.collection("users").document(user_email)
    user_snapshot = user_doc.get()

    if not user_snapshot.exists:
        print("[INFO] New user. Creating Firestore document.")
        user_doc.set({
            "user_id": f"user_{user_email.split('@')[0]}",
            "email": user_email,
            "name": user_name,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "downloaded_songs": []
        })
    else:
        print("[INFO] Existing user. Updating name.")
        user_doc.update({
            "name": user_name
        })

    request.session["user"] = {"email": user_email, "name": user_name}
    print("[INFO] Session updated")

    print("[INFO] Redirecting to frontend app")
    return RedirectResponse(url="http://localhost:8000/frontend/")

# ---------- 🚪 LOGOUT ROUTE ----------
@app.get("/logout")
async def logout(request: Request):
    print(f"[INFO] User logged out: {request.session.get('user', {}).get('email', 'Unknown')}")
    request.session.clear()
    return RedirectResponse(url="/")
