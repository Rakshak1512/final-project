import base64
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db import firestore_service as db_service
from app.dependencies import require_role
from app.models.notification import NotificationType
from app.models.user import RoleEnum, User
from app.schemas.certificate_schema import (
    CertificateAutoGenerateRequest,
    CertificateGenerateRequest,
    CertificateOut,
)
from app.services.storage_service import get_or_restore_file
from app.utils.email_utils import send_certificate_uploaded_email
from app.utils.file_utils import delete_file_if_exists, save_upload
from app.utils.pdf_utils import generate_certificate_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@router.post("/generate-preview")
def generate_certificate_preview_endpoint(
    payload: CertificateGenerateRequest,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """
    Generates dynamic certificate PDF bytes in-memory for previewing in frontend
    before saving or uploading. Does not persist to database.
    """
    clean_reg = payload.registration_number.strip()
    student = db_service.get_user_by_reg_no(clean_reg)
    
    event = None
    event_title = payload.event_title or "Campus Event"
    event_date_str = "Campus Event"
    if payload.event_id:
        event = db_service.get_event_by_id(payload.event_id)
        if event:
            event_title = event.title
            event_date_str = str(event.event_date) if event.event_date else "Campus Event"

    student_name = payload.student_name or (student.name if student else clean_reg)
    dept = payload.department or (student.department if student else "")
    sem = payload.semester or (str(student.semester) if student and student.semester else "")
    issuer_name = current_user.name or "Faculty Coordinator"

    pos = payload.award_standing or payload.position or "1st Place"
    achievement = payload.achievement_wording or pos

    pdf_bytes = generate_certificate_pdf(
        student_name=student_name,
        registration_number=clean_reg,
        event_title=event_title,
        event_date=event_date_str,
        certificate_id=999999,
        position=pos,
        department=dept,
        semester=sem,
        issuer_name=issuer_name,
        title=payload.title,
        achievement_wording=achievement,
        score_or_remarks=payload.score_or_remarks,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview_certificate.pdf"'},
    )


@router.post("/auto-generate", response_model=CertificateOut, status_code=status.HTTP_201_CREATED)
def auto_generate_certificate_endpoint(
    payload: CertificateAutoGenerateRequest,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """
    Auto-generates official certificate PDF, stores in Firestore & disk,
    links to result/winner record, and notifies the student.
    """
    clean_reg = payload.registration_number.strip()
    student = db_service.get_user_by_reg_no(clean_reg)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No student found with registration number {clean_reg}",
        )

    event = None
    event_title = payload.event_title or "Campus Event"
    event_date_str = "Campus Event"
    if payload.event_id:
        event = db_service.get_event_by_id(payload.event_id)
        if event:
            event_title = event.title
            event_date_str = str(event.event_date) if event.event_date else "Campus Event"

    # Prevent duplicate certificate generation and duplicate notification delivery
    if payload.event_id and clean_reg:
        existing_certs = db_service.get_certificates_by_registration_number(clean_reg)
        for existing in existing_certs:
            if existing.event_id == payload.event_id:
                cert_dict = existing.to_dict()
                cert_dict["student_email"] = student.email
                return CertificateOut(**cert_dict)

    from app.core.firebase import get_next_id
    cert_id = get_next_id("certificates")

    dept = payload.department or student.department or ""
    sem = payload.semester or (str(student.semester) if student.semester else "")
    issuer_name = current_user.name or "Faculty Coordinator"
    
    pos = payload.award_standing or payload.position or "1st Place"
    achievement = payload.achievement_wording or pos
    title = payload.title or f"{event_title} — {pos}"

    pdf_bytes = generate_certificate_pdf(
        student_name=student.name,
        registration_number=clean_reg,
        event_title=event_title,
        event_date=event_date_str,
        certificate_id=cert_id,
        position=pos,
        department=dept,
        semester=sem,
        issuer_name=issuer_name,
        title=title,
        achievement_wording=achievement,
        score_or_remarks=payload.score_or_remarks,
    )

    filename = f"cert_ESP_{cert_id:06d}_{clean_reg}.pdf"
    rel_path = f"certificates/{filename}"
    local_abs = os.path.join(settings.upload_dir_abs, rel_path)
    os.makedirs(os.path.dirname(local_abs), exist_ok=True)
    with open(local_abs, "wb") as f:
        f.write(pdf_bytes)

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # Send email notification
    email_status = "not_sent"
    try:
        sent = send_certificate_uploaded_email(
            student.email,
            student.name,
            f"{event_title} — {pos}",
        )
        email_status = "sent" if sent else "not_sent"
    except Exception as e:
        logger.warning(f"Failed to dispatch certificate email: {e}")
        email_status = "failed"

    certificate = db_service.create_certificate(
        registration_number=clean_reg,
        event_id=event.id if event else None,
        title=title,
        file_path=f"uploads/{rel_path}",
        uploaded_by=current_user.id,
        pdf_base64=pdf_b64,
        student_id=student.id,
        student_name=student.name,
        department=dept,
        semester=sem,
        event_title=event_title,
        award_standing=pos,
        achievement_wording=achievement,
        score_or_remarks=payload.score_or_remarks,
        certificate_issuance_mode="auto",
        email_notification_status=email_status,
    )

    # Link certificate to result if result_id provided
    if payload.result_id:
        db_service.update_event_result(payload.result_id, {"certificate_id": certificate.id})

    # Student In-App Notification
    db_service.create_notification(
        user_id=student.id,
        title="Certificate Issued",
        message=f'Congratulations! Your certificate for "{event_title}" ({pos}) is now available in your portal.',
        type=NotificationType.certificate_uploaded,
    )

    cert_dict = certificate.to_dict()
    cert_dict["student_email"] = student.email
    return CertificateOut(**cert_dict)


@router.post("", response_model=CertificateOut, status_code=status.HTTP_201_CREATED)
async def upload_certificate(
    registration_number: str = Form(...),
    title: str = Form(...),
    event_id: Optional[int] = Form(None),
    award_standing: Optional[str] = Form(None),
    achievement_wording: Optional[str] = Form(None),
    score_or_remarks: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    clean_reg = registration_number.strip()
    student = db_service.get_user_by_reg_no(clean_reg)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # File validation: accept pdf or images
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents or PNG/JPG images are allowed for certificates.",
        )

    file_path = await save_upload(file, "certificates")

    # Read base64 backup if <= 800KB
    pdf_b64 = None
    try:
        clean_rel = file_path.replace("\\", "/")
        sub_rel = clean_rel[len("uploads/") :] if clean_rel.startswith("uploads/") else clean_rel
        local_abs = os.path.join(settings.upload_dir_abs, sub_rel)
        if os.path.exists(local_abs) and os.path.getsize(local_abs) < 800 * 1024:
            with open(local_abs, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

    event = db_service.get_event_by_id(event_id) if event_id else None
    event_title = event.title if event else ""

    # Send email notification
    email_status = "not_sent"
    try:
        sent = send_certificate_uploaded_email(student.email, student.name, title)
        email_status = "sent" if sent else "not_sent"
    except Exception as e:
        logger.warning(f"Failed to dispatch certificate upload email: {e}")
        email_status = "failed"

    certificate = db_service.create_certificate(
        registration_number=clean_reg,
        event_id=event_id,
        title=title,
        file_path=file_path,
        uploaded_by=current_user.id,
        pdf_base64=pdf_b64,
        student_id=student.id,
        student_name=student.name,
        department=student.department,
        semester=str(student.semester) if student.semester else "",
        event_title=event_title,
        award_standing=award_standing,
        achievement_wording=achievement_wording,
        score_or_remarks=score_or_remarks,
        certificate_issuance_mode="upload",
        email_notification_status=email_status,
    )

    db_service.create_notification(
        user_id=student.id,
        title="New Certificate Uploaded",
        message=f'A certificate "{title}" has been uploaded to your account.',
        type=NotificationType.certificate_uploaded,
    )

    cert_dict = certificate.to_dict()
    cert_dict["student_email"] = student.email
    return CertificateOut(**cert_dict)


@router.get("/student/details/{registration_number}")
def get_student_details_by_registration(
    registration_number: str,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    student = db_service.get_user_by_reg_no(registration_number)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Fetch any active registrations for this student to pre-select or list related events
    registered_events = []
    try:
        registrations = db_service.get_student_registrations(student.id)
        for r in registrations:
            ev = db_service.get_event_by_id(r.event_id)
            if ev:
                registered_events.append({
                    "id": ev.id,
                    "title": ev.title,
                    "status": r.status,
                })
    except Exception as e:
        logger.debug(f"Failed to load student registered events: {e}")

    return {
        "id": student.id,
        "name": student.name,
        "registration_number": student.registration_number,
        "department": student.department,
        "semester": student.semester,
        "email": student.email,
        "registered_events": registered_events,
    }


@router.get("/my", response_model=list[CertificateOut])
def my_certificates(
    current_user: User = Depends(require_role(RoleEnum.student)),
):
    if not current_user.registration_number:
        return []

    return db_service.get_certificates_by_registration_number(current_user.registration_number)


@router.get("/{certificate_id}/download")
def download_certificate(
    certificate_id: int,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.faculty, RoleEnum.admin)),
):
    certificate = db_service.get_certificate_by_id(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")

    # Enforce the core rule: a student may ONLY access a certificate whose
    # registration_number matches their own.
    if current_user.role == RoleEnum.student:
        cert_reg = (certificate.registration_number or "").strip().lower()
        user_reg = (current_user.registration_number or "").strip().lower()
        if not user_reg or cert_reg != user_reg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this certificate")

    file_bytes = get_or_restore_file(certificate.file_path)
    if not file_bytes and certificate.pdf_base64:
        try:
            file_bytes = base64.b64decode(certificate.pdf_base64)
            # Restore to local cache
            clean_rel = certificate.file_path.replace("\\", "/")
            sub_rel = clean_rel[len("uploads/") :] if clean_rel.startswith("uploads/") else clean_rel
            local_abs = os.path.join(settings.upload_dir_abs, sub_rel)
            os.makedirs(os.path.dirname(local_abs), exist_ok=True)
            with open(local_abs, "wb") as f:
                f.write(file_bytes)
        except Exception:
            pass

    if not file_bytes:
        # On-the-fly regeneration for persistent zero-failure certificate serving
        from app.utils.pdf_utils import generate_certificate_pdf
        student = db_service.get_user_by_reg_no(certificate.registration_number)
        event = db_service.get_event_by_id(certificate.event_id) if certificate.event_id else None
        issuer = db_service.get_user_by_id(certificate.uploaded_by) if certificate.uploaded_by else None

        student_name = student.name if student else (certificate.registration_number or "Student Participant")
        event_title = event.title if event else certificate.title
        event_date_str = str(event.event_date) if event and event.event_date else "Campus Event"
        issuer_name = issuer.name if issuer else "Faculty Coordinator"

        file_bytes = generate_certificate_pdf(
            student_name=student_name,
            registration_number=certificate.registration_number or "",
            event_title=event_title,
            event_date=event_date_str,
            certificate_id=certificate.id,
            issuer_name=issuer_name,
        )

        # Cache back to database & disk
        try:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            db_service.update_certificate(certificate.id, {"pdf_base64": b64})
            clean_rel = certificate.file_path.replace("\\", "/")
            sub_rel = clean_rel[len("uploads/") :] if clean_rel.startswith("uploads/") else clean_rel
            local_abs = os.path.join(settings.upload_dir_abs, sub_rel)
            os.makedirs(os.path.dirname(local_abs), exist_ok=True)
            with open(local_abs, "wb") as f:
                f.write(file_bytes)
        except Exception:
            pass

    ext = os.path.splitext(certificate.file_path)[1].lower()
    media_type = "application/pdf"
    if ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"

    safe_title = "".join(c for c in certificate.title if c.isalnum() or c in (" ", "-", "_")).strip() or "certificate"
    headers = {
        "Content-Disposition": f'inline; filename="{safe_title}{ext or ".pdf"}"',
        "Access-Control-Expose-Headers": "Content-Disposition, Content-Type, Content-Length",
        "Cache-Control": "private, max-age=3600",
    }

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers=headers,
    )


@router.get("/faculty/uploaded", response_model=list[CertificateOut])
def faculty_uploaded_certificates(
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    return db_service.get_certificates_by_faculty(current_user.id)


@router.put("/{certificate_id}", response_model=CertificateOut)
async def update_certificate(
    certificate_id: int,
    title: str = Form(None),
    file: UploadFile = File(None),
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    certificate = db_service.get_certificate_by_id(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")

    if current_user.role == RoleEnum.faculty and certificate.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit certificates you uploaded")

    updates = {}
    if title:
        updates["title"] = title

    if file:
        old_path = certificate.file_path
        new_path = await save_upload(file, "certificates")
        updates["file_path"] = new_path
        delete_file_if_exists(old_path)
        try:
            clean_rel = new_path.replace("\\", "/")
            sub_rel = clean_rel[len("uploads/") :] if clean_rel.startswith("uploads/") else clean_rel
            local_abs = os.path.join(settings.upload_dir_abs, sub_rel)
            if os.path.exists(local_abs) and os.path.getsize(local_abs) < 800 * 1024:
                with open(local_abs, "rb") as f:
                    updates["pdf_base64"] = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass

    updated_cert = db_service.update_certificate(certificate_id, updates)
    return updated_cert


@router.delete("/{certificate_id}")
def delete_certificate(
    certificate_id: int,
    current_user: User = Depends(require_role(RoleEnum.faculty, RoleEnum.admin)),
):
    """
    Deletes certificate record & physical file.
    Unlinks certificate reference from any event_results.
    Keeps student registration, attendance, and event intact.
    """
    certificate = db_service.get_certificate_by_id(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")

    if current_user.role == RoleEnum.faculty and certificate.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete certificates you uploaded")

    delete_file_if_exists(certificate.file_path)
    db_service.delete_certificate(certificate_id)

    # Unlink from results if attached
    try:
        db = db_service.get_firestore_db()
        results_ref = db.collection("event_results")
        matching = results_ref.where("certificate_id", "==", certificate_id).stream()
        for doc in matching:
            doc.reference.update({"certificate_id": None})
    except Exception as e:
        logger.debug(f"Unlink certificate fallback: {e}")

    return {"message": "Certificate deleted successfully"}
