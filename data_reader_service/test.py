import pytest
from unittest.mock import patch, MagicMock
from app import app  # Change to match your filename if not app.py

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# ----------------------------
# /job-history/<job_id> tests
# ----------------------------

@patch("app.firestore_client")
def test_job_history_complete(mock_firestore, client):
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "lyrics_status": "Completed",
        "vocals_status": "Completed",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

    res = client.get("/job-history/job123")
    assert res.status_code == 200
    assert res.json["status"] == "complete"

@patch("app.firestore_client")
def test_job_history_not_found(mock_firestore, client):
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

    res = client.get("/job-history/unknown")
    assert res.status_code == 404
    assert res.json["error"] == "Job history not found"

# ----------------------------
# /users/<user_email> tests
# ----------------------------

@patch("app.firestore_client")
def test_get_user_success(mock_firestore, client):
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "name": "Srushti",
        "email": "srushti@example.com",
        "downloaded_songs": ["song1", "song2"]
    }
    mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

    res = client.get("/users/srushti@example.com")
    assert res.status_code == 200
    assert res.json["name"] == "Srushti"

@patch("app.firestore_client")
def test_get_user_not_found(mock_firestore, client):
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

    res = client.get("/users/unknown@example.com")
    assert res.status_code == 404
    assert res.json["error"] == "User not found"
