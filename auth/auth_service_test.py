import pytest
from auth_service import app  # Assuming your Flask app is in auth_service.py
import os

# Disable the security check for HTTPS
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

@pytest.fixture
def client():
    """Set up a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_google_login_redirect(client):
    """Test if Google login redirects properly."""
    response = client.get("/login")  # This will initiate the OAuth flow
    assert response.status_code == 302  # 302 indicates a redirect
    assert "https://accounts.google.com/o/oauth2/auth" in response.location

    # After login, check the session to ensure the state is set
    with client.session_transaction() as session:
        assert 'state' in session, "State is not set in session after login"
        state = session['state']
        assert state is not None, "State should not be None after login"

def test_google_callback(client, requests_mock):
    """Mock Google's OAuth response and test callback handling."""
    mock_token_url = "https://oauth2.googleapis.com/token"
    mock_userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"

    # Mock Google token response
    requests_mock.post(mock_token_url, json={"access_token": "mock_access_token", "expires_in": 3600})
    
    # Mock Google user info response
    requests_mock.get(mock_userinfo_url, json={"email": "testuser@gmail.com", "name": "Test User"})

    # Trigger the login route first to initiate the OAuth flow and generate state
    response = client.get("/login")
    assert response.status_code == 302  # It should redirect to Google's OAuth server

    # After login, check the session to ensure the state is set
    with client.session_transaction() as session:
        state = session.get('state')
        assert state is not None, "State is not present in session after login"

    # Perform the callback request with the correct state and mock authorization code
    response = client.get(f"/callback?state={state}&code=mock_code")  # Use the state from the session
    
    # Verify that the session state is still correct after the callback
    with client.session_transaction() as session:
        assert session.get("state") == state, "Session state mismatch after callback"

    # Assert that the response is a redirect to the profile page (302)
    assert response.status_code == 302, "Callback should redirect to profile"

    # Follow the redirect and check the profile page response
    response = client.get(response.location)
    assert response.status_code == 200, "Profile page should return a 200 status code"
    
    # Ensure that user information (e.g., Test User) is in the response data
    assert b"Test User" in response.data

if __name__ == "__main__":
    pytest.main()
