import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db import firestore_service as db_service
from app.dependencies import get_current_user, require_role
from app.models.notification import NotificationType
from app.models.user import RoleEnum, User
from app.schemas.assignment_schema import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentStatusUpdate,
    AssignmentUpdate,
)
from app.schemas.user_schema import UserOut
from app.services.email_service import (
    send_faculty_approved_email,
    send_faculty_rejected_email,
    send_faculty_work_assigned_email,
    send_student_approved_email,
    send_student_rejected_email,
    send_volunteer_approved_email,
    send_volunteer_rejected_email,
)
from app.services.pdf_report_service import (
    generate_faculty_approval_pdf,
    generate_student_approval_pdf,
    generate_volunteer_approval_pdf,
)

logger = logging.getLogger("app.admin")

router = APIRouter(prefix="/api/admin", tags=["Admin"])
faculty_task_router = APIRouter(prefix="/api/faculty/tasks", tags=["Faculty Tasks"])
faculty_approval_router = APIRouter(prefix="/api/faculty", tags=["Faculty Approvals"])
reports_root_router = APIRouter(tags=["Reports PDF"])


class RejectionPayload(BaseModel):
    reason: Optional[str] = None


# ============================================================
# FACULTY DIRECTORY & MONITORING (ADMIN ONLY)
# ============================================================

