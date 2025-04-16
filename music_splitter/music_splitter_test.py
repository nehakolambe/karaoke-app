import unittest
from unittest.mock import MagicMock, patch, call
import tempfile
import os
import shutil

from music_splitter import (
    upload_file_safe,
    split_and_upload_instrumental,
    handle_message
)

class TestSplitterService(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.job_id = "test-job"
        self.song_id = "test-song"
        self.audio_loader = MagicMock()
        self.separator = MagicMock()
        self.gcs_utils = MagicMock()

        self.gcs_utils.get_instrumental_url.return_value = os.path.join(self.test_dir, "instrumental.wav")
        self.gcs_utils.get_vocals_url.return_value = os.path.join(self.test_dir, "vocal.wav")
        self.gcs_utils.get_artifact_url.return_value = os.path.join(self.test_dir, "original.wav")
        self.gcs_utils.gcs_file_exists.return_value = False

        # create dummy original.wav
        with open(self.gcs_utils.get_artifact_url.return_value, 'w') as f:
            f.write("")

        self.audio_loader.load.return_value = ("dummy_waveform", 44100)
        self.separator.separate.return_value = {
            "accompaniment": "accomp_data",
            "vocals": "vocal_data"
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_upload_file_safe_success(self):
        errors = {}
        self.gcs_utils.upload_file_to_gcs = MagicMock()
        upload_file_safe("mock_url", "mock_path", "instrumental", errors, self.gcs_utils)
        self.assertEqual(errors, {})

    def test_upload_file_safe_failure(self):
        errors = {}
        self.gcs_utils.upload_file_to_gcs.side_effect = Exception("Upload failed")
        upload_file_safe("mock_url", "mock_path", "instrumental", errors, self.gcs_utils)
        self.assertIn("instrumental", errors)
        self.assertEqual(errors["instrumental"], "Upload failed")

    @patch("threading.Thread")
    def test_split_and_upload_instrumental_happy_path(self, mock_thread):
        mock_thread.return_value = MagicMock(start=lambda: None, join=lambda: None)
        self.audio_loader.save = MagicMock()
        self.gcs_utils.upload_file_to_gcs = MagicMock()

        split_and_upload_instrumental(
            self.job_id,
            self.song_id,
            self.audio_loader,
            self.separator,
            self.gcs_utils
        )

        self.audio_loader.load.assert_called_once()
        self.audio_loader.save.assert_any_call(os.path.join(self.test_dir, "instrumental.wav"), "accomp_data", sample_rate=44100)
        self.audio_loader.save.assert_any_call(os.path.join(self.test_dir, "vocal.wav"), "vocal_data", sample_rate=44100)

    def test_handle_message_success(self):
        ch = MagicMock()
        message = {
            "job_id": self.job_id,
            "song_id": self.song_id,
            "song_name": "Test Song",
            "artist_name": "Test Artist",
            "delivery_tag": "xyz"
        }

        with patch("splitter.split_and_upload_instrumental") as mock_split, \
             patch("splitter.notify_event_tracker") as mock_notify, \
             patch("splitter.publish_to_lyrics_syncer_queue") as mock_publish:
            handle_message(message, ch, self.audio_loader, self.separator, self.gcs_utils)

        ch.basic_ack.assert_called_once_with(delivery_tag="xyz")

    def test_handle_message_failure(self):
        ch = MagicMock()
        message = {
            "job_id": self.job_id,
            "song_id": self.song_id,
            "song_name": "Test Song",
            "artist_name": "Test Artist",
            "delivery_tag": "abc"
        }

        with patch("splitter.split_and_upload_instrumental", side_effect=Exception("Something went wrong")), \
             patch("splitter.notify_event_tracker") as mock_notify:
            handle_message(message, ch, self.audio_loader, self.separator, self.gcs_utils)

        ch.basic_nack.assert_called_once_with(delivery_tag="abc", requeue=False)

if __name__ == "__main__":
    unittest.main()
