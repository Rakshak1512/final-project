"""
Secure file upload handling.

- Validates file extension against an allow-list per upload category
- Validates file size against MAX_UPLOAD_SIZE_MB
- Generates a random filename (never trusts the client-supplied filename)
  to prevent path traversal and overwrite attacks.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.storage_service import (
    delete_from_firebase_storage,
    upload_to_firebase_storage,
)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf"}

CATEGORY_FOLDERS = {
    "profile_pictures": ALLOWED_IMAGE_EXTENSIONS,
    "event_posters": ALLOWED_IMAGE_EXTENSIONS,
    "certificates": ALLOWED_DOCUMENT_EXTENSIONS,
}


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


async def save_upload(file: UploadFile, category: str) -> str:
    if category not in CATEGORY_FOLDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload category")

    allowed_extensions = CATEGORY_FOLDERS[category]
    ext = _get_extension(file.filename or "")
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    folder = os.path.join(settings.upload_dir_abs, category)
    os.makedirs(folder, exist_ok=True)

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, safe_filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    rel_path = os.path.join("uploads", category, safe_filename).replace("\\", "/")

    # Also persist to Firebase Cloud Storage if configured
    content_type = file.content_type or ("application/pdf" if ext == ".pdf" else "application/octet-stream")
    success, cloud_url = upload_to_firebase_storage(contents, rel_path, content_type=content_type)
    if success and cloud_url:
        return cloud_url

    return rel_path


def delete_file_if_exists(path: str) -> None:
    if not path:
        return

    # If it is a Firebase Cloud Storage URL, parse and delete from bucket
    if "firebasestorage.googleapis.com" in path:
        try:
            from urllib.parse import unquote
            if "/o/" in path:
                blob_name = unquote(path.split("/o/")[1].split("?")[0])
                delete_from_firebase_storage(blob_name)
        except Exception:
            pass
        return

    clean = path.replace("\\", "/")
    if clean.startswith("uploads/"):
        clean_sub = clean[len("uploads/") :]
    else:
        clean_sub = clean
    full_path = os.path.join(settings.upload_dir_abs, clean_sub) if not os.path.isabs(path) else path
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass
    delete_from_firebase_storage(clean)

