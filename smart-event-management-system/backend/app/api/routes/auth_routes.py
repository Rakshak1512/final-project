from datetime import datetime, timedelta, timezone
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from firebase_admin import auth as firebase_auth_admin

from app.core.config import settings
from app.core.firebase_auth import verify_firebase_id_token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp,
    hash_password,
    verify_otp_hash,
    verify_password,
)
from app.db import firestore_service as db_service
from app.dependencies import get_client_ip, get_current_user
from app.models.user import RoleEnum, User
from app.schemas.user_schema import (
    EmailSendOtpRequest,
    EmailVerifyOtpRequest,
    ForgotPasswordRequest,
    FirebaseRegisterRequest,
    FirebaseSessionRequest,
    FirebasePasswordResetPrepareRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    Token,
    TokenRefreshRequest,
    UserCreate,
    UserLogin,
    UserOut,
    VerifyEmailRequest,
    VerifyResetOtpRequest,
)
from app.services.email_service import (
    _mask_email,
    send_account_pending_approval_email,
    send_admin_new_faculty_alert_email,
    send_otp_email,
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _log(user_id, action: str, request: Request, details: str = None):
    try:
        db_service.create_audit_log(
            user_id=user_id,
            action=action,
            entity_type="user",
            entity_id=user_id,
            ip_address=get_client_ip(request),
            details=details,
        )
    except Exception:
        pass


@router.post("/firebase/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def firebase_register(payload: FirebaseRegisterRequest, request: Request):
    """Create/synchronize the EventSphere profile after Firebase creates the account."""
    try:
        decoded = verify_firebase_id_token(payload.id_token)
    except Exception as e:
        logger.warning("Firebase registration token rejected: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase authentication token")

    clean_email = decoded["email"]
    token_verified = bool(decoded.get("email_verified"))
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)

    if payload.role == RoleEnum.student and not payload.registration_number:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Registration number is required for students")
    if payload.role == RoleEnum.admin and not (payload.admin_id or payload.registration_number):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Admin ID is required for admins")

    existing = db_service.get_user_by_email(clean_email)
    if existing and existing.is_email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists.")

    if payload.registration_number and payload.role == RoleEnum.student:
        existing_reg = db_service.get_user_by_reg_no(payload.registration_number)
        if existing_reg and (not existing or existing_reg.id != existing.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration number already in use")

    try:
        role_lower = role_str.lower()
        if role_lower in ("student", "faculty", "volunteer"):
            init_active = False
            init_status = "PENDING"
        else:
            init_active = True
            init_status = "APPROVED"

        if existing:
            updates = {
                "name": payload.name.strip(),
                "role": role_str,
                "registration_number": payload.registration_number or existing.registration_number,
                "admin_id": payload.admin_id or existing.admin_id,
                "department": payload.department or existing.department,
                "semester": payload.semester or existing.semester,
                "is_email_verified": token_verified,
            }
            user = db_service.update_user(existing.id, updates)
        else:
            user = db_service.create_user(
                name=payload.name.strip(),
                email=clean_email,
                # Firebase owns password authentication. Keep a non-usable
                # local hash for backward compatibility with existing schema.
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                role=role_str,
                registration_number=payload.registration_number,
                admin_id=payload.admin_id,
                department=payload.department,
                semester=payload.semester,
                is_email_verified=token_verified,
                is_active=init_active,
                approval_status=init_status,
            )
            if role_lower in ("student", "faculty", "volunteer"):
                try:
                    send_account_pending_approval_email(clean_email, payload.name.strip(), role_lower)
                    if role_lower == "faculty":
                        admin_recipient = getattr(settings, "ADMIN_EMAIL", "admin@test.com")
                        send_admin_new_faculty_alert_email(admin_recipient, user.name, user.email, user.department)
                except Exception as mail_err:
                    logger.warning("[EMAIL] Failed to send registration email: %s", mail_err)

        logger.info(
            "Firebase profile synchronized for %s (verified=%s, status=%s)",
            _mask_email(clean_email),
            token_verified,
            user.approval_status,
        )
        _log(user.id, "firebase_register", request)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Firebase registration failed for %s", _mask_email(clean_email))
        raise HTTPException(status_code=500, detail="Unable to create your EventSphere profile")


@router.post("/firebase/prepare-password-reset")
def prepare_firebase_password_reset(payload: FirebasePasswordResetPrepareRequest):
    """Provision a Firebase password account for a legacy EventSphere user before reset."""
    clean_email = payload.email.strip().lower()
    user = db_service.get_user_by_email(clean_email)

    # Never reveal whether an email exists in EventSphere.
    if not user:
        return {"ready": True}

    try:
        try:
            firebase_user = firebase_auth_admin.get_user_by_email(clean_email)
        except firebase_auth_admin.UserNotFoundError:
            firebase_user = firebase_auth_admin.create_user(
                email=clean_email,
                password=secrets.token_urlsafe(24),
                email_verified=bool(user.is_email_verified),
                display_name=user.name,
            )
        return {"ready": True, "firebase_user_exists": True}
    except Exception as e:
        logger.warning("Firebase reset preparation failed for %s: %s", _mask_email(clean_email), e)
        # Keep the response generic; the frontend will show the standard reset message.
        return {"ready": True}


@router.post("/firebase/session", response_model=Token)
def firebase_session(payload: FirebaseSessionRequest, request: Request):
    """Exchange a verified Firebase ID token for the EventSphere API JWT."""
    try:
        decoded = verify_firebase_id_token(payload.id_token)
    except Exception as e:
        logger.warning("Firebase session token rejected: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase authentication token")

    if not decoded.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before logging in.",
        )

    clean_email = decoded["email"]
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    user = db_service.get_user_by_email(clean_email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your EventSphere profile was not found. Please complete registration first.",
        )

    user_role_str = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower().strip()
    if user_role_str != role_str.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account does not have permission for this role.",
        )

    appr_st = str(getattr(user, "approval_status", "APPROVED") or "APPROVED").upper().strip()
    if not user.is_active:
        if appr_st not in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL", "REJECTED"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is currently inactive.")

    if not user.is_email_verified:
        user = db_service.update_user(user.id, {"is_email_verified": True}) or user

    access_expires = timedelta(days=30) if payload.remember_me else None
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token({"sub": str(user.id), "role": role_val}, access_expires)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    _log(user.id, "firebase_login", request)
    return Token(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request):
    clean_email = payload.email.strip().lower()
    admin_id = payload.admin_id.strip() if payload.admin_id and payload.admin_id.strip() else None
    reg_num = payload.registration_number.strip() if payload.registration_number and payload.registration_number.strip() else None
    dept = payload.department.strip() if payload.department and payload.department.strip() else None
    sem = payload.semester.strip() if payload.semester and payload.semester.strip() else None
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)

    if payload.role == RoleEnum.admin and admin_id and not reg_num:
        reg_num = admin_id

    existing = db_service.get_user_by_email(clean_email)
    if existing and existing.is_email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists.")

    if reg_num and payload.role == RoleEnum.student:
        existing_reg = db_service.get_user_by_reg_no(reg_num)
        if existing_reg and existing_reg.is_email_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration number already in use")

    try:
        otp = generate_otp()
        hashed_otp = hash_otp(otp)
        logger.info("[AUTH] [OTP] Secure OTP generated for %s (Expires in %d min)", _mask_email(clean_email), settings.OTP_EXPIRE_MINUTES)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

        pending_data = {
            "name": payload.name.strip(),
            "email": clean_email,
            "hashed_password": hash_password(payload.password),
            "role": role_str,
            "registration_number": reg_num,
            "admin_id": admin_id or (reg_num if role_str == "admin" else None),
            "department": dept,
            "semester": sem,
            "hashed_otp": hashed_otp,
            "otp_code": otp,
            "attempts": 0,
            "max_attempts": settings.OTP_MAX_ATTEMPTS,
            "last_sent_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
        db_service.save_pending_registration(pending_data)
        logger.info("[AUTH] [OTP] Pending registration saved securely for %s", _mask_email(clean_email))

        # Dispatch OTP via Resend
        try:
            email_sent, email_msg = send_otp_email(clean_email, otp, payload.name.strip(), settings.OTP_EXPIRE_MINUTES)
            if not email_sent:
                if settings.APP_ENV == "production" or (settings.RESEND_API_KEY and not settings.DEBUG):
                    logger.error("[AUTH] [EMAIL] Registration verification email could not be sent to %s: %s", _mask_email(clean_email), email_msg)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Unable to send verification email via Resend. Please try again later.",
                    )
                else:
                    logger.warning("[AUTH] [EMAIL] Verification email could not be delivered to %s: %s", _mask_email(clean_email), email_msg)
        except HTTPException:
            raise
        except Exception as mail_err:
            logger.error("[AUTH] [EMAIL] Unexpected error delivering OTP to %s: %s", _mask_email(clean_email), mail_err)
            if settings.APP_ENV == "production" or (settings.RESEND_API_KEY and not settings.DEBUG):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to send verification email via Resend. Please try again later.",
                )

        # Return unverified placeholder UserOut object without exposing OTP
        return UserOut(
            id=0,
            name=payload.name.strip(),
            email=clean_email,
            phone=None,
            role=payload.role,
            registration_number=reg_num,
            admin_id=admin_id or (reg_num if role_str == "admin" else None),
            department=dept,
            semester=sem,
            is_email_verified=False,
            created_at=datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to process registration: {str(e)}",
        )


