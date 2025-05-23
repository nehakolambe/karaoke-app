from google.cloud import storage
from shared.constants import GCS_BUCKET_NAME
import time


# def upload_file_to_gcs(gcs_url: str, local_path: str):
def upload_file_to_gcs(gcs_url: str, local_path: str, timeout: int = 300, retries: int = 3):
    """
    Uploads a local file to the GCS location specified by a gs:// URL.
    """
    # assert gcs_url.startswith("gs://"), "GCS URL must start with 'gs://'"

    # path = gcs_url[5:]  # strip 'gs://'
    # bucket_name, *blob_parts = path.split("/")
    # blob_path = "/".join(blob_parts)

    # client = storage.Client()
    # bucket = client.bucket(bucket_name)
    # blob = bucket.blob(blob_path)

    # blob.upload_from_filename(local_path)
    # print(f"[GCS] Uploaded: {local_path} --> {gcs_url}")

    assert gcs_url.startswith("gs://"), "GCS URL must start with 'gs://'"

    path = gcs_url[5:]  # strip 'gs://'
    bucket_name, *blob_parts = path.split("/")
    blob_path = "/".join(blob_parts)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    for attempt in range(1, retries + 1):
        try:
            blob.upload_from_filename(local_path, timeout=timeout)
            print(f"[GCS] Uploaded: {local_path} --> {gcs_url}")
            return  # success
        except Exception as e:
            print(f"[GCS][Attempt {attempt}] Upload failed: {e}")
            if attempt == retries:
                print("[GCS] Final retry failed. Raising exception.")
                raise
            time.sleep(2 ** attempt)


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

def get_artifact_url(song_id: str, artifact: str) -> str:
    return f"gs://{GCS_BUCKET_NAME}/songs/{song_id}/{artifact}"


def get_instrumental_url(song_id: str) -> str:
    return get_artifact_url(song_id, "instrumental.wav")

def get_vocals_url(song_id: str) -> str:
    return get_artifact_url(song_id, "vocals.wav")