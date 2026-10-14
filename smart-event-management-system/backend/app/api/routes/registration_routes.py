import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db import firestore_service as db_service
from app.dependencies import require_role
from app.models.notification import NotificationType
from app.models.registration import RegistrationStatus
from app.models.user import RoleEnum, User
from app.schemas.event_schema import EventCapacityOut
from app.schemas.registration_schema import (
    BranchStatsOut,
    RegistrationCreate,
    RegistrationOut,
    RegistrationStatusUpdate,
    StudentSearchOut,
    TeamCreate,
    TeamOut,
)
from app.services.websocket_manager import notify_clients_sync
from app.utils.email_utils import (
    send_registration_approved_email,
    send_registration_cancellation_email,
    send_registration_confirmation_email,
    send_registration_rejected_email,
)
from app.utils.pdf_utils import generate_registration_slip_pdf
from app.utils.qr_utils import generate_qr_code, generate_qr_png_bytes, generate_ticket_code

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/registrations", tags=["Registrations"])


@router.get("/students/search", response_model=StudentSearchOut)
def search_student_for_team_endpoint(
    reg_no: str,
    event_id: int,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.faculty, RoleEnum.admin)),
):
    ok, msg, student_info = db_service.search_student_for_team(reg_no, event_id)
    if not ok:
        if "not available" in msg.lower() or "not a student" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return StudentSearchOut(**student_info)


