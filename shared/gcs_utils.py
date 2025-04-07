from google.cloud import storage
from constants import GCS_BUCKET_NAME

def upload_file_to_gcs(gcs_url: str, local_path: str):
    """
    Uploads a local file to the GCS location specified by a gs:// URL.
    """
    assert gcs_url.startswith("gs://"), "GCS URL must start with 'gs://'"

    path = gcs_url[5:]  # strip 'gs://'
    bucket_name, *blob_parts = path.split("/")
    blob_path = "/".join(blob_parts)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    blob.upload_from_filename(local_path)
    print(f"[GCS] Uploaded: {local_path} --> {gcs_url}")


def download_file_from_gcs(gcs_url: str, local_path: str):
    """
    Downloads a file from the given GCS URL to a local path.
    """
    assert gcs_url.startswith("gs://"), "GCS URL must start with 'gs://'"

    # Parse the GCS path
    path = gcs_url[5:]  # strip 'gs://'
    bucket_name, *blob_parts = path.split("/")
    blob_path = "/".join(blob_parts)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    if not blob.exists():
        raise FileNotFoundError(f"No such file in GCS: {gcs_url}")

    blob.download_to_filename(local_path)
    print(f"[GCS] Downloaded: {gcs_url} --> {local_path}")


def gcs_file_exists(gcs_url: str) -> bool:
    """Returns True if the given GCS file exists."""
    assert gcs_url.startswith("gs://"), "GCS URL must start with 'gs://'"
    path = gcs_url[5:]  # strip 'gs://'
    bucket_name, *blob_parts = path.split("/")
    blob_path = "/".join(blob_parts)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    return blob.exists()


def get_song_gcs_url(song_id: str, artifact: str) -> str:
    return f"gs://{GCS_BUCKET_NAME}/songs/{song_id}/{artifact}"


def get_instrumental_url(song_id: str) -> str:
    return get_song_gcs_url(song_id, "instrumental.wav")
