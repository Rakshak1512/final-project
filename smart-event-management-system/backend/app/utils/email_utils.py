"""
Email utilities bridge forwarding calls to app.services.email_service (SMTP).
"""
from app.services.email_service import (
    send_certificate_uploaded_email,
    send_email,
    send_email_detailed,
    send_otp_email,
    send_password_reset_email,
    send_password_reset_otp_email,
    send_registration_approved_email,
    send_registration_cancellation_email,
    send_registration_confirmation_email,
    send_verification_email,
    test_smtp_connection,
)

__all__ = [
    "send_email",
    "send_email_detailed",
    "send_otp_email",
    "send_verification_email",
    "send_password_reset_email",
    "send_password_reset_otp_email",
    "send_registration_confirmation_email",
    "send_registration_approved_email",
    "send_certificate_uploaded_email",
    "send_registration_cancellation_email",
    "test_smtp_connection",
]
