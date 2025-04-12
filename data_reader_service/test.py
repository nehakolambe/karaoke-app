import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_get_job_status(client):
    # Use an existing job ID from your Firestore for testing
    response = client.get('/job-history/001')
    assert response.status_code == 200  # Expecting a 200 if the job exists

def test_job_not_found(client):
    # Use a non-existing job ID from your Firestore for testing
    response = client.get('/job-history/1209abc')
    assert response.status_code == 404  # Expecting 404 since the job doesn't exist

def test_get_user_data(client):
    # Use an existing user ID from your Firestore for testing
    response = client.get('/users/srushtisangawar@gmail.com')
    assert response.status_code == 200  # Expecting a 200 if the user exists

def test_user_not_found(client):
    # Use a non-existing user ID from your Firestore for testing
    response = client.get('/users/non_existing_user_id')
    assert response.status_code == 404  # Expecting 404 since the user doesn't exist
