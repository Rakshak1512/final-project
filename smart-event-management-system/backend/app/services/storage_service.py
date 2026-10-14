"""
Firebase Cloud Storage service for persistent file storage.
Stores and retrieves certificates and media assets across server restarts.
"""
import logging
import os
from typing import Optional

from firebase_admin import storage

from app.core.config import settings
from app.core.firebase import init_firebase

logger = logging.getLogger("app.storage")


def get_storage_bucket():
    """Retrieve Firebase Storage bucket instance using existing Firebase Admin SDK initialization."""
    try:
        init_firebase()
        bucket_name = getattr(settings, "FIREBASE_STORAGE_BUCKET", None) or ""

        # Option 1: Specified bucket name
        if bucket_name:
            try:
                return storage.bucket(bucket_name)
            except Exception as e:
                logger.warning("Could not open explicit bucket '%s': %s", bucket_name, e)

        # Option 2: Default Firebase Storage project bucket (.firebasestorage.app)
        if settings.FIREBASE_PROJECT_ID:
            try:
                return storage.bucket(f"{settings.FIREBASE_PROJECT_ID}.firebasestorage.app")
            except Exception:
                pass

        # Option 3: Appspot default bucket (.appspot.com)
        if settings.FIREBASE_PROJECT_ID:
            try:
                return storage.bucket(f"{settings.FIREBASE_PROJECT_ID}.appspot.com")
            except Exception:
                pass

        # Option 4: Default bucket from initialized app
        return storage.bucket()
    except Exception as e:
        logger.warning("Firebase Storage bucket initialization note: %s", e)
        return None


import uuid
from urllib.parse import quote, unquote

def upload_to_firebase_storage(
    file_bytes: bytes,
    destination_blob_name: str,
    content_type: str = "application/pdf",
) -> tuple[bool, Optional[str]]:
    """
    Upload byte content to Firebase Cloud Storage.
    Returns (success: bool, download_url: Optional[str]).
    """
    try:
        bucket = get_storage_bucket()
        if not bucket:
            return False, None

        # Clean blob name
        clean_name = destination_blob_name.replace("\\", "/").lstrip("/")
        blob = bucket.blob(clean_name)

        # Generate a standard Firebase download token
        token = str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": token}

        blob.upload_from_string(file_bytes, content_type=content_type)
        logger.info("Persisted '%s' to Firebase Cloud Storage", clean_name)

        encoded_name = quote(clean_name, safe="")
        public_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{encoded_name}?alt=media&token={token}"
        return True, public_url
    except Exception as e:
        logger.warning("Could not persist '%s' to Firebase Storage: %s", destination_blob_name, e)
        return False, None


def download_from_firebase_storage(blob_name: str) -> Optional[bytes]:
    """Download byte content from Firebase Cloud Storage."""
    try:
        bucket = get_storage_bucket()
        if not bucket:
            return None

        clean_name = blob_name.replace("\\", "/").lstrip("/")
        # Check standard name
        blob = bucket.blob(clean_name)
        if blob.exists():
            return blob.download_as_bytes()

        # Check alternative name without 'uploads/' prefix if present
        if clean_name.startswith("uploads/"):
            alt_name = clean_name[len("uploads/") :]
            alt_blob = bucket.blob(alt_name)
            if alt_blob.exists():
                return alt_blob.download_as_bytes()
        else:
            # Try with 'uploads/' prefix
            alt_name = f"uploads/{clean_name}"
            alt_blob = bucket.blob(alt_name)
            if alt_blob.exists():
                return alt_blob.download_as_bytes()

        return None
    except Exception as e:
        logger.warning("Could not download '%s' from Firebase Storage: %s", blob_name, e)
        return None


def delete_from_firebase_storage(blob_name: str) -> bool:
    """Delete a blob from Firebase Cloud Storage."""
    try:
        bucket = get_storage_bucket()
        if not bucket:
            return False

        clean_name = blob_name.replace("\\", "/").lstrip("/")
        blob = bucket.blob(clean_name)
        if blob.exists():
            blob.delete()
            return True

        if clean_name.startswith("uploads/"):
            alt_blob = bucket.blob(clean_name[len("uploads/") :])
            if alt_blob.exists():
                alt_blob.delete()
                return True

        return False
    except Exception as e:
        logger.warning("Could not delete '%s' from Firebase Storage: %s", blob_name, e)
        return False


def get_or_restore_file(relative_or_abs_path: str) -> Optional[bytes]:
    """
    Check if the file exists on local disk.
    If missing (e.g. after container restart), try downloading from Firebase Cloud Storage
    and restoring to local cache.
    Returns file bytes or None if not found anywhere.
    """
    if not relative_or_abs_path:
        return None

    clean = relative_or_abs_path.replace("\\", "/")
    if clean.startswith("uploads/"):
        sub_path = clean[len("uploads/") :]
    else:
        sub_path = clean

    local_path = (
        relative_or_abs_path
        if os.path.isabs(relative_or_abs_path)
        else os.path.join(settings.upload_dir_abs, sub_path)
    )

    # 1. If exists on local disk, read and return
    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as f:
                return f.read()
        except Exception:
            pass

    # 2. Try fetching from Firebase Cloud Storage
    cloud_bytes = download_from_firebase_storage(clean)
    if cloud_bytes:
        # Cache locally for subsequent fast access
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(cloud_bytes)
        except Exception:
            pass
        return cloud_bytes

    return None
