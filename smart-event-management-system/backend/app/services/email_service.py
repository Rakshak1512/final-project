"""
Email Service for transactional emails exclusively via Gmail SMTP (smtplib).

Configured via environment variables in backend .env:
- SMTP_HOST: smtp.gmail.com (default)
- SMTP_PORT: 587 (default)
- SMTP_USER: smart.event.system2026@gmail.com
- SMTP_PASSWORD: 16-character Google App Password
- SMTP_FROM_NAME: EventSphere
- SMTP_FROM_EMAIL: smart.event.system2026@gmail.com
- SMTP_USE_TLS: True (STARTTLS)
"""
from datetime import datetime
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional, Tuple

import requests

from app.core.config import settings

logger = logging.getLogger("app.email")


def _mask_email(email: str) -> str:
    """Mask email for safe logging without exposing personal data (e.g. r***k@gmail.com)."""
    if not email or "@" not in email:
        return "***"
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + "*"
    else:
        masked_local = local_part[0] + "*" * (len(local_part) - 2) + local_part[-1]
    return f"{masked_local}@{domain}"


def _send_via_resend(
    to_addr: str, subject: str, html_body: str, text_body: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Send an email using Resend REST API (https://api.resend.com/emails).
    Returns (success: bool, detail: str).
    Never simulates successful delivery.
    """
    api_key = (settings.RESEND_API_KEY or "").strip()
    masked_to = _mask_email(to_addr)

    if not api_key:
        logger.error("[EMAIL] [RESEND] RESEND_API_KEY is not configured on the backend server for %s", masked_to)
        return False, "RESEND_API_KEY is not configured on the backend server."

    from_name = (settings.SMTP_FROM_NAME or settings.APP_NAME or "EventSphere").strip()
    from_email = (settings.RESEND_FROM_EMAIL or "onboarding@resend.dev").strip().strip("\"'")
    sender = f"{from_name} <{from_email}>"

    payload = {
        "from": sender,
        "to": [to_addr],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    logger.info("[EMAIL] [RESEND] Dispatching email to %s via Resend API (from: %s)", masked_to, sender)

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=12,
            )
            if response.status_code in (200, 201):
                msg_id = ""
                try:
                    res_json = response.json()
                    msg_id = res_json.get("id", "")
                except Exception:
                    pass
                logger.info("[EMAIL] [RESEND] Successfully accepted by Resend for %s (id: %s)", masked_to, msg_id)
                return True, "Email delivered successfully via Resend"

            err_detail = ""
            try:
                res_json = response.json()
                err_detail = res_json.get("message") or res_json.get("error") or ""
            except Exception:
                pass
            if not err_detail:
                err_detail = response.text[:200]

            logger.error(
                "[EMAIL] [RESEND] API error (HTTP %s) for %s (attempt %d): %s",
                response.status_code,
                masked_to,
                attempt + 1,
                err_detail,
            )

            if "domain" in err_detail.lower() or "verify" in err_detail.lower() or "onboarding@resend.dev" in err_detail.lower():
                err_detail += " (Note: When using onboarding@resend.dev, Resend only allows sending to the email registered on your Resend account. Verify a custom domain at resend.com/domains for unrestricted delivery.)"

            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue

            return False, f"Resend API error (HTTP {response.status_code}): {err_detail}"
        except Exception as e:
            logger.error("[EMAIL] [RESEND] Network error for %s (attempt %d): %s", masked_to, attempt + 1, str(e))
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return False, f"Network error connecting to Resend: {str(e)}"

    return False, "Unable to deliver email via Resend after retries."


def _send_via_smtp(
    to_addr: str, subject: str, html_body: str, text_body: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Send an email using Gmail SMTP via smtplib with STARTTLS on port 587.
    Returns (success: bool, detail: str).
    Never simulates successful delivery.
    """
    masked_to = _mask_email(to_addr)
    host = (settings.SMTP_HOST or "smtp.gmail.com").strip()
    port = int(settings.SMTP_PORT) if settings.SMTP_PORT else 587
    user = (settings.SMTP_USER or "smart.event.system2026@gmail.com").strip()
    password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip().strip("\"'")
    from_name = (settings.SMTP_FROM_NAME or settings.APP_NAME or "EventSphere").strip()
    from_email = (settings.SMTP_FROM_EMAIL or user or "smart.event.system2026@gmail.com").strip()

    if not user or not password:
        logger.error("[EMAIL] [SMTP] Credentials missing in backend .env for %s (user=%s, password_set=%s)", masked_to, _mask_email(user), bool(password))
        return False, "Gmail SMTP credentials not configured (SMTP_USER or SMTP_PASSWORD is empty in backend .env)."

    pass_len = len(password)
    sender_header = formataddr((from_name, from_email))
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_header
    msg["To"] = to_addr

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    logger.info(
        "[EMAIL] [SMTP] Connecting to Gmail SMTP %s:%s (TLS: %s, sender: %s, pass_length: %d) for %s",
        host, port, settings.SMTP_USE_TLS, _mask_email(user), pass_len, masked_to
    )
    if pass_len != 16:
        logger.warning(
            "[EMAIL] [SMTP] Diagnostic Warning: SMTP_PASSWORD length is %d characters (Google App Passwords must be exactly 16 characters).",
            pass_len
        )

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                try:
                    server.login(user, password)
                except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as auth_err:
                    hint = f" (detected password length: {pass_len} characters; Google App Passwords must be exactly 16 characters, not normal account password)" if pass_len != 16 else ""
                    logger.error("[EMAIL] [SMTP] Authentication failed for %s (sender: %s): %s", masked_to, _mask_email(user), str(auth_err))
                    return False, f"Gmail SMTP authentication failed. Google rejected the credentials (535 Bad Credentials). Please verify your 16-character Google App Password in backend .env.{hint}"
                server.sendmail(from_email, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls()
                    server.ehlo()
                try:
                    server.login(user, password)
                except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as auth_err:
                    hint = f" (detected password length: {pass_len} characters; Google App Passwords must be exactly 16 characters, not normal account password)" if pass_len != 16 else ""
                    logger.error("[EMAIL] [SMTP] Authentication failed for %s (sender: %s): %s", masked_to, _mask_email(user), str(auth_err))
                    return False, f"Gmail SMTP authentication failed. Google rejected the credentials (535 Bad Credentials). Please verify your 16-character Google App Password in backend .env.{hint}"
                server.sendmail(from_email, [to_addr], msg.as_string())

        logger.info("[EMAIL] [SMTP] Email successfully delivered to %s via Gmail SMTP (%s:%d)", masked_to, host, port)
        return True, "Email delivered successfully via Gmail SMTP"
    except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
        logger.error("[EMAIL] [SMTP] Connection failed to %s:%s for %s: %s", host, port, masked_to, str(e))
        return False, f"Could not connect to Gmail SMTP server ({host}:{port}): {str(e)}"
    except smtplib.SMTPAuthenticationError as e:
        err_code = getattr(e, "smtp_code", 535)
        logger.error("[EMAIL] [SMTP] Authentication failed for %s (code %s): %s", masked_to, err_code, str(e))
        hint = f" (detected password length: {pass_len} characters; Google App Passwords must be 16 chars)" if pass_len != 16 else ""
        return False, f"Gmail SMTP authentication failed. Please verify that your 16-character Google App Password is set correctly in backend .env.{hint}"
    except smtplib.SMTPServerDisconnected as e:
        logger.error("[EMAIL] [SMTP] Connection disconnected during SMTP delivery to %s: %s", masked_to, str(e))
        hint = f" (detected password length: {pass_len} characters; Google App Passwords must be 16 chars)" if pass_len != 16 else ""
        return False, f"Gmail SMTP authentication failed. Google rejected the credentials (535 Bad Credentials). Please verify your 16-character Google App Password in backend .env.{hint}"
    except Exception as e:
        logger.error("[EMAIL] [SMTP] Delivery failed for %s: %s", masked_to, str(e))
        return False, f"Gmail SMTP delivery failed: {str(e)}"


def test_smtp_connection() -> Tuple[bool, str]:
    """
    Diagnostic helper to verify Gmail SMTP authentication on smtp.gmail.com:587 with STARTTLS.
    Returns (success: bool, detail: str).
    Never logs or leaks credentials.
    """
    host = (settings.SMTP_HOST or "smtp.gmail.com").strip()
    port = int(settings.SMTP_PORT) if settings.SMTP_PORT else 587
    user = (settings.SMTP_USER or "smart.event.system2026@gmail.com").strip()
    password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip().strip("\"'")

    if not user or not password:
        return False, "Gmail SMTP credentials not configured (SMTP_USER or SMTP_PASSWORD is empty in backend .env)."

    pass_len = len(password)
    logger.info("[EMAIL] [DIAGNOSTIC] Testing Gmail SMTP connection for %s (host: %s:%d, pass_len: %d)", _mask_email(user), host, port, pass_len)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                server.login(user, password)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls()
                    server.ehlo()
                server.login(user, password)
        logger.info("[EMAIL] [DIAGNOSTIC] Gmail SMTP connection and authentication succeeded for %s", _mask_email(user))
        return True, "Gmail SMTP authentication successful"
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as e:
        hint = f" (detected password length: {pass_len} characters; Google App Passwords must be exactly 16 characters, not personal account password)" if pass_len != 16 else ""
        logger.error("[EMAIL] [DIAGNOSTIC] Authentication failed for %s: %s", _mask_email(user), str(e))
        return False, f"Gmail SMTP authentication failed: Google rejected the credentials (535 Bad Credentials). Please verify your 16-character Google App Password for {user} in backend .env.{hint}"
    except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
        logger.error("[EMAIL] [DIAGNOSTIC] Connection failed to %s:%s: %s", host, port, str(e))
        return False, f"Could not connect to Gmail SMTP server ({host}:{port}): {str(e)}"
    except Exception as e:
        logger.error("[EMAIL] [DIAGNOSTIC] Unexpected diagnostic error: %s", str(e))
        return False, f"Gmail SMTP test failed: {str(e)}"


def send_email_detailed(
    to_email: str, subject: str, html_body: str, text_body: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Primary email dispatch function.
    Defaults to Resend REST API (https://api.resend.com/emails).
    Supports Gmail SMTP when explicitly configured (EMAIL_PROVIDER=smtp).
    Never simulates fake successful delivery.
    """
    to_addr = (to_email or "").strip()
    if not to_addr:
        return False, "Recipient email address is required."

    provider = (settings.EMAIL_PROVIDER or "resend").lower().strip()
    if provider == "smtp":
        return _send_via_smtp(to_addr, subject, html_body, text_body)
    elif provider == "resend" or settings.is_resend_configured:
        return _send_via_resend(to_addr, subject, html_body, text_body)
    else:
        # Fallback check
        if settings.is_smtp_configured:
            return _send_via_smtp(to_addr, subject, html_body, text_body)
        return _send_via_resend(to_addr, subject, html_body, text_body)


def send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Send an email and return boolean status."""
    success, _ = send_email_detailed(to_email, subject, html_body, text_body)
    return success


def send_otp_email(
    to_email: str,
    otp: str,
    name: Optional[str] = None,
    expiry_minutes: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Send a 6-digit OTP verification email via Gmail SMTP.
    Returns (success: bool, message_or_error: str).
    """
    exp_mins = expiry_minutes or settings.OTP_EXPIRE_MINUTES or 5
    user_name = name or "User"
    subject = "EventSphere Email Verification OTP"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); padding: 32px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
        Event<span style="color: #cbd5e1;">Sphere</span>
      </h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    
    <!-- Body -->
    <div style="padding: 32px 28px;">
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc;">
        Email Verification OTP
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{user_name}</strong>,<br><br>
        Your EventSphere verification OTP is:
      </p>
      
      <!-- OTP Box -->
      <div style="background: rgba(99, 102, 241, 0.1); border: 1.5px dashed #818cf8; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
        <span style="font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #a5b4fc; font-family: 'Courier New', Courier, monospace; display: inline-block; padding-left: 10px;">
          {otp}
        </span>
      </div>
      
      <!-- Expiry Notice -->
      <div style="background: #0f172a; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px;">
        <p style="margin: 0; font-size: 13.5px; color: #cbd5e1;">
          This OTP expires in <strong>{exp_mins} minutes</strong>.
        </p>
      </div>
      
      <!-- Security Warning -->
      <p style="margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #f43f5e;">
        Do not share this OTP with anyone.
      </p>
      <p style="margin: 20px 0 0; font-size: 13.5px; line-height: 1.5; color: #94a3b8;">
        Regards,<br>
        <strong>EventSphere Team</strong>
      </p>
    </div>
    
    <!-- Footer -->
    <div style="background: #0f172a; padding: 18px 24px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        &copy; 2026 EventSphere. All rights reserved.<br>
        If you did not request this OTP, you can safely ignore this email.
      </p>
    </div>
  </div>
 </body>
</html>"""

    text_content = (
        f"Hello {user_name},\n\n"
        f"Your EventSphere verification OTP is:\n\n"
        f"{otp}\n\n"
        f"This OTP expires in {exp_mins} minutes.\n\n"
        f"Do not share this OTP with anyone.\n\n"
        f"Regards,\n"
        f"EventSphere Team"
    )

    return send_email_detailed(to_email, subject, html_content, text_content)


def send_verification_email(to_email: str, name: str, otp_code: str) -> bool:
    """Alias for send_otp_email for backward compatibility."""
    success, _ = send_otp_email(to_email, otp_code, name)
    return success


def send_password_reset_otp_email(
    to_email: str, name: str, otp_code: str, expiry_minutes: Optional[int] = None
) -> Tuple[bool, str]:
    """Send 6-digit password reset OTP email via Gmail SMTP."""
    exp_mins = expiry_minutes or settings.OTP_EXPIRE_MINUTES or 5
    user_name = name or "User"
    subject = f"{settings.APP_NAME} - Password Reset OTP"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); padding: 28px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff;">{settings.APP_NAME}</h1>
      <p style="margin: 4px 0 0; color: rgba(255,255,255,0.9); font-size: 13px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 24px;">
      <h2 style="margin: 0 0 12px; font-size: 19px; color: #f8fafc;">Password Reset OTP</h2>
      <p style="margin: 0 0 18px; font-size: 14px; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{user_name}</strong>,<br><br>
        We received a request to reset your EventSphere account password. Your 6-digit verification OTP is:
      </p>
      <div style="background: rgba(99, 102, 241, 0.1); border: 1.5px dashed #818cf8; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
        <span style="font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #a5b4fc; font-family: monospace; display: inline-block; padding-left: 10px;">
          {otp_code}
        </span>
      </div>
      <div style="background: #0f172a; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px;">
        <p style="margin: 0; font-size: 13px; color: #cbd5e1;">⏱️ This OTP expires in <strong>{exp_mins} minutes</strong>.</p>
      </div>
      <p style="margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #f43f5e;">
        Do not share this OTP with anyone.
      </p>
      <p style="margin: 16px 0 0; font-size: 12.5px; color: #64748b;">
        If you did not request a password reset, you can safely ignore this email.
      </p>
    </div>
  </div>
 </body>
</html>"""

    text_content = (
        f"EventSphere Password Reset OTP\n\n"
        f"Hello {user_name},\n\n"
        f"Your 6-digit password reset OTP is:\n\n"
        f"{otp_code}\n\n"
        f"This OTP expires in {exp_mins} minutes.\n\n"
        f"Do not share this OTP with anyone.\n\n"
        f"Regards,\n"
        f"EventSphere Team"
    )

    return send_email_detailed(to_email, subject, html_content, text_content)


def send_password_reset_email(to_email: str, name: str, otp_code: str) -> bool:
    """Send password verification 6-digit OTP email via Gmail SMTP (backward-compatible bool return)."""
    ok, _ = send_password_reset_otp_email(to_email, name, otp_code)
    return ok


def send_registration_confirmation_email(
    to_email: str,
    name: str,
    event_title: str,
    ticket_code: str,
    event_date: Optional[str] = None,
    event_time: Optional[str] = None,
    venue: Optional[str] = None,
) -> bool:
    """Send detailed event registration confirmation email via SMTP."""
    subject = f"Registration Confirmed: {event_title}"
    date_val = event_date or "To be announced"
    time_val = event_time or "To be announced"
    venue_val = venue or "Campus Venue"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 28px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff;">🎉 Registration Confirmed</h1>
      <p style="margin: 4px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{settings.APP_NAME}</p>
    </div>
    <div style="padding: 28px 24px;">
      <p style="margin: 0 0 16px; font-size: 15px; color: #f1f5f9;">Hello <strong>{name}</strong>,</p>
      <p style="margin: 0 0 20px; font-size: 14px; color: #94a3b8; line-height: 1.5;">
        You have successfully registered for <strong>{event_title}</strong>. Here are your event details:
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px; margin-bottom: 20px; border: 1px solid #334155;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr><td style="padding: 6px 0; color: #94a3b8; width: 110px;">Event:</td><td style="padding: 6px 0; color: #f8fafc; font-weight: 600;">{event_title}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Status:</td><td style="padding: 6px 0; color: #34d399; font-weight: 700;">Confirmed</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Ticket Code:</td><td style="padding: 6px 0; color: #a5b4fc; font-family: monospace; font-weight: 700; font-size: 15px;">#{ticket_code}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Date:</td><td style="padding: 6px 0; color: #f8fafc;">{date_val}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Time:</td><td style="padding: 6px 0; color: #f8fafc;">{time_val}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Venue:</td><td style="padding: 6px 0; color: #f8fafc;">{venue_val}</td></tr>
        </table>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: #cbd5e1; line-height: 1.5;">
        📌 <strong>Instructions:</strong> Please present your QR ticket or downloaded registration slip at the entrance for attendance verification.
      </p>
    </div>
  </div>
</body>
</html>"""
    text = f"Registration Confirmed for {event_title}\nTicket: #{ticket_code}\nDate: {date_val}\nTime: {time_val}\nVenue: {venue_val}"
    return send_email(to_email, subject, html, text)


def send_registration_approved_email(
    to_email: str,
    name: str,
    event_title: str,
    registration_number: Optional[str] = None,
    event_date: Optional[str] = None,
    venue: Optional[str] = None,
    ticket_code: Optional[str] = None,
) -> bool:
    """Send official registration approval notification email via SMTP."""
    subject = f"Registration Approved: {event_title}"
    date_val = event_date or "Campus Event Date"
    venue_val = venue or "Campus Venue"
    reg_val = registration_number or "N/A"
    ticket_val = ticket_code or "N/A"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 18px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.35);">
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 28px 24px; text-align: center;">
      <h2 style="margin: 0 0 6px; color: #ffffff; font-size: 22px;">🎉 Registration Approved!</h2>
      <p style="margin: 0; color: rgba(255,255,255,0.9); font-size: 14px;">EventSphere Smart Event System</p>
    </div>
    <div style="padding: 26px;">
      <p style="margin: 0 0 16px; font-size: 15px; color: #f1f5f9;">Hello <strong>{name}</strong>,</p>
      <p style="margin: 0 0 18px; font-size: 14px; color: #cbd5e1; line-height: 1.55;">
        Great news! Your registration for <strong>{event_title}</strong> has been officially approved by the faculty coordinator.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px; margin-bottom: 20px; border: 1px solid #334155;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr><td style="padding: 6px 0; color: #94a3b8; width: 120px;">Event:</td><td style="padding: 6px 0; color: #f8fafc; font-weight: 600;">{event_title}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Status:</td><td style="padding: 6px 0; color: #34d399; font-weight: 700;">Approved</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Register No:</td><td style="padding: 6px 0; color: #a5b4fc; font-family: monospace; font-weight: 700;">{reg_val}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Ticket / Pass:</td><td style="padding: 6px 0; color: #a5b4fc; font-family: monospace; font-weight: 700; font-size: 14px;">#{ticket_val}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Date:</td><td style="padding: 6px 0; color: #f8fafc;">{date_val}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Venue:</td><td style="padding: 6px 0; color: #f8fafc;">{venue_val}</td></tr>
        </table>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: #94a3b8; line-height: 1.5;">
        📌 <strong>Next Step:</strong> You can view your QR attendance ticket inside the EventSphere student portal and have it scanned at the entrance during the event.
      </p>
    </div>
  </div>
</body>
</html>"""
    text = f"Registration Approved for {event_title}\nRegister No: {reg_val}\nTicket: #{ticket_val}\nDate: {date_val}\nVenue: {venue_val}"
    return send_email(to_email, subject, html, text)


def send_certificate_uploaded_email(to_email: str, name: str, cert_title: str) -> bool:
    """Send certificate notification email via SMTP."""
    subject = f"New Certificate Available: {cert_title}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; padding: 28px 24px; text-align: center;">
    <h2 style="color: #a5b4fc; margin-top: 0;">🎓 Certificate Issued</h2>
    <p style="color: #cbd5e1; font-size: 14.5px;">Hi <strong>{name}</strong>, a new certificate titled <strong>{cert_title}</strong> has been uploaded to your account.</p>
    <p style="color: #94a3b8; font-size: 13px;">Log in to EventSphere to preview and download your certificate.</p>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"New Certificate: {cert_title}")


def send_registration_cancellation_email(
    to_email: str,
    name: str,
    event_title: str,
    reason: Optional[str] = None,
) -> bool:
    """Send event cancellation notification email via SMTP."""
    subject = f"Registration Cancelled: {event_title}"
    reason_text = reason or "Cancelled by event coordinator."

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 24px; text-align: center;">
      <h2 style="margin: 0; color: #ffffff;">Registration Update</h2>
    </div>
    <div style="padding: 24px;">
      <p style="margin: 0 0 14px; font-size: 14.5px; color: #f1f5f9;">Hello <strong>{name}</strong>,</p>
      <p style="margin: 0 0 16px; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
        Your registration for <strong>{event_title}</strong> has been cancelled.
      </p>
      <div style="background: #0f172a; padding: 14px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #334155;">
        <p style="margin: 0; font-size: 13px; color: #fca5a5;"><strong>Status:</strong> Cancelled</p>
        <p style="margin: 6px 0 0; font-size: 12.5px; color: #94a3b8;"><strong>Reason/Note:</strong> {reason_text}</p>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: #94a3b8;">
        If you have questions, please contact the event organizer or department faculty.
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Registration Cancelled for {event_title}. {reason_text}")


def send_attendance_confirmed_student_email(
    to_email: str,
    student_name: str,
    event_title: str,
    event_date: str,
    attendance_time: str,
    volunteer_name: str,
) -> bool:
    subject = f"Attendance Confirmed — {event_title}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 24px; text-align: center;">
      <h2 style="margin: 0; color: #ffffff;">✓ Attendance Confirmed</h2>
    </div>
    <div style="padding: 24px;">
      <p style="margin: 0 0 14px; font-size: 14.5px; color: #f1f5f9;">Hello <strong>{student_name}</strong>,</p>
      <p style="margin: 0 0 16px; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
        Your attendance has been successfully confirmed for:
      </p>
      <div style="background: #0f172a; padding: 16px; border-radius: 10px; margin-bottom: 16px; border: 1px solid #334155;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr><td style="padding: 5px 0; color: #94a3b8; width: 120px;">Event:</td><td style="padding: 5px 0; color: #f8fafc; font-weight: 600;">{event_title}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Date:</td><td style="padding: 5px 0; color: #f8fafc;">{event_date}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Attendance Time:</td><td style="padding: 5px 0; color: #34d399; font-weight: 600;">{attendance_time}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Confirmed by:</td><td style="padding: 5px 0; color: #a5b4fc;">{volunteer_name}</td></tr>
        </table>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: #94a3b8;">
        Thank you,<br>EventSphere Team
      </p>
    </div>
  </div>
</body>
</html>"""
    text = f"Hello {student_name},\n\nYour attendance has been successfully confirmed for:\nEvent: {event_title}\nDate: {event_date}\nAttendance Time: {attendance_time}\nConfirmed by: {volunteer_name}\n\nThank you,\nEventSphere"
    return send_email(to_email, subject, html, text)


def send_attendance_confirmed_faculty_email(
    to_email: str,
    faculty_name: str,
    student_name: str,
    registration_number: str,
    event_title: str,
    attendance_time: str,
    volunteer_name: str,
) -> bool:
    subject = f"Student Attendance Confirmed — {event_title}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
    <div style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); padding: 24px; text-align: center;">
      <h2 style="margin: 0; color: #ffffff;">Attendee Check-in Notification</h2>
    </div>
    <div style="padding: 24px;">
      <p style="margin: 0 0 14px; font-size: 14.5px; color: #f1f5f9;">Dear <strong>{faculty_name}</strong>,</p>
      <p style="margin: 0 0 16px; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
        A student has checked in for your event:
      </p>
      <div style="background: #0f172a; padding: 16px; border-radius: 10px; margin-bottom: 16px; border: 1px solid #334155;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr><td style="padding: 5px 0; color: #94a3b8; width: 120px;">Student:</td><td style="padding: 5px 0; color: #f8fafc; font-weight: 600;">{student_name}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Registration No:</td><td style="padding: 5px 0; color: #f8fafc;">{registration_number}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Event:</td><td style="padding: 5px 0; color: #f8fafc;">{event_title}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Check-in Time:</td><td style="padding: 5px 0; color: #34d399; font-weight: 600;">{attendance_time}</td></tr>
          <tr><td style="padding: 5px 0; color: #94a3b8;">Checked in by:</td><td style="padding: 5px 0; color: #a5b4fc;">{volunteer_name}</td></tr>
        </table>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: #94a3b8;">
        EventSphere Automated System
      </p>
    </div>
  </div>
</body>
</html>"""
    text = f"Student Attendance Confirmed\nStudent: {student_name} ({registration_number})\nEvent: {event_title}\nTime: {attendance_time}\nVolunteer: {volunteer_name}"
    return send_email(to_email, subject, html, text)


def send_faculty_work_assigned_email(
    to_email: str,
    faculty_name: str,
    task_title: str,
    description: str,
    priority: str = "Medium",
    deadline: Optional[str] = None,
    event_title: Optional[str] = None,
    assigned_by_name: str = "Administrator / Principal",
    portal_link: Optional[str] = None,
) -> bool:
    """
    Dispatches task assignment notification email from Admin to Faculty member.
    Fails gracefully if SMTP is not configured.
    """
    subject = f"New Work Assignment: {task_title}"
    link = portal_link or f"{settings.FRONTEND_URL}/faculty/dashboard"
    deadline_str = deadline or "As soon as possible"
    event_row = f'<tr><td style="padding: 6px 0; color: #94a3b8; width: 120px;">Associated Event:</td><td style="padding: 6px 0; color: #f8fafc; font-weight: 600;">{event_title}</td></tr>' if event_title else ""

    p_color = "#38bdf8" if priority.lower() == "low" else "#f59e0b" if priority.lower() == "medium" else "#ef4444"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 540px; margin: 0 auto; background: #1e293b; border-radius: 18px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); padding: 28px 24px; text-align: center;">
      <h2 style="margin: 0; color: #ffffff; font-size: 20px;">Faculty Work Assignment</h2>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.85); font-size: 13px;">Assigned by {assigned_by_name}</p>
    </div>
    <div style="padding: 26px 24px;">
      <p style="margin: 0 0 14px; font-size: 15px; color: #f1f5f9;">Dear <strong>Prof. {faculty_name}</strong>,</p>
      <p style="margin: 0 0 18px; font-size: 14px; color: #cbd5e1; line-height: 1.5;">
        You have been assigned a new administrative task by <strong>{assigned_by_name}</strong>. Please review the assignment details below:
      </p>

      <div style="background: #0f172a; padding: 18px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr><td style="padding: 6px 0; color: #94a3b8; width: 120px;">Task Title:</td><td style="padding: 6px 0; color: #f8fafc; font-weight: 700;">{task_title}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8; vertical-align: top;">Description:</td><td style="padding: 6px 0; color: #cbd5e1; line-height: 1.4;">{description}</td></tr>
          {event_row}
          <tr><td style="padding: 6px 0; color: #94a3b8;">Priority:</td><td style="padding: 6px 0; color: {p_color}; font-weight: 700; text-transform: uppercase;">{priority}</td></tr>
          <tr><td style="padding: 6px 0; color: #94a3b8;">Deadline:</td><td style="padding: 6px 0; color: #34d399; font-weight: 600;">{deadline_str}</td></tr>
        </table>
      </div>

      <div style="text-align: center; margin-bottom: 22px;">
        <a href="{link}" style="display: inline-block; background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 10px; font-size: 14px; font-weight: 600; box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);">
          Open Faculty Dashboard
        </a>
      </div>

      <p style="margin: 0; font-size: 12px; color: #94a3b8; text-align: center;">
        EventSphere Academic & Event Administration System
      </p>
    </div>
  </div>
</body>
</html>"""
    text = f"Dear Prof. {faculty_name},\n\nYou have been assigned a new task: {task_title}\n\nDescription: {description}\nPriority: {priority}\nDeadline: {deadline_str}\nAssigned by: {assigned_by_name}\n\nView on Portal: {link}"
    return send_email(to_email, subject, html, text)


def send_account_pending_approval_email(to_email: str, name: str, role: str) -> bool:
    """Send alert that account is verified and waiting for institutional approval."""
    role_str = str(role).capitalize()
    approver = "Faculty" if role.lower() == "student" else "Admin"
    subject = f"EventSphere Account Created — Waiting for {approver} Approval"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; padding: 28px 24px; text-align: center;">
    <h2 style="color: #38bdf8; margin-top: 0;">⏳ Account Awaiting Approval</h2>
    <p style="color: #cbd5e1; font-size: 15px;">Hello <strong>{name}</strong>,</p>
    <p style="color: #94a3b8; font-size: 14px; line-height: 1.55;">
      Your email has been successfully verified! Your <strong>{role_str}</strong> account registration is currently waiting for approval by your <strong>{approver}</strong>.
    </p>
    <div style="background: #0f172a; padding: 14px; border-radius: 10px; margin: 18px 0; border: 1px solid #334155;">
      <p style="margin: 0; font-size: 13px; color: #cbd5e1;">Status: <strong style="color: #fbbf24;">Pending Approval</strong></p>
    </div>
    <p style="color: #64748b; font-size: 12px; margin: 0;">You will receive an email as soon as your account is approved.</p>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Hello {name}, your EventSphere account is awaiting {approver} approval.")


def send_student_approved_email(to_email: str, name: str, uucms_id: Optional[str] = None) -> bool:
    """Send student account approval notification email via Gmail SMTP."""
    subject = "Your EventSphere student account has been approved."
    login_url = f"{settings.FRONTEND_URL}/login"
    dashboard_url = f"{settings.FRONTEND_URL}/student/dashboard"
    uucms_display = uucms_id or "Recorded with Faculty"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #d1fae5;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 20px; color: #34d399; font-weight: 700; font-size: 13px;">
          ✓ STATUS: APPROVED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        Your Student Account Has Been Approved!
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{name}</strong>,<br>
        Great news! Your EventSphere student registration has been successfully verified and approved by the faculty coordinators.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Student Name:</td>
            <td style="color: #f1f5f9; font-weight: 600; text-align: right; padding: 4px 0;">{name}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">UUCMS ID:</td>
            <td style="color: #38bdf8; font-family: monospace; font-weight: 600; text-align: right; padding: 4px 0;">{uucms_display}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Approval Status:</td>
            <td style="color: #34d399; font-weight: 700; text-align: right; padding: 4px 0;">APPROVED</td>
          </tr>
        </table>
      </div>
      <div style="background: rgba(99, 102, 241, 0.08); border-left: 3px solid #6366f1; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px;">
        <p style="margin: 0; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
          <strong>Login Instruction:</strong> Sign in with your registered email and password to access the student dashboard, register for campus events, and manage tickets.
        </p>
      </div>
      <div style="text-align: center; margin: 24px 0 10px;">
        <a href="{dashboard_url}" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; text-decoration: none; padding: 13px 32px; border-radius: 10px; font-weight: 700; font-size: 14.5px; display: inline-block;">
          Open Student Dashboard &rarr;
        </a>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • Institutional Academic Administration
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Hello {name}, your EventSphere student account ({uucms_display}) has been APPROVED. Log in at {login_url}")


def send_student_rejected_email(to_email: str, name: str, reason: Optional[str] = None) -> bool:
    """Send student account rejection notification email via Gmail SMTP."""
    subject = "Update Regarding Your EventSphere Student Account"
    reason_txt = reason or "Verification details could not be validated against official institutional records."

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #fee2e2;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 20px; color: #f87171; font-weight: 700; font-size: 13px;">
          STATUS: REJECTED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        Update Regarding Your Student Account
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{name}</strong>,<br>
        Your application for an EventSphere student account was reviewed by faculty coordinators and could not be approved at this time.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <p style="margin: 0 0 8px; font-size: 13px; color: #64748b; font-weight: 600;">
          REASON FOR REJECTION:
        </p>
        <p style="margin: 0; font-size: 14px; color: #f87171; font-weight: 500; line-height: 1.5;">
          {reason_txt}
        </p>
      </div>
      <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid #334155; padding: 14px 16px; border-radius: 8px;">
        <p style="margin: 0; font-size: 13px; color: #cbd5e1; line-height: 1.5;">
          <strong>Contact Information:</strong> If you believe this decision is in error, please contact your department faculty coordinator or head of department with your valid institutional credentials.
        </p>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • Institutional Academic Administration
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Hello {name}, your EventSphere student registration could not be approved. Reason: {reason_txt}")


def send_faculty_approved_email(to_email: str, name: str, faculty_id: Optional[str] = None) -> bool:
    """Send faculty account approval notification email via Gmail SMTP."""
    subject = "Your EventSphere faculty account has been approved."
    login_url = f"{settings.FRONTEND_URL}/login"
    dashboard_url = f"{settings.FRONTEND_URL}/faculty/dashboard"
    fac_id_display = faculty_id or "Recorded with Admin"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #6366f1 0%, #4338ca 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #c7d2fe;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(99, 102, 241, 0.15); border: 1px solid #6366f1; border-radius: 20px; color: #a5b4fc; font-weight: 700; font-size: 13px;">
          ✓ STATUS: APPROVED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        Your Faculty Account Has Been Approved!
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Dear <strong style="color: #f1f5f9;">Prof. {name}</strong>,<br>
        Your EventSphere Faculty Coordinator account has been verified and approved by the System Administrator.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Faculty Name:</td>
            <td style="color: #f1f5f9; font-weight: 600; text-align: right; padding: 4px 0;">{name}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Faculty ID:</td>
            <td style="color: #38bdf8; font-family: monospace; font-weight: 600; text-align: right; padding: 4px 0;">{fac_id_display}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Approval Status:</td>
            <td style="color: #34d399; font-weight: 700; text-align: right; padding: 4px 0;">APPROVED</td>
          </tr>
        </table>
      </div>
      <div style="background: rgba(99, 102, 241, 0.08); border-left: 3px solid #6366f1; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px;">
        <p style="margin: 0; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
          <strong>Login Instruction:</strong> Log in using your email and password to access the Faculty Dashboard, review pending student registrations, and manage campus events.
        </p>
      </div>
      <div style="text-align: center; margin: 24px 0 10px;">
        <a href="{dashboard_url}" style="background: linear-gradient(135deg, #6366f1 0%, #4338ca 100%); color: #ffffff; text-decoration: none; padding: 13px 32px; border-radius: 10px; font-weight: 700; font-size: 14.5px; display: inline-block;">
          Access Faculty Dashboard &rarr;
        </a>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • System Administration Directorate
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Dear Prof. {name}, your EventSphere faculty account ({fac_id_display}) has been approved! Visit {login_url}")


def send_faculty_rejected_email(to_email: str, name: str, reason: Optional[str] = None) -> bool:
    """Send faculty account rejection notification email via Gmail SMTP."""
    subject = "Update Regarding Your EventSphere Faculty Account"
    reason_txt = reason or "Faculty institutional credentials could not be verified by the System Administrator."

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #fee2e2;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 20px; color: #f87171; font-weight: 700; font-size: 13px;">
          STATUS: REJECTED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        Update Regarding Your Faculty Account
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Dear <strong style="color: #f1f5f9;">Prof. {name}</strong>,<br>
        Your application for an EventSphere Faculty Coordinator account was reviewed by the System Administrator and could not be approved at this time.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <p style="margin: 0 0 8px; font-size: 13px; color: #64748b; font-weight: 600;">
          REASON FOR REJECTION:
        </p>
        <p style="margin: 0; font-size: 14px; color: #f87171; font-weight: 500; line-height: 1.5;">
          {reason_txt}
        </p>
      </div>
      <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid #334155; padding: 14px 16px; border-radius: 8px;">
        <p style="margin: 0; font-size: 13px; color: #cbd5e1; line-height: 1.5;">
          <strong>Contact Information:</strong> If you believe this decision is in error, please contact the System Administrator / Principal to verify your institutional appointment.
        </p>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • System Administration Directorate
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Dear Prof. {name}, your EventSphere faculty registration was not approved. Reason: {reason_txt}")


def send_admin_new_faculty_alert_email(admin_email: str, faculty_name: str, faculty_email: str, department: Optional[str] = None) -> bool:
    """Alert administrator of new faculty registration needing approval."""
    subject = f"Action Required: New Faculty Registration ({faculty_name})"
    admin_url = f"{settings.FRONTEND_URL}/admin/faculty"
    dept_str = department or "Not Specified"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; padding: 28px 24px;">
    <h2 style="color: #fbbf24; margin-top: 0; text-align: center;">⚠️ Faculty Approval Required</h2>
    <p style="color: #cbd5e1; font-size: 14px;">A new faculty member has verified their email and is awaiting admin approval:</p>
    <div style="background: #0f172a; padding: 16px; border-radius: 10px; border: 1px solid #334155; font-size: 13.5px; margin: 16px 0;">
      <p style="margin: 4px 0; color: #cbd5e1;"><strong>Name:</strong> {faculty_name}</p>
      <p style="margin: 4px 0; color: #cbd5e1;"><strong>Email:</strong> {faculty_email}</p>
      <p style="margin: 4px 0; color: #cbd5e1;"><strong>Department:</strong> {dept_str}</p>
    </div>
    <div style="text-align: center; margin-top: 20px;">
      <a href="{admin_url}" style="background: #3b82f6; color: #ffffff; text-decoration: none; padding: 11px 24px; border-radius: 8px; font-weight: 600; display: inline-block;">
        Review & Approve in Admin Portal
      </a>
    </div>
  </div>
</body>
</html>"""
    return send_email(admin_email, subject, html, f"New Faculty awaiting approval: {faculty_name} ({faculty_email})")


def send_volunteer_approved_email(to_email: str, name: str, volunteer_id: Optional[str] = None) -> bool:
    """Send volunteer account approval notification email via Gmail SMTP."""
    subject = "Your EventSphere volunteer account has been approved."
    login_url = f"{settings.FRONTEND_URL}/login"
    dashboard_url = f"{settings.FRONTEND_URL}/volunteer/dashboard"
    vol_id_display = volunteer_id or "Recorded with Faculty"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #99f6e4;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(13, 148, 136, 0.15); border: 1px solid #0d9488; border-radius: 20px; color: #5eead4; font-weight: 700; font-size: 13px;">
          ✓ STATUS: APPROVED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        Your Volunteer Account Has Been Approved!
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{name}</strong>,<br>
        Great news! Your EventSphere volunteer account has been verified and approved by the faculty coordinators.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Volunteer Name:</td>
            <td style="color: #f1f5f9; font-weight: 600; text-align: right; padding: 4px 0;">{name}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Volunteer ID:</td>
            <td style="color: #38bdf8; font-family: monospace; font-weight: 600; text-align: right; padding: 4px 0;">{vol_id_display}</td>
          </tr>
          <tr>
            <td style="color: #64748b; padding: 4px 0;">Approval Status:</td>
            <td style="color: #34d399; font-weight: 700; text-align: right; padding: 4px 0;">APPROVED</td>
          </tr>
        </table>
      </div>
      <div style="background: rgba(13, 148, 136, 0.08); border-left: 3px solid #0d9488; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px;">
        <p style="margin: 0; font-size: 13.5px; color: #cbd5e1; line-height: 1.5;">
          <strong>Login Instruction:</strong> Sign in with your registered email and password to access the Volunteer Dashboard, scan QR tickets, and assist in event coordination.
        </p>
      </div>
      <div style="text-align: center; margin: 24px 0 10px;">
        <a href="{dashboard_url}" style="background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); color: #ffffff; text-decoration: none; padding: 13px 32px; border-radius: 10px; font-weight: 700; font-size: 14.5px; display: inline-block;">
          Open Volunteer Dashboard &rarr;
        </a>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • Student & Volunteer Activities Board
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Hello {name}, your EventSphere volunteer account ({vol_id_display}) has been APPROVED. Log in at {login_url}")


def send_volunteer_rejected_email(to_email: str, name: str, reason: Optional[str] = None) -> bool:
    """Send volunteer account rejection notification email via Gmail SMTP."""
    subject = "EventSphere Volunteer Account Update"
    reason_txt = reason or "Volunteer credentials could not be validated by institutional coordinators."

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 16px; color: #f8fafc;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ffffff;">Event<span style="color: #fee2e2;">Sphere</span></h1>
      <p style="margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Smart Event Management System</p>
    </div>
    <div style="padding: 30px 26px;">
      <div style="text-align: center; margin-bottom: 18px;">
        <span style="display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 20px; color: #f87171; font-weight: 700; font-size: 13px;">
          STATUS: REJECTED
        </span>
      </div>
      <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #f8fafc; text-align: center;">
        EventSphere Volunteer Account Update
      </h2>
      <p style="margin: 0 0 20px; font-size: 14.5px; line-height: 1.6; color: #94a3b8;">
        Hello <strong style="color: #f1f5f9;">{name}</strong>,<br>
        Your application for an EventSphere volunteer account was reviewed by faculty coordinators and could not be approved at this time.
      </p>
      <div style="background: #0f172a; border-radius: 12px; padding: 18px 20px; border: 1px solid #334155; margin-bottom: 22px;">
        <p style="margin: 0 0 8px; font-size: 13px; color: #64748b; font-weight: 600;">
          REASON FOR REJECTION:
        </p>
        <p style="margin: 0; font-size: 14px; color: #f87171; font-weight: 500; line-height: 1.5;">
          {reason_txt}
        </p>
      </div>
      <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid #334155; padding: 14px 16px; border-radius: 8px;">
        <p style="margin: 0; font-size: 13px; color: #cbd5e1; line-height: 1.5;">
          <strong>Contact Information:</strong> If you believe this decision is in error, please consult your department faculty coordinator.
        </p>
      </div>
    </div>
    <div style="background: #0f172a; padding: 16px 28px; text-align: center; border-top: 1px solid #334155;">
      <p style="margin: 0; font-size: 12px; color: #64748b;">
        © {datetime.now().year} EventSphere • Student & Volunteer Activities Board
      </p>
    </div>
  </div>
</body>
</html>"""
    return send_email(to_email, subject, html, f"Hello {name}, your EventSphere volunteer application was not approved. Reason: {reason_txt}")



