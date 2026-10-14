from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.db import firestore_service as db_service
from app.dependencies import require_role
from app.models.user import RoleEnum, User
from app.schemas.event_schema import (
    EventCapacityOut,
    EventEditHistoryOut,
    EventOut,
    PaginatedEvents,
)
from app.utils.file_utils import delete_file_if_exists, save_upload

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=PaginatedEvents)
def list_events(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort_by: str = Query("event_date", pattern="^(event_date|title|available_seats|created_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=500),
):
    total, items = db_service.list_events(
        search=search,
        category=category,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return PaginatedEvents(total=total, page=page, page_size=page_size, items=items)


@router.get("/categories/list")
def list_categories():
    categories = db_service.list_categories()
    return {"categories": categories}


@router.get("/{event_id}/capacity", response_model=EventCapacityOut)
def get_event_capacity(event_id: int):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return db_service.get_event_capacity(event_id)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.get("/{event_id}/history", response_model=list[EventEditHistoryOut])
def get_event_history(
    event_id: int,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return db_service.get_event_edit_history(event_id)


@router.get("/{event_id}/poster")
def get_event_poster(event_id: int):
    event = db_service.get_event_by_id(event_id)
    if not event or not event.poster_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event poster not found")
    from fastapi.responses import RedirectResponse
    clean = event.poster_url.replace("\\", "/").strip()
    if clean.startswith(("http://", "https://", "data:", "blob:")):
        return RedirectResponse(url=clean)
    rel = clean.lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/") :]
    return RedirectResponse(url=f"/api/uploads/{rel}")


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    venue: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    total_seats: int = Form(...),
    registration_type: str = Form("both"),
    max_team_size: int = Form(4),
    rules: Optional[str] = Form(None),
    requirements: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    poster_url: Optional[str] = Form(None),
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    final_poster_url = poster_url.strip() if poster_url and poster_url.strip() else None
    if poster:
        final_poster_url = await save_upload(poster, "event_posters")

    parsed_date = date.fromisoformat(str(event_date).strip()) if isinstance(event_date, str) else event_date

    event = db_service.create_event(
        title=title,
        description=description,
        category=category,
        venue=venue,
        event_date=parsed_date,
        event_time=event_time,
        total_seats=total_seats,
        available_seats=total_seats,
        poster_url=final_poster_url,
        created_by=current_user.id,
        registration_type=registration_type,
        max_team_size=max_team_size,
        rules=rules,
        requirements=requirements,
    )
    return event


@router.put("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    venue: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    event_time: Optional[str] = Form(None),
    total_seats: Optional[int] = Form(None),
    registration_type: Optional[str] = Form(None),
    max_team_size: Optional[int] = Form(None),
    rules: Optional[str] = Form(None),
    requirements: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    poster_url: Optional[str] = Form(None),
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    registered_count = event.total_seats - event.available_seats
    updates = {}
    changed_fields = {}

    if title is not None and title.strip() and title != event.title:
        updates["title"] = title.strip()
        changed_fields["title"] = {"old": event.title, "new": title.strip()}
    if description is not None and description != event.description:
        updates["description"] = description
        changed_fields["description"] = {"old": event.description, "new": description}
    if category is not None and category != event.category:
        updates["category"] = category
        changed_fields["category"] = {"old": event.category, "new": category}
    if venue is not None and venue != event.venue:
        updates["venue"] = venue
        changed_fields["venue"] = {"old": event.venue, "new": venue}
    if event_date is not None and str(event_date).strip():
        parsed_d = date.fromisoformat(str(event_date).strip())
        if parsed_d != event.event_date:
            updates["event_date"] = parsed_d
            changed_fields["event_date"] = {"old": str(event.event_date), "new": str(parsed_d)}
    if event_time is not None and event_time != event.event_time:
        updates["event_time"] = event_time
        changed_fields["event_time"] = {"old": event.event_time, "new": event_time}
    if registration_type is not None and registration_type != event.registration_type:
        updates["registration_type"] = registration_type
        changed_fields["registration_type"] = {"old": event.registration_type, "new": registration_type}
    if max_team_size is not None and max_team_size != event.max_team_size:
        updates["max_team_size"] = max_team_size
        changed_fields["max_team_size"] = {"old": event.max_team_size, "new": max_team_size}
    if rules is not None and rules != event.rules:
        updates["rules"] = rules
        changed_fields["rules"] = {"old": event.rules, "new": rules}
    if requirements is not None and requirements != event.requirements:
        updates["requirements"] = requirements
        changed_fields["requirements"] = {"old": event.requirements, "new": requirements}

    if total_seats is not None and total_seats != event.total_seats:
        if total_seats < registered_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot set total seats below current registrations ({registered_count})",
            )
        updates["total_seats"] = total_seats
        updates["available_seats"] = total_seats - registered_count
        changed_fields["total_seats"] = {"old": event.total_seats, "new": total_seats}

    if poster:
        old_poster = event.poster_url
        new_poster = await save_upload(poster, "event_posters")
        updates["poster_url"] = new_poster
        changed_fields["poster"] = {"old": "Previous Poster", "new": "Updated Poster"}
        if old_poster and not old_poster.startswith("http"):
            delete_file_if_exists(old_poster)
    elif poster_url is not None:
        clean_p = poster_url.strip()
        if clean_p and clean_p != event.poster_url:
            updates["poster_url"] = clean_p
            changed_fields["poster"] = {"old": "Previous Poster", "new": "Updated Poster"}

    # Any authenticated faculty or admin can update the event; original created_by remains untouched!
    updates["updated_by"] = current_user.id
    updates["updated_by_name"] = current_user.name
    updated_event = db_service.update_event(event_id, updates)

    # Record edit history if changes were made
    if changed_fields:
        db_service.create_event_edit_history(
            event_id=event_id,
            faculty_id=current_user.id,
            faculty_name=current_user.name,
            action="update",
            changed_fields=changed_fields,
        )

    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
def delete_event(
    event_id: int,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.poster_url:
        delete_file_if_exists(event.poster_url)

    db_service.delete_event(event_id)
    return {"message": "Event deleted successfully"}
