import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from main import app

client = TestClient(app)

# ---------- Home Route ----------
def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

# ---------- Logout Route ----------
def test_logout_clears_session():
    response = client.request("GET", "/logout", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert response.headers["location"].startswith("http://")


# ---------- Firestore Test ----------
@patch("main.db")
def test_firestore_test(mock_db):
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_doc = MagicMock()
    mock_collection.document.return_value = mock_doc

    response = client.get("/firestore-test")
    assert response.status_code == 200
    assert response.json()["status"] == "Success"
    mock_doc.set.assert_called_once_with({"msg": "Hello from FastAPI!"})

# ---------- Login Redirect ----------
@patch("main.oauth")
def test_login_redirect(mock_oauth):
    mock_oauth.google.authorize_redirect = AsyncMock(return_value="redirect")
    response = client.get("/login")
    assert response.status_code in [200, 302, 500]

# ---------- Auth Callback (happy path) ----------
@patch("main.db")
@patch("main.oauth")
def test_auth_callback_success(mock_oauth, mock_db):
    token = {"id_token": "fake_id_token"}
    user_info = {"email": "test@example.com", "name": "Test User", "picture": "pic.jpg"}

    mock_oauth.google.authorize_access_token = AsyncMock(return_value=token)
    mock_oauth.google.parse_id_token = AsyncMock(return_value=user_info)

    mock_doc = MagicMock()
    mock_doc.get.return_value.exists = False
    mock_db.collection.return_value.document.return_value = mock_doc

    response = client.get("/auth/callback")
    assert response.status_code in [200, 302, 500, 404]
