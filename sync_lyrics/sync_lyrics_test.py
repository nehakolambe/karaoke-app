import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json
import tempfile
import shutil

from sync_lyrics import (
    build_azlyrics_url,
    align_lyrics,
    callback
)

class TestLyricsSyncer(unittest.TestCase):

    def test_build_azlyrics_url_cleaning(self):
        url = build_azlyrics_url("Drake ft. Travis Scott", "SICKO Mode")
        self.assertEqual(url, "https://www.azlyrics.com/lyrics/drake/sickomode.html")

    @patch("lyrics_syncer.gcs_utils")
    @patch("lyrics_syncer.ForceAlign")
    def test_align_lyrics_happy_path(self, MockForceAlign, mock_gcs):
        # Setup
        song_id = "abc123"
        temp_dir = tempfile.mkdtemp()
        download_path = os.path.join(temp_dir, song_id)
        os.makedirs(download_path, exist_ok=True)

        mock_gcs.get_artifact_url.side_effect = lambda sid, f: os.path.join(download_path, f)
        mock_gcs.gcs_file_exists.return_value = False
        mock_gcs.download_file_from_gcs = MagicMock()
        mock_gcs.upload_file_to_gcs = MagicMock()

        lyrics_txt = os.path.join(download_path, "lyrics.txt")
        vocals_wav = os.path.join(download_path, "vocals.wav")

        with open(lyrics_txt, "w") as f:
            f.write("hello world\nhow are you")

        with open(vocals_wav, "wb") as f:
            f.write(b"fake_wav_data")

        mock_aligned = [
            MagicMock(time_start=0.5, time_end=1.0),
            MagicMock(time_start=1.0, time_end=1.5),
            MagicMock(time_start=2.0, time_end=2.5),
            MagicMock(time_start=2.5, time_end=3.0),
            MagicMock(time_start=3.0, time_end=3.5)
        ]
        MockForceAlign.return_value.inference.return_value = mock_aligned

        with patch("lyrics_syncer.os.path.exists", return_value=True), \
             patch("lyrics_syncer.os.listdir", return_value=["lyrics.txt", "vocals.wav"]), \
             patch("lyrics_syncer.os.remove"), \
             patch("lyrics_syncer.os.rmdir"):

            align_lyrics(song_id)

        output_path = os.path.join(download_path, "lyrics.json")
        self.assertTrue(os.path.exists(output_path) or mock_gcs.upload_file_to_gcs.called)

        shutil.rmtree(temp_dir)

    @patch("lyrics_syncer.gcs_utils")
    @patch("lyrics_syncer.notify_event_tracker")
    def test_callback_missing_lyrics_txt(self, mock_notify, mock_gcs):
        ch = MagicMock()
        method = MagicMock()
        method.delivery_tag = "xyz"
        body = json.dumps({
            "job_id": "job123",
            "song_id": "song123",
            "song_name": "Hello",
            "artist_name": "Adele"
        })

        mock_gcs.get_artifact_url.return_value = "/mock/lyrics.txt"
        mock_gcs.gcs_file_exists.return_value = False

        callback(ch, method, None, body)

        mock_notify.assert_called_once()
        ch.basic_nack.assert_called_once_with(delivery_tag="xyz", requeue=False)

    @patch("lyrics_syncer.notify_event_tracker")
    def test_callback_malformed_json(self, mock_notify):
        ch = MagicMock()
        method = MagicMock()
        method.delivery_tag = "malformed"
        bad_body = "NOT JSON"

        callback(ch, method, None, bad_body)
        mock_notify.assert_called_once()
        ch.basic_nack.assert_called_once_with(delivery_tag="malformed", requeue=False)

if __name__ == "__main__":
    unittest.main()
