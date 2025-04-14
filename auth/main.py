from fastapi import FastAPI, Request, Depends
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from datetime import datetime
import os
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from google.cloud import firestore
import uuid

load_dotenv()

# ---------- CONFIGURATION ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY")
BUCKET_NAME = os.getenv("PROJECT_NAME")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5002")

# ---------- FASTAPI SETUP ----------
app = FastAPI()

# Add static files and templates directories
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")  # Set the directory for templates

# ---------- FIRESTORE CLIENT ----------
db = firestore.Client(project=BUCKET_NAME)

# ---------- OAUTH CONFIG ----------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    authorize_params={"access_type": "offline", "prompt": "consent"},
    client_kwargs={"scope": "openid email profile"},
)

# ---------- HOME ROUTE ----------
@app.get("/")
async def home(request: Request):
    print("[INFO] Home page accessed")
    return templates.TemplateResponse("home.html", {"request": request})

# ---------- LOGIN ----------
@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    print(f"[INFO] Initiating login. Redirect URI: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    print("[INFO] OAuth callback triggered")

    token = await oauth.google.authorize_access_token(request)
    print("[INFO] Access token received:", token)

    user_info = None
    if "id_token" in token:
        try:
            user_info = await oauth.google.parse_id_token(request, token)
            print("[INFO] Parsed ID token successfully")
        except Exception as e:
            print(f"[WARNING] parse_id_token failed: {e}")
    else:
        print("[WARNING] No id_token found in token")

    if not user_info:
        try:
            # Explicit URL to avoid protocol error
            resp = await oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
            user_info = resp.json()
            print("[INFO] Userinfo fetched via fallback:", user_info)
        except Exception as e:
            print(f"[ERROR] Failed to fetch user info: {e}")
            return {"error": "Authentication failed"}

    if not user_info:
        return {"error": "Authentication failed"}

    user_email = user_info.get("email")
    user_name = user_info.get("name", "Unknown")
    user_picture = user_info.get("picture", "")

    print(f"[INFO] Authenticated user: {user_email}, Name: {user_name}")

    user_doc = db.collection("users").document(user_email)
    user_snapshot = user_doc.get()

    if not user_snapshot.exists:
        print("[INFO] New user. Creating Firestore document.")
        user_doc.set({
            "email": user_email,
            "name": user_name,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "downloaded_songs": []
        })
    else:
        print("[INFO] Existing user. Updating name.")
        user_doc.update({"name": user_name})

    request.session["user"] = {"email": user_email, "name": user_name, "picture": user_picture}
    print("[INFO] Session updated")

    return RedirectResponse(f"{FRONTEND_URL}/set_user?name={user_name}&email={user_email}&picture={user_picture}")


# ---------- LOGOUT ----------
@app.get("/logout")
async def logout(request: Request):
    print(f"[INFO] User logged out: {request.session.get('user', {}).get('email', 'Unknown')}")
    request.session.clear()
    return RedirectResponse(url=f"http://{FRONTEND_URL}/")

# ---------- FIRESTORE TEST ----------
@app.get("/firestore-test")
async def firestore_test():
    db.collection("test").document("check").set({"msg": "Hello from FastAPI!"})
    return {"status": "Success"}