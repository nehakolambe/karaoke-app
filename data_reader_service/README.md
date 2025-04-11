# Karaoke App - Data Reader Service

A read-only service that interacts with Firestore to fetch job statuses and user data. This service serves API requests from the frontend and does not perform any writes.

## Features

- **Get Job Status**: Fetch job status (e.g., "download complete", "split complete").
- **Get User Data**: Retrieve user information for session/login purposes.

## Setup

### Service Account

Set up Firestore with a service account. Download the `service-account.json` file and set the environment variable to it:

export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

Install the required dependencies:

pip install -r requirements.txt

Start the Flask app:

python app.py

The app will be available at http://127.0.0.1:5002.

API Endpoints
GET /job-status/<job_id>: Fetch job status.

GET /user/<user_id>: Fetch user data.

curl --location 'http://127.0.0.1:5002/users/srushtisangawar@gmail.com'
curl --location 'http://localhost:5002/job-history/001'

Run tests with pytest:

pytest test.py