@router.post("/verify-email", response_model=UserOut)
def verify_email(payload: VerifyEmailRequest, request: Request):
    clean_email = str(payload.email).strip().lower()
    otp_input = str(payload.otp_code).strip()

    # 1. Check pending registration (staged before adding to users table)
    pending = db_service.get_pending_registration(clean_email)
    if pending:
        # Check attempts limit
        attempts = int(pending.get("attempts", 0))
        max_attempts = int(pending.get("max_attempts", settings.OTP_MAX_ATTEMPTS))
        if attempts >= max_attempts:
            logger.warning("OTP verification failed (max attempts exceeded) for %s", _mask_email(clean_email))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new OTP.",
            )

        # Check expiration
        exp = pending.get("expires_at")
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                logger.warning("OTP verification failed (expired OTP) for %s", _mask_email(clean_email))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This OTP has expired. Please request a new OTP.",
                )

        # Constant-time secure verification
        hashed_otp = pending.get("hashed_otp")
        is_match = False
        if hashed_otp and verify_otp_hash(otp_input, hashed_otp):
            is_match = True
        elif pending.get("otp_code") and str(pending.get("otp_code")).strip() == otp_input:
            is_match = True

        if not is_match:
            pending["attempts"] = attempts + 1
            db_service.save_pending_registration(pending)
            logger.warning(
                "OTP verification failed (invalid OTP) for %s (attempt %d/%d)",
                _mask_email(clean_email),
                attempts + 1,
                max_attempts,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP. Please try again.")

        # Determine approval status: students & volunteers require faculty approval; faculty require admin approval
        p_role = str(pending.get("role", "")).lower()
        if p_role in ("student", "faculty", "volunteer"):
            appr_status = "PENDING"
            is_active_flag = False
        else:
            appr_status = "APPROVED"
            is_active_flag = True

        # Create user in permanent users table now that email is verified
        created_user = db_service.create_user(
            name=pending["name"],
            email=pending["email"],
            hashed_password=pending["hashed_password"],
            role=pending["role"],
            registration_number=pending.get("registration_number"),
            admin_id=pending.get("admin_id"),
            phone=pending.get("phone"),
            department=pending.get("department"),
            semester=pending.get("semester"),
            is_email_verified=True,
            is_active=is_active_flag,
            approval_status=appr_status,
        )

        db_service.delete_pending_registration(clean_email)
        logger.info("[AUTH] [APPROVAL] User %s created with status %s (ID: %s)", _mask_email(clean_email), appr_status, created_user.id)
        _log(created_user.id, "verify_email", request)

        # Dispatch async approval notification emails
        if p_role in ("student", "faculty", "volunteer"):
            try:
                send_account_pending_approval_email(created_user.email, created_user.name, p_role)
                if p_role == "faculty":
                    admin_recipient = getattr(settings, "ADMIN_EMAIL", "admin@test.com")
                    send_admin_new_faculty_alert_email(admin_recipient, created_user.name, created_user.email, created_user.department)
            except Exception as mail_err:
                logger.error("[EMAIL ERROR] Exception sending pending approval email for %s: %s", _mask_email(clean_email), mail_err)

        return created_user

    # 2. Legacy fallback for users created prior to pending table
    user = db_service.get_user_by_email(clean_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this email. Please register first.",
        )

    if user.is_email_verified:
        return user

    verification = db_service.get_latest_email_verification(user.id, otp_input)
    if not verification:
        logger.warning("OTP verification failed (invalid OTP) for %s", _mask_email(clean_email))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP. Please try again.")

    exp = verification.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        logger.warning("OTP verification failed (expired OTP) for %s", _mask_email(clean_email))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This OTP has expired. Please request a new OTP.")

    db_service.mark_email_verification_used(verification.id)
    updated_user = db_service.update_user(user.id, {"is_email_verified": True})
    logger.info("OTP verification successful for %s", _mask_email(clean_email))
    _log(user.id, "verify_email", request)

    return updated_user


@router.post("/email/send-login-otp")
def send_email_login_otp(payload: EmailSendOtpRequest, request: Request):
    clean_email = payload.email.strip().lower()
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    user = db_service.get_user_by_email(clean_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )

    user_role_str = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower().strip()
    if user_role_str != role_str.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account does not have permission for this role.",
        )

    appr_st = str(getattr(user, "approval_status", "APPROVED") or "APPROVED").upper().strip()
    if not user.is_active and appr_st not in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is currently inactive.")

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    ok, msg, _ = db_service.create_login_otp(clean_email, otp, expires_at)
    if not ok:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg)

    email_sent, email_msg = send_otp_email(clean_email, otp, user.name, settings.OTP_EXPIRE_MINUTES)
    if not email_sent and not settings.DEBUG:
        logger.error("[AUTH] [EMAIL] Failed to send login OTP to %s: %s", _mask_email(clean_email), email_msg)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to send verification email. Please try again later.")

    return {"message": "Login OTP has been sent to your email."}


