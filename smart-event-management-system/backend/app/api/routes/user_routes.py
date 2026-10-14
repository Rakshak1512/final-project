from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.security import hash_password, verify_password
from app.db import firestore_service as db_service
from app.dependencies import get_current_approved_user, get_current_user
from app.models.user import User
from app.schemas.user_schema import (
    ChangePassword,
    EmailUpdateRequest,
    NotificationPreferencesUpdate,
    UserOut,
    UserUpdate,
)
from app.utils.file_utils import delete_file_if_exists, save_upload

router = APIRouter(prefix="/api/users", tags=["User Profile"])


@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Retrieve currently authenticated user profile including live approval status."""
    return current_user


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_approved_user),
):
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.department is not None:
        updates["department"] = payload.department
    if payload.semester is not None:
        updates["semester"] = payload.semester

    updated_user = db_service.update_user(current_user.id, updates)
    return updated_user or current_user


@router.post("/profile/picture", response_model=UserOut)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_approved_user),
):
    new_path = await save_upload(file, "profile_pictures")
    old_path = current_user.profile_picture

    updated_user = db_service.update_user(current_user.id, {"profile_picture": new_path})

    if old_path:
        delete_file_if_exists(old_path)

    return updated_user or current_user


@router.put("/email", response_model=UserOut)
def update_email(
    payload: EmailUpdateRequest,
    current_user: User = Depends(get_current_approved_user),
):
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    existing = db_service.get_user_by_email(payload.new_email)
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")

    updated_user = db_service.update_user(
        current_user.id,
        {"email": payload.new_email.strip().lower(), "is_email_verified": False},
    )
    return updated_user or current_user


@router.put("/password")
def change_password(
    payload: ChangePassword,
    current_user: User = Depends(get_current_approved_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    db_service.update_user(
        current_user.id,
        {"hashed_password": hash_password(payload.new_password)},
    )
    return {"message": "Password updated successfully"}


@router.put("/notification-preferences", response_model=UserOut)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update in-app and email notification preferences."""
    current_prefs = current_user.notification_preferences or {"in_app": True, "email": True}
    updated_prefs = {
        "in_app": payload.get_in_app(current_prefs.get("in_app", True)),
        "email": payload.get_email(current_prefs.get("email", True)),
    }
    updated_user = db_service.update_user(
        current_user.id,
        {"notification_preferences": updated_prefs},
    )
    return updated_user or current_user


@router.delete("/me", status_code=status.HTTP_200_OK)
def delete_account(
    current_user: User = Depends(get_current_user),
):
    """
    Deactivates (soft-deletes) the current user's account, preserving historical
    registrations, certificates, events, and audit logs.
    """
    success = db_service.deactivate_user(current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

    # If Firebase Auth is used, attempt cleanup of Firebase Auth record
    try:
        from firebase_admin import auth as fb_auth
        fb_user = fb_auth.get_user_by_email(current_user.email)
        if fb_user:
            fb_auth.delete_user(fb_user.uid)
    except Exception:
        pass

    try:
        db_service.create_audit_log(
            user_id=current_user.id,
            action="account_deleted",
            entity_type="user",
            entity_id=current_user.id,
            details="User requested account deactivation/deletion.",
        )
    except Exception:
        pass

    return {"message": "Account successfully deactivated and deleted."}