@router.post("/team", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def register_team(
    payload: TeamCreate,
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    ok, msg, team = db_service.create_team_registration(
        event_id=payload.event_id,
        team_name=payload.team_name,
        leader_user=current_user,
        member_reg_nos=payload.member_registration_numbers,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return team


@router.get("/teams/event/{event_id}", response_model=list[TeamOut])
def get_event_teams(
    event_id: int,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return db_service.get_event_teams(event_id)


@router.get("/teams/my", response_model=list[TeamOut])
def get_my_teams(
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    return db_service.get_my_teams(current_user.id)


@router.post("", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED)
def register_for_event(
    payload: RegistrationCreate,
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    event = db_service.get_event_by_id(payload.event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.registration_type == "team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event only allows team registration. Please register as a team.",
        )

    # Check if student is already in a team for this event
    ok, msg, _ = db_service.search_student_for_team(current_user.registration_number or "", payload.event_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    ticket_code = generate_ticket_code()
    success, reg_msg, registration = db_service.create_registration_atomic(
        event_id=event.id,
        student_id=current_user.id,
        ticket_code=ticket_code,
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reg_msg)

    # Generate QR Code
    qr_payload = f"TICKET:{ticket_code}|EVENT:{event.id}|STUDENT:{current_user.id}"
    qr_path = generate_qr_code(qr_payload)
    db_service.update_registration_qr(registration.id, qr_path)

    # Student notification
    db_service.create_notification(
        user_id=current_user.id,
        title="Registration Successful",
        message=f"You have successfully registered for {event.title}.",
        type=NotificationType.registration_approved,
    )

    # Faculty notification
    if event.created_by:
        db_service.create_notification(
            user_id=event.created_by,
            title="New Event Registration",
            message=f"Student {current_user.name} registered for your event {event.title}.",
            type=NotificationType.general,
        )

    try:
        event_date_str = str(event.event_date) if hasattr(event, "event_date") and event.event_date else "N/A"
        event_time_str = event.event_time or "N/A"
        venue_str = event.venue or "Campus Venue"
        send_registration_confirmation_email(
            to_email=current_user.email,
            name=current_user.name,
            event_title=event.title,
            ticket_code=ticket_code,
            event_date=event_date_str,
            event_time=event_time_str,
            venue=venue_str,
        )
    except Exception as e:
        logger.error("[EMAIL ERROR] Exception during registration confirmation email dispatch to %s: %s", current_user.email, e)

    fresh_reg = db_service.get_registration_by_id(registration.id)

    # Real-time WebSocket broadcast: new registration created
    notify_clients_sync({
        "type": "REGISTRATION_CREATED",
        "registration_id": fresh_reg.id,
        "event_id": event.id,
        "student_id": current_user.id,
        "status": fresh_reg.status.value if hasattr(fresh_reg.status, "value") else str(fresh_reg.status),
        "ticket_code": fresh_reg.ticket_code,
    }, event_id=event.id)

    return fresh_reg


@router.get("/my", response_model=list[RegistrationOut])
def my_registrations(
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    regs = db_service.get_my_registrations(current_user.id)
    for r in regs:
        r.qr_code_path = f"/api/registrations/{r.id}/qr"
    return regs


@router.get("/{registration_id}/qr")
def get_registration_qr(registration_id: int):
    """
    Dynamically generates the QR code for a given registration.
    Guaranteed permanent across server restarts and deployments.
    """
    registration = db_service.get_registration_by_id(registration_id)
    if not registration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    ticket_code = registration.ticket_code or f"REG-{registration.id}"
    qr_payload = f"TICKET:{ticket_code}|EVENT:{registration.event_id}|STUDENT:{registration.student_id}"
    png_bytes = generate_qr_png_bytes(qr_payload)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'inline; filename="qr-{ticket_code}.png"',
        },
    )


@router.get("/ticket/{ticket_code}/qr")
def get_ticket_qr(ticket_code: str):
    """
    Dynamically generates QR code for a ticket code.
    """
    clean_code = ticket_code.strip()
    qr_payload = f"TICKET:{clean_code}"
    png_bytes = generate_qr_png_bytes(qr_payload)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'inline; filename="qr-{clean_code}.png"',
        },
    )


@router.delete("/{registration_id}")
def cancel_registration(
    registration_id: int,
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    reg = db_service.get_registration_by_id(registration_id)
    success, msg = db_service.cancel_registration_by_student(registration_id, current_user.id)
    if not success:
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Real-time WebSocket broadcast: student cancelled registration
    if reg:
        notify_clients_sync({
            "type": "REGISTRATION_CANCELLED",
            "registration_id": registration_id,
            "event_id": reg.event_id,
            "student_id": current_user.id,
            "status": "cancelled",
        }, event_id=reg.event_id)

    return {"message": "Registration cancelled successfully"}


@router.get("/event/{event_id}/branch-stats", response_model=BranchStatsOut)
def get_event_branch_stats_endpoint(
    event_id: int,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin, RoleEnum.volunteer)),
):
    """
    Returns real-time dynamic branch-wise registration statistics for an event.
    """
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return db_service.get_event_branch_stats(event_id)


@router.get("/{registration_id}/slip")
def download_slip(
    registration_id: int,
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    registration = db_service.get_registration_by_id(registration_id)
    if not registration or registration.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    pdf_bytes = generate_registration_slip_pdf(
        student_name=current_user.name,
        registration_number=current_user.registration_number or "N/A",
        event_title=registration.event.title if registration.event else "Event",
        venue=registration.event.venue if registration.event else "N/A",
        event_date=str(registration.event.event_date) if registration.event else "N/A",
        event_time=registration.event.event_time if registration.event else "N/A",
        ticket_code=registration.ticket_code,
        qr_code_path=registration.qr_code_path,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="slip-{registration.ticket_code}.pdf"'},
    )


@router.get("/event/{event_id}", response_model=list[RegistrationOut])
def event_registrations(
    event_id: int,
    search: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    semester: str | None = None,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    return db_service.get_event_registrations(
        event_id=event_id,
        search=search,
        branch=branch,
        status=status,
        semester=semester,
    )


@router.get("/event/{event_id}/capacity", response_model=EventCapacityOut)
def event_capacity(
    event_id: int,
):
    event = db_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    return db_service.get_event_capacity(event_id)


@router.put("/{registration_id}/status", response_model=RegistrationOut)
def update_registration_status(
    registration_id: int,
    payload: RegistrationStatusUpdate,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    status_val = payload.status.value if hasattr(payload.status, "value") else str(payload.status)
    clean_status = status_val.strip().lower()

    updated_reg, is_cancelling, event, student = db_service.update_registration_status(
        registration_id=registration_id,
        new_status=clean_status,
        action_by_user_id=current_user.id,
        action_by_user_name=current_user.name,
    )
    if not updated_reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    is_appr = getattr(updated_reg, "is_approving", False)
    is_rej = getattr(updated_reg, "is_rejecting", False)

    # 1. Approval workflow (only when transitioned to approved)
    if is_appr and student and event:
        logger.info("[APPROVAL] Faculty User %s (ID %s) approved registration %s", current_user.name, current_user.id, registration_id)
        db_service.create_notification(
            user_id=student.id,
            title="Registration Approved! 🎉",
            message=f"Congratulations! Your registration for '{event.title}' has been approved by the faculty. Your QR ticket is ready.",
            type=NotificationType.registration_approved,
        )
        try:
            send_registration_approved_email(
                to_email=student.email,
                name=student.name,
                event_title=event.title,
                registration_number=student.registration_number or "N/A",
                event_date=str(event.event_date) if event.event_date else "Campus Event",
                venue=event.venue or "Campus Venue",
                ticket_code=updated_reg.ticket_code or "N/A",
            )
        except Exception as e:
            logger.error("[EMAIL ERROR] Exception during approval email dispatch to %s: %s", student.email, e, exc_info=True)

    # 2. Rejection workflow (only when transitioned to rejected)
    elif is_rej and student and event:
        logger.info("[REJECTION] Faculty User %s (ID %s) rejected registration %s", current_user.name, current_user.id, registration_id)
        db_service.create_notification(
            user_id=student.id,
            title="Registration Not Approved",
            message=f"Your registration application for '{event.title}' was not approved.",
            type=NotificationType.general,
        )
        try:
            send_registration_rejected_email(
                to_email=student.email,
                name=student.name,
                event_title=event.title,
            )
        except Exception as e:
            logger.error("[EMAIL ERROR] Exception during rejection email dispatch to %s: %s", student.email, e, exc_info=True)

    # 3. Cancellation workflow (only when transitioned to cancelled)
    elif is_cancelling and student and event:
        logger.info("[CANCELLATION] Faculty User %s (ID %s) cancelled registration %s", current_user.name, current_user.id, registration_id)
        db_service.create_notification(
            user_id=student.id,
            title="Registration Cancelled",
            message=f"Your registration for '{event.title}' has been cancelled by the faculty coordinator.",
            type=NotificationType.registration_cancelled,
        )
        try:
            send_registration_cancellation_email(
                to_email=student.email,
                name=student.name,
                event_title=event.title,
            )
        except Exception as e:
            logger.error("[EMAIL ERROR] Exception during cancellation email dispatch to %s: %s", student.email, e, exc_info=True)

    # Real-time WebSocket broadcast: registration status changed
    notify_clients_sync({
        "type": "REGISTRATION_STATUS_CHANGED",
        "registration_id": updated_reg.id,
        "event_id": updated_reg.event_id,
        "student_id": updated_reg.student_id,
        "status": updated_reg.status.value if hasattr(updated_reg.status, "value") else str(updated_reg.status),
        "ticket_code": updated_reg.ticket_code,
    }, event_id=updated_reg.event_id)

    return updated_reg