import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime


class TestEventTrackerCallback(unittest.TestCase):
    def setUp(self):
        self.mock_ch = MagicMock()
        self.mock_method = MagicMock()
        self.mock_method.delivery_tag = 'tag123'

    @patch("event_tracker.handle_frontend_update")
    def test_frontend_callback_success(self, mock_handler):
        from event_tracker import callback
        message = {
            "source": "frontend",
            "job_id": "job123",
            "song_id": "song456",
            "timestamp": datetime.utcnow().isoformat()
        }

        callback(self.mock_ch, self.mock_method, None, json.dumps(message).encode())
        mock_handler.assert_called_once_with(message)
        self.mock_ch.basic_ack.assert_called_once_with(delivery_tag='tag123')

    @patch("event_tracker.handle_job_update")
    def test_downloader_callback_success(self, mock_handler):
        from event_tracker import callback
        message = {
            "source": "downloader",
            "job_id": "job1",
            "song_id": "song2",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "Completed"
        }

        callback(self.mock_ch, self.mock_method, None, json.dumps(message).encode())
        mock_handler.assert_called_once_with(message)
        self.mock_ch.basic_ack.assert_called_once()

    @patch("event_tracker.handle_user_history_update")
    def test_history_callback_success(self, mock_handler):
        from event_tracker import callback
        message = {
            "source": "history",
            "user_email": "user@example.com",
            "song_id": "song1",
            "timestamp": datetime.utcnow().isoformat()
        }

        callback(self.mock_ch, self.mock_method, None, json.dumps(message).encode())
        mock_handler.assert_called_once_with(message)
        self.mock_ch.basic_ack.assert_called_once()

    def test_invalid_source_raises_nack(self):
        from event_tracker import callback
        message = {
            "source": "alien_service",
            "job_id": "jobx",
            "song_id": "songy",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "Completed"
        }

        callback(self.mock_ch, self.mock_method, None, json.dumps(message).encode())
        self.mock_ch.basic_nack.assert_called_once_with(delivery_tag='tag123', requeue=False)

    def test_missing_source_field_raises_nack(self):
        from event_tracker import callback
        message = {
            "job_id": "job1",
            "song_id": "song2",
            "timestamp": datetime.utcnow().isoformat()
        }

        callback(self.mock_ch, self.mock_method, None, json.dumps(message).encode())
        self.mock_ch.basic_nack.assert_called_once_with(delivery_tag='tag123', requeue=False)

    def test_malformed_json_raises_nack(self):
        from event_tracker import callback
        bad_data = b"{not a valid json"

        callback(self.mock_ch, self.mock_method, None, bad_data)
        self.mock_ch.basic_nack.assert_called_once_with(delivery_tag='tag123', requeue=False)


if __name__ == "__main__":
    unittest.main()