@router.post("/email/verify-login-otp", response_model=Token)
def verify_email_login_otp(payload: EmailVerifyOtpRequest, request: Request):
    clean_email = payload.email.strip().lower()
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    user = db_service.get_user_by_email(clean_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_role_str = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower().strip()
    if user_role_str != role_str.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account does not have permission for this role.",
        )

    appr_st = str(getattr(user, "approval_status", "APPROVED") or "APPROVED").upper().strip()
    if not user.is_active and appr_st not in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is currently inactive.")

    ok, msg, verification = db_service.verify_login_otp_code(clean_email, payload.otp_code.strip())
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    access_expires = timedelta(days=30) if payload.remember_me else None
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token({"sub": str(user.id), "role": role_val}, access_expires)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    _log(user.id, "login_email_otp", request)
    return Token(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/resend-verification-otp")
def resend_verification_otp(payload: ResendOtpRequest):
    clean_email = str(payload.email).strip().lower()

    # 1. Check if user is already verified
    existing = db_service.get_user_by_email(clean_email)
    if existing and existing.is_email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified. Please login.")

    # 2. Check pending registration
    pending = db_service.get_pending_registration(clean_email)
    if pending:
        # Check cooldown
        last_sent = pending.get("last_sent_at")
        if isinstance(last_sent, datetime):
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
            cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS or 60
            if elapsed < cooldown:
                wait_sec = int(cooldown - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {wait_sec} seconds before requesting a new OTP.",
                )

        otp = generate_otp()
        hashed_otp = hash_otp(otp)
        logger.info("[AUTH] [OTP] New OTP generated for resend to %s", _mask_email(clean_email))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        pending["hashed_otp"] = hashed_otp
        pending["otp_code"] = otp
        pending["attempts"] = 0
        pending["last_sent_at"] = datetime.now(timezone.utc)
        pending["expires_at"] = expires_at
        db_service.save_pending_registration(pending)

        email_sent, email_msg = send_otp_email(clean_email, otp, pending.get("name", "User"), settings.OTP_EXPIRE_MINUTES)
        if not email_sent:
            if settings.APP_ENV != "production" or settings.DEBUG:
                logger.warning("[AUTH] [EMAIL] Dev mode: resend simulated for %s: %s", _mask_email(clean_email), email_msg)
            else:
                logger.error("[AUTH] [EMAIL] Failed to resend verification email to %s: %s", _mask_email(clean_email), email_msg)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to send verification email. Please try again later.",
                )
        return {"message": "Verification OTP resent successfully"}

    # 3. Fallback for legacy unverified user
    if existing and not existing.is_email_verified:
        otp = generate_otp()
        logger.info("[AUTH] [OTP] New OTP generated for resend to legacy user %s", _mask_email(clean_email))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        db_service.create_email_verification(existing.id, otp, expires_at)

        email_sent, email_msg = send_otp_email(existing.email, otp, existing.name, settings.OTP_EXPIRE_MINUTES)
        if not email_sent:
            if settings.APP_ENV != "production" or settings.DEBUG:
                logger.warning("[AUTH] [EMAIL] Dev mode: resend simulated for %s: %s", _mask_email(clean_email), email_msg)
            else:
                logger.error("[AUTH] [EMAIL] Failed to resend verification email to legacy user %s: %s", _mask_email(clean_email), email_msg)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to send verification email. Please try again later.",
                )
        return {"message": "Verification OTP resent successfully"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No pending registration found for this email. Please register first.",
    )


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request):
    clean_email = payload.email.strip().lower()
    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    user = db_service.get_user_by_email(clean_email)

    if not user or not verify_password(payload.password, user.hashed_password):
        _log(user.id if user else None, "login_failed", request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    user_role_str = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower().strip()
    if user_role_str != role_str.lower().strip():
        if user_role_str == "student" and role_str.lower().strip() in ["admin", "faculty"]:
            _log(user.id, "login_role_mismatch", request)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account does not have permission for this role.",
            )

    if not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email first")

    appr_st = str(getattr(user, "approval_status", "APPROVED") or "APPROVED").upper().strip()
    if not user.is_active:
        if appr_st not in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL", "REJECTED"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is currently inactive.",
            )

    # Migrate existing EventSphere password accounts into Firebase Authentication
    # on the first successful legacy login. Firebase becomes the long-term
    # credential provider without breaking existing users.
    try:
        firebase_user = None
        try:
            firebase_user = firebase_auth_admin.get_user_by_email(clean_email)
        except firebase_auth_admin.UserNotFoundError:
            firebase_user = None

        if firebase_user:
            firebase_auth_admin.update_user(
                firebase_user.uid,
                password=payload.password,
                email_verified=True,
                display_name=user.name,
            )
        else:
            firebase_auth_admin.create_user(
                email=clean_email,
                password=payload.password,
                email_verified=True,
                display_name=user.name,
            )
        logger.info("Firebase account synchronized after legacy password login for %s", _mask_email(clean_email))
    except Exception as e:
        logger.warning("Firebase account synchronization skipped for %s: %s", _mask_email(clean_email), e)

    access_expires = timedelta(days=30) if payload.remember_me else None
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token({"sub": str(user.id), "role": role_val}, access_expires)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    _log(user.id, "login_success", request)

    return Token(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/refresh", response_model=Token)
def refresh_token(payload: TokenRefreshRequest):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    resolved_id = int(user_id) if str(user_id).isdigit() else str(user_id)
    user = db_service.get_user_by_id(resolved_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    appr_st = str(getattr(user, "approval_status", "APPROVED") or "APPROVED").upper().strip()
    if not user.is_active and appr_st not in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token({"sub": str(user.id), "role": role_val})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})

    return Token(access_token=access_token, refresh_token=new_refresh_token, user=user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    clean_email = str(payload.email).strip().lower()
    user = db_service.get_user_by_email(clean_email)
    if not user:
        return {"message": "If that email exists, a reset OTP has been sent"}

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    db_service.create_password_reset(user.id, otp, expires_at)
    sent = send_password_reset_email(user.email, user.name, otp)
    if not sent and (settings.APP_ENV == "production" or (settings.RESEND_API_KEY and not settings.DEBUG)):
        logger.error("[AUTH] [EMAIL] Password reset email could not be sent to %s via Resend", _mask_email(user.email))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to send password reset email via Resend. Please try again later.",
        )

    return {"message": "If that email exists, a reset OTP has been sent"}


@router.post("/verify-reset-otp")
def verify_reset_otp(payload: VerifyResetOtpRequest):
    user = db_service.get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    reset = db_service.get_latest_password_reset(user.id, payload.otp_code)
    if not reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    exp = reset.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    return {"message": "OTP verified. You may now reset your password."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request):
    user = db_service.get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")

    reset = db_service.get_latest_password_reset(user.id, payload.otp_code)
    if not reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    exp = reset.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    db_service.update_user(user.id, {"hashed_password": hash_password(payload.new_password)})
    db_service.mark_password_reset_used(reset.id)

    _log(user.id, "password_reset", request)

    return {"message": "Password reset successfully"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
