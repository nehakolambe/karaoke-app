import os
import logging
from flask import Flask, jsonify, request
from google.cloud import firestore
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firestore
if os.getenv("FIRESTORE_EMULATOR_HOST"):
    firestore_client = firestore.Client(project="bda-karaoke-app")
else:
    firestore_client = firestore.Client()

@app.route('/job-history/<job_id>', methods=['GET'])
def job_history(job_id):
    try:
        job_ref = firestore_client.collection('job_history').document(job_id)
        job = job_ref.get()

        if job.exists:
            job_data = job.to_dict()
            statuses = [
                job_data.get('lyrics_status'),
                job_data.get('download_status'),
                job_data.get('vocals_status')
            ]

            if all(s == "Completed" for s in statuses):
                overall_status = "complete"
            elif any(s == "Failed" for s in statuses):
                overall_status = "failed"
            else:
                overall_status = "inProcess"

            return jsonify({
                "job_id": job_id,
                "status": overall_status,
                "timestamp": job_data.get('timestamp')
            })
        else:
            return jsonify({"error": "Job history not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching job history: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user_ref = firestore_client.collection('users').document(user_id)
        user = user_ref.get()

        if user.exists:
            user_data = user.to_dict()
            return jsonify({
                "user_id": user_id,
                "name": user_data.get('name'),
                "email": user_data.get('email'),
                "last_login": user_data.get('last_login')
            })
        else:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5002)