@router.get("/faculty", response_model=List[dict])
def get_faculty_directory(
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """
    Real-time list of all active faculty members enriched with active task counts
    and events created count.
    """
    return db_service.get_all_faculty_with_stats()


# ============================================================
# WORK ASSIGNMENTS (ADMIN ONLY CRUD)
# ============================================================

@router.post("/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def assign_work_to_faculty(
    payload: AssignmentCreate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """
    Admin assigns work/tasks to a faculty member.
    1. Stores in Firestore assignments collection.
    2. Generates an in-app notification for the faculty member.
    3. Sends an email alert to the faculty member (with graceful fallback).
    """
    faculty = db_service.get_user_by_id(payload.faculty_id)
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target faculty member not found.",
        )

    assignment = db_service.create_assignment(
        faculty_id=payload.faculty_id,
        title=payload.title,
        description=payload.description,
        assigned_by=current_user.id,
        assigned_by_name=current_user.name or "Administrator",
        event_id=payload.event_id,
        priority=payload.priority,
        deadline=payload.deadline,
    )

    # 1. In-app notification for faculty
    event_info = f" for event '{assignment.event_title}'" if assignment.event_title else ""
    db_service.create_notification(
        user_id=faculty.id,
        title="New Work Assignment",
        message=f"Administrator {current_user.name} assigned you a new task: '{assignment.title}'{event_info} (Priority: {assignment.priority.upper()}).",
        type=NotificationType.general,
    )

    # 2. Email alert to faculty
    if faculty.email:
        try:
            send_faculty_work_assigned_email(
                to_email=faculty.email,
                faculty_name=faculty.name,
                task_title=assignment.title,
                description=assignment.description,
                priority=assignment.priority.value if hasattr(assignment.priority, "value") else str(assignment.priority),
                deadline=assignment.deadline,
                event_title=assignment.event_title,
                assigned_by_name=current_user.name,
            )
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not dispatch task assignment email to %s: %s", faculty.email, e)

    return assignment


@router.get("/assignments", response_model=List[AssignmentOut])
def get_all_assignments(
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """List all work assignments across faculty."""
    return db_service.get_all_assignments()


@router.get("/assignments/faculty/{faculty_id}", response_model=List[AssignmentOut])
def get_assignments_for_faculty(
    faculty_id: int,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Get all assignments for a specific faculty member."""
    return db_service.get_faculty_assignments(faculty_id)


@router.put("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Edit or update an existing faculty assignment."""
    updated = db_service.update_assignment(assignment_id, payload.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found.",
        )
    return updated


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Delete an assignment."""
    success = db_service.delete_assignment(assignment_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found.",
        )
    return {"message": "Assignment deleted successfully"}


# ============================================================
# FACULTY-FACING TASK ENDPOINTS
# ============================================================

@faculty_task_router.get("", response_model=List[AssignmentOut])
def get_my_assigned_tasks(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty retrieves their own assigned tasks."""
    return db_service.get_faculty_assignments(current_user.id)


@faculty_task_router.put("/{assignment_id}/status", response_model=AssignmentOut)
def update_my_task_status(
    assignment_id: int,
    payload: AssignmentStatusUpdate,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty updates the status of their assigned task (Pending, In Progress, Completed)."""
    task = db_service.get_assignment_by_id(assignment_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found.",
        )
    if current_user.role == RoleEnum.faculty and task.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own assigned tasks.",
        )

    updated = db_service.update_assignment(assignment_id, {"status": payload.status})
    return updated


# ============================================================
# ADMINISTRATIVE REPORTS SUMMARY
# ============================================================

@router.get("/reports/summary")
def get_admin_reports_summary(
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """
    Returns aggregate counts for system reports.
    """
    all_users = db_service.get_all_users()
    all_events = db_service.get_all_events()
    all_assignments = db_service.get_all_assignments()

    students = [u for u in all_users if u.role == RoleEnum.student]
    faculties = [u for u in all_users if u.role == RoleEnum.faculty]
    volunteers = [u for u in all_users if u.role == RoleEnum.volunteer]

    total_seats = sum(e.total_seats for e in all_events)
    total_reg = sum(e.total_seats - e.available_seats for e in all_events)

    return {
        "total_users": len(all_users),
        "total_students": len(students),
        "total_faculty": len(faculties),
        "total_volunteers": len(volunteers),
        "total_events": len(all_events),
        "total_seat_capacity": total_seats,
        "total_registrations": total_reg,
        "total_assignments": len(all_assignments),
        "active_assignments": sum(1 for a in all_assignments if a.status in ("pending", "in_progress")),
        "completed_assignments": sum(1 for a in all_assignments if a.status == "completed"),
    }


# ============================================================
# FACULTY ACCOUNT APPROVAL WORKFLOW (ADMIN ONLY)
# ============================================================

@router.get("/pending-faculty", response_model=List[UserOut])
def get_pending_faculty_accounts(
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin retrieves all faculty registrations awaiting institutional verification."""
    return db_service.get_pending_faculty()


@router.get("/faculty-approvals")
def get_all_faculty_approvals_with_stats(
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin retrieves full faculty approval roster with pending, approved, and rejected statistics."""
    return db_service.get_all_faculty_approvals()


@router.post("/faculty/{faculty_id}/approve", response_model=UserOut)
def approve_faculty_account(
    faculty_id: str,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin approves a faculty account, activating dashboard and event management privileges."""
    fac = db_service.get_user_by_id(faculty_id)
    if not fac or fac.role != RoleEnum.faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty account not found.")

    updated = db_service.approve_user(faculty_id, approver_id=current_user.id)

    # In-app notification
    db_service.create_notification(
        user_id=faculty_id,
        title="Faculty Account Approved",
        message=f"Administrator {current_user.name} has approved your faculty credentials. You can now access your Faculty Dashboard!",
        type=NotificationType.general,
    )

    # Email notification via Gmail SMTP
    if fac.email:
        try:
            fac_id = fac.admin_id or fac.registration_number or f"FAC-{fac.id}"
            send_faculty_approved_email(fac.email, fac.name, fac_id)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send faculty approval email to %s: %s", fac.email, e)

    return updated


@router.post("/faculty/{faculty_id}/reject", response_model=UserOut)
def reject_faculty_account(
    faculty_id: str,
    payload: Optional[RejectionPayload] = None,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin rejects an unverified faculty registration."""
    fac = db_service.get_user_by_id(faculty_id)
    if not fac or fac.role != RoleEnum.faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty account not found.")

    reason = payload.reason if payload else None
    updated = db_service.reject_user(faculty_id, reason=reason, rejected_by=current_user.id)

    if fac.email:
        try:
            send_faculty_rejected_email(fac.email, fac.name, reason)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send faculty rejection email to %s: %s", fac.email, e)

    return updated


@router.delete("/faculty/{faculty_id}")
def remove_faculty_account(
    faculty_id: str,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin removes a faculty account safely without breaking related records."""
    fac = db_service.get_user_by_id(faculty_id)
    if not fac or fac.role != RoleEnum.faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty account not found.")

    success = db_service.remove_user_account(faculty_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to remove faculty account.")

    try:
        db_service.create_audit_log(
            user_id=current_user.id,
            action="remove_faculty",
            entity_type="user",
            entity_id=faculty_id,
            details=f"Admin {current_user.name} removed faculty account {fac.name} ({fac.email}).",
        )
    except Exception:
        pass

    return {"message": "Faculty account removed successfully."}


# ============================================================
# FACULTY PDF REPORT ENDPOINTS (ADMIN ONLY)
# ============================================================

def _generate_faculty_pdf_response(status_type: str) -> Response:
    status_lower = (status_type or "all").lower().strip()
    data = db_service.get_all_faculty_approvals()
    all_faculty: List[User] = data.get("faculty", [])

    if status_lower == "pending":
        filtered = [f for f in all_faculty if (f.approval_status or "PENDING").upper() == "PENDING"]
        filename = "Pending Faculty.pdf"
        label = "Pending Faculty"
    elif status_lower == "approved":
        filtered = [f for f in all_faculty if (f.approval_status or "PENDING").upper() == "APPROVED"]
        filename = "Approved Faculty.pdf"
        label = "Approved Faculty"
    elif status_lower == "rejected":
        filtered = [f for f in all_faculty if (f.approval_status or "PENDING").upper() == "REJECTED"]
        filename = "Rejected Faculty.pdf"
        label = "Rejected Faculty"
    else:
        filtered = all_faculty
        filename = "All Faculty.pdf"
        label = "All Faculty"

    pdf_bytes = generate_faculty_approval_pdf(filtered, label)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


@router.get("/reports/faculty/{status_type}/pdf")
def download_faculty_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    """Admin downloads faculty PDF report by status (pending, approved, rejected, all)."""
    return _generate_faculty_pdf_response(status_type)


@router.get("/reports/faculty/pending/pdf")
def download_faculty_pending_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("pending")


@router.get("/reports/faculty/approved/pdf")
def download_faculty_approved_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("approved")


@router.get("/reports/faculty/rejected/pdf")
def download_faculty_rejected_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("rejected")


@router.get("/reports/faculty/all/pdf")
def download_faculty_all_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("all")


# ============================================================
# STUDENT ACCOUNT APPROVAL WORKFLOW (FACULTY ONLY)
# ============================================================

@faculty_approval_router.get("/pending-students", response_model=List[UserOut])
def get_pending_student_accounts(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty retrieves all student registrations awaiting departmental approval."""
    return db_service.get_pending_students()


@faculty_approval_router.get("/student-approvals")
def get_all_student_approvals_with_stats(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty retrieves complete student approvals roster with pending, approved, and rejected statistics."""
    return db_service.get_all_students_approvals()


@faculty_approval_router.post("/students/{student_id}/approve", response_model=UserOut)
def approve_student_account(
    student_id: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty approves a student registration, unlocking the student dashboard and ticket registration."""
    student = db_service.get_user_by_id(student_id)
    if not student or student.role != RoleEnum.student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student account not found.")

    updated = db_service.approve_user(student_id, approver_id=current_user.id)

    # In-app notification
    db_service.create_notification(
        user_id=student_id,
        title="Student Account Approved",
        message=f"Faculty coordinator {current_user.name} has approved your account. Welcome to EventSphere!",
        type=NotificationType.general,
    )

    # Email notification via Gmail SMTP
    if student.email:
        try:
            send_student_approved_email(student.email, student.name, student.registration_number)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send student approval email to %s: %s", student.email, e)

    return updated


@faculty_approval_router.post("/students/{student_id}/reject", response_model=UserOut)
def reject_student_account(
    student_id: str,
    payload: Optional[RejectionPayload] = None,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty rejects a student registration."""
    student = db_service.get_user_by_id(student_id)
    if not student or student.role != RoleEnum.student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student account not found.")

    reason = payload.reason if payload else None
    updated = db_service.reject_user(student_id, reason=reason, rejected_by=current_user.id)

    if student.email:
        try:
            send_student_rejected_email(student.email, student.name, reason)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send student rejection email to %s: %s", student.email, e)

    return updated


@faculty_approval_router.delete("/students/{student_id}")
def remove_student_account(
    student_id: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty or Admin removes a student account safely without breaking related records."""
    student = db_service.get_user_by_id(student_id)
    if not student or student.role != RoleEnum.student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student account not found.")

    success = db_service.remove_user_account(student_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to remove student account.")

    try:
        db_service.create_audit_log(
            user_id=current_user.id,
            action="remove_student",
            entity_type="user",
            entity_id=student_id,
            details=f"Coordinator {current_user.name} removed student account {student.name} ({student.email}).",
        )
    except Exception:
        pass

    return {"message": "Student account removed successfully."}


# ============================================================
# STUDENT PDF REPORT ENDPOINTS (FACULTY & ADMIN ONLY)
# ============================================================

def _generate_student_pdf_response(status_type: str) -> Response:
    status_lower = (status_type or "all").lower().strip()
    data = db_service.get_all_students_approvals()
    all_students: List[User] = data.get("students", [])

    if status_lower == "pending":
        filtered = [s for s in all_students if (s.approval_status or "PENDING").upper() == "PENDING"]
        filename = "Pending Students.pdf"
        label = "Pending Students"
    elif status_lower == "approved":
        filtered = [s for s in all_students if (s.approval_status or "PENDING").upper() == "APPROVED"]
        filename = "Approved Students.pdf"
        label = "Approved Students"
    elif status_lower == "rejected":
        filtered = [s for s in all_students if (s.approval_status or "PENDING").upper() == "REJECTED"]
        filename = "Rejected Students.pdf"
        label = "Rejected Students"
    else:
        filtered = all_students
        filename = "All Students.pdf"
        label = "All Students"

    pdf_bytes = generate_student_approval_pdf(filtered, label)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


@faculty_approval_router.get("/reports/students/{status_type}/pdf")
def download_student_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty downloads student PDF report by status (pending, approved, rejected, all)."""
    return _generate_student_pdf_response(status_type)


@faculty_approval_router.get("/reports/students/pending/pdf")
def download_student_pending_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("pending")


@faculty_approval_router.get("/reports/students/approved/pdf")
def download_student_approved_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("approved")


@faculty_approval_router.get("/reports/students/rejected/pdf")
def download_student_rejected_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("rejected")


@faculty_approval_router.get("/reports/students/all/pdf")
def download_student_all_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("all")


# ============================================================
# ROOT COMPATIBILITY REPORT ENDPOINTS (WITHOUT /api PREFIX)
# ============================================================

@reports_root_router.get("/admin/reports/faculty/{status_type}/pdf")
def root_faculty_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.admin)),
):
    return _generate_faculty_pdf_response(status_type)


@reports_root_router.get("/admin/reports/faculty/pending/pdf")
def root_faculty_pending_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("pending")


@reports_root_router.get("/admin/reports/faculty/approved/pdf")
def root_faculty_approved_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("approved")


@reports_root_router.get("/admin/reports/faculty/rejected/pdf")
def root_faculty_rejected_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("rejected")


@reports_root_router.get("/admin/reports/faculty/all/pdf")
def root_faculty_all_pdf(current_user: User = Depends(require_role(RoleEnum.admin))):
    return _generate_faculty_pdf_response("all")


@reports_root_router.get("/faculty/reports/students/{status_type}/pdf")
def root_student_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response(status_type)


@reports_root_router.get("/faculty/reports/students/pending/pdf")
def root_student_pending_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("pending")


@reports_root_router.get("/faculty/reports/students/approved/pdf")
def root_student_approved_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("approved")


@reports_root_router.get("/faculty/reports/students/rejected/pdf")
def root_student_rejected_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("rejected")


@reports_root_router.get("/faculty/reports/students/all/pdf")
def root_student_all_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_student_pdf_response("all")


# ============================================================
# VOLUNTEER ACCOUNT APPROVAL WORKFLOW (FACULTY & ADMIN)
# ============================================================

@faculty_approval_router.get("/pending-volunteers", response_model=List[UserOut])
def get_pending_volunteer_accounts(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty retrieves all volunteer registrations awaiting departmental approval."""
    return db_service.get_pending_volunteers()


@faculty_approval_router.get("/volunteer-approvals")
def get_all_volunteer_approvals_with_stats(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty retrieves complete volunteer approvals roster with pending, approved, and rejected statistics."""
    return db_service.get_all_volunteer_approvals()


@faculty_approval_router.post("/volunteers/{volunteer_id}/approve", response_model=UserOut)
def approve_volunteer_account(
    volunteer_id: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty approves a volunteer registration, unlocking volunteer dashboard and features."""
    volunteer = db_service.get_user_by_id(volunteer_id)
    if not volunteer or volunteer.role != RoleEnum.volunteer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer account not found.")

    updated = db_service.approve_user(volunteer_id, approver_id=current_user.id)

    # In-app notification
    db_service.create_notification(
        user_id=volunteer_id,
        title="Volunteer Account Approved",
        message=f"Faculty coordinator {current_user.name} has approved your volunteer account. You may now access the Volunteer Dashboard.",
        type=NotificationType.general,
    )

    # Email notification via Gmail SMTP
    if volunteer.email:
        try:
            vol_id = volunteer.registration_number or volunteer.admin_id or f"VOL-{volunteer.id}"
            send_volunteer_approved_email(volunteer.email, volunteer.name, vol_id)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send volunteer approval email to %s: %s", volunteer.email, e)

    return updated


@faculty_approval_router.post("/volunteers/{volunteer_id}/reject", response_model=UserOut)
def reject_volunteer_account(
    volunteer_id: str,
    payload: Optional[RejectionPayload] = None,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty rejects a volunteer registration."""
    volunteer = db_service.get_user_by_id(volunteer_id)
    if not volunteer or volunteer.role != RoleEnum.volunteer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer account not found.")

    reason = payload.reason if payload else None
    updated = db_service.reject_user(volunteer_id, reason=reason, rejected_by=current_user.id)

    if volunteer.email:
        try:
            send_volunteer_rejected_email(volunteer.email, volunteer.name, reason)
        except Exception as e:
            logger.error("[EMAIL ERROR] Could not send volunteer rejection email to %s: %s", volunteer.email, e)

    return updated


@faculty_approval_router.delete("/volunteers/{volunteer_id}")
def remove_volunteer_account(
    volunteer_id: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty or Admin removes a volunteer account safely without breaking related records."""
    volunteer = db_service.get_user_by_id(volunteer_id)
    if not volunteer or volunteer.role != RoleEnum.volunteer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer account not found.")

    success = db_service.remove_user_account(volunteer_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to remove volunteer account.")

    try:
        db_service.create_audit_log(
            user_id=current_user.id,
            action="remove_volunteer",
            entity_type="user",
            entity_id=volunteer_id,
            details=f"Coordinator {current_user.name} removed volunteer account {volunteer.name} ({volunteer.email}).",
        )
    except Exception:
        pass

    return {"message": "Volunteer account removed successfully."}


# ============================================================
# VOLUNTEER PDF REPORT ENDPOINTS (FACULTY & ADMIN ONLY)
# ============================================================

def _generate_volunteer_pdf_response(status_type: str) -> Response:
    status_lower = (status_type or "all").lower().strip()
    data = db_service.get_all_volunteer_approvals()
    all_volunteers: List[User] = data.get("volunteers", [])

    if status_lower == "pending":
        filtered = [v for v in all_volunteers if (v.approval_status or "PENDING").upper() == "PENDING"]
        filename = "Pending Volunteers.pdf"
        label = "Pending Volunteers"
    elif status_lower == "approved":
        filtered = [v for v in all_volunteers if (v.approval_status or "PENDING").upper() == "APPROVED"]
        filename = "Approved Volunteers.pdf"
        label = "Approved Volunteers"
    elif status_lower == "rejected":
        filtered = [v for v in all_volunteers if (v.approval_status or "PENDING").upper() == "REJECTED"]
        filename = "Rejected Volunteers.pdf"
        label = "Rejected Volunteers"
    else:
        filtered = all_volunteers
        filename = "All Volunteers.pdf"
        label = "All Volunteers"

    pdf_bytes = generate_volunteer_approval_pdf(filtered, label)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


@faculty_approval_router.get("/reports/volunteers/{status_type}/pdf")
def download_volunteer_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """Faculty downloads volunteer PDF report by status (pending, approved, rejected, all)."""
    return _generate_volunteer_pdf_response(status_type)


@faculty_approval_router.get("/reports/volunteers/pending/pdf")
def download_volunteer_pending_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("pending")


@faculty_approval_router.get("/reports/volunteers/approved/pdf")
def download_volunteer_approved_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("approved")


@faculty_approval_router.get("/reports/volunteers/rejected/pdf")
def download_volunteer_rejected_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("rejected")


@faculty_approval_router.get("/reports/volunteers/all/pdf")
def download_volunteer_all_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("all")


@reports_root_router.get("/faculty/reports/volunteers/{status_type}/pdf")
def root_volunteer_report_pdf(
    status_type: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response(status_type)


@reports_root_router.get("/faculty/reports/volunteers/pending/pdf")
def root_volunteer_pending_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("pending")


@reports_root_router.get("/faculty/reports/volunteers/approved/pdf")
def root_volunteer_approved_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("approved")


@reports_root_router.get("/faculty/reports/volunteers/rejected/pdf")
def root_volunteer_rejected_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("rejected")


@reports_root_router.get("/faculty/reports/volunteers/all/pdf")
def root_volunteer_all_pdf(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return _generate_volunteer_pdf_response("all")

