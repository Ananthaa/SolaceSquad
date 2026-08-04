"""GCS upload helpers for consultant CV and profile photo."""
import os
import uuid
from typing import Optional

GCS_BUCKET = os.getenv("GCS_BUCKET", "solacesquad-call-recordings")
CONSULTANT_UPLOADS_PREFIX = "consultant-uploads"


def _gcs_client():
    from google.cloud import storage
    return storage.Client()


def upload_to_gcs(file_bytes: bytes, filename: str, content_type: str, folder: str) -> Optional[str]:
    """Upload bytes to GCS and return the GCS object path (not a public URL).
    Photos are served via /api/profile-photo/{user_id} proxy endpoint (GCS bucket
    has uniform access enforced by org policy — direct public URLs are not possible).
    """
    try:
        client = _gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        unique_name = f"{CONSULTANT_UPLOADS_PREFIX}/{folder}/{uuid.uuid4().hex}.{ext}"
        blob = bucket.blob(unique_name)
        blob.upload_from_string(file_bytes, content_type=content_type)
        # Store the full GCS URL so it can be parsed by the proxy endpoint later.
        url = f"https://storage.googleapis.com/{GCS_BUCKET}/{unique_name}"
        print(f"[GCS] Uploaded {filename} → {url}")
        return url
    except Exception as e:
        import sys
        print(f"[GCS] Upload failed for {filename}: {e}", file=sys.stderr)
        return None


def upload_cv(file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Upload a CV/resume PDF and return its public URL."""
    return upload_to_gcs(file_bytes, original_filename, "application/pdf", "cv")


def upload_profile_photo(file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Upload a profile photo (JPEG/PNG/WEBP) and return its public URL."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    ct_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    content_type = ct_map.get(ext, "image/jpeg")
    return upload_to_gcs(file_bytes, original_filename, content_type, "photos")


def upload_demo_video(file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Upload an admin demo video (MP4/WEBM/MOV) to GCS and return its URL.
    The file is stored under 'demo-videos/' prefix in the recordings bucket.
    Access is proxied through the /api/demo-videos/{id}/stream backend endpoint.
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "mp4"
    ct_map = {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
    }
    content_type = ct_map.get(ext, "video/mp4")
    return upload_to_gcs(file_bytes, original_filename, content_type, "demo-videos")

