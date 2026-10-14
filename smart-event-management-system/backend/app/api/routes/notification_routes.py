from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import firestore_service as db_service
from app.dependencies import get_current_user
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.notification_schema import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    search: Optional[str] = Query(None),
    type: Optional[NotificationType] = Query(None),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    return db_service.list_notifications(
        user_id=current_user.id,
        search=search,
        type=type,
        unread_only=unread_only,
    )


@router.get("/unread-count")
def unread_count(current_user: User = Depends(get_current_user)):
    count = db_service.get_unread_notification_count(current_user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read", response_model=NotificationOut)
def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
):
    notification = db_service.mark_notification_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.put("/mark-all-read")
def mark_all_read(current_user: User = Depends(get_current_user)):
    db_service.mark_all_notifications_read(current_user.id)
    return {"message": "All notifications marked as read"}

