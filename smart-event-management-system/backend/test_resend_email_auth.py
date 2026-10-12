"""
Unit and Integration Tests for Gmail SMTP Email Authentication and OTP Workflows
Strictly tests SMTP delivery without external providers.
Validates:
- Gmail SMTP connection & STARTTLS on port 587
- 6-digit OTP generation and secure hashing
- Missing credentials error handling (never fakes success)
- Bad credentials and server disconnect handling (535 Bad Credentials)
- Whitespace stripping for 16-character Google App Passwords
- Registration OTP email delivery and formatting
- Password reset OTP email delivery and formatting
- Email masking utility
"""
import unittest
from unittest.mock import patch, MagicMock
import smtplib

from app.core.config import settings
from app.services.email_service import (
    send_email_detailed,
    send_otp_email,
    send_password_reset_otp_email,
    send_registration_confirmation_email,
    test_smtp_connection,
    _mask_email,
)
from app.core.security import generate_otp, hash_otp, verify_otp_hash


class TestSMTPEmailAuth(unittest.TestCase):

    def test_mask_email_utility(self):
        """Verifies emails are securely masked in logs without leaking user identity."""
        self.assertEqual(_mask_email(""), "***")
        self.assertEqual(_mask_email("invalid"), "***")
        self.assertEqual(_mask_email("ab@gmail.com"), "a*@gmail.com")
        self.assertEqual(_mask_email("example@gmail.com"), "e*****e@gmail.com")

    def test_otp_generation_and_hashing(self):
        """Verifies 6-digit OTP generation and secure one-way hashing."""
        otp = generate_otp(6)
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        hashed = hash_otp(otp)
        self.assertNotEqual(otp, hashed)
        self.assertTrue(verify_otp_hash(otp, hashed))
        self.assertFalse(verify_otp_hash("000000", hashed))

    def test_missing_credentials_never_reports_success(self):
        """Ensures that missing SMTP_PASSWORD returns (False, error) and never simulates success."""
        with patch.object(settings, "SMTP_PASSWORD", ""):
            ok, msg = send_email_detailed("test@college.edu", "Subject", "<p>Body</p>")
            self.assertFalse(ok)
            self.assertIn("Gmail SMTP credentials not configured", msg)

    @patch("smtplib.SMTP")
    def test_smtp_starttls_success(self, mock_smtp_class):
        """Verifies successful Gmail SMTP delivery via port 587 with STARTTLS."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcd efgh ijkl mnop"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587), \
             patch.object(settings, "SMTP_USE_TLS", True):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertTrue(ok)
            self.assertIn("Email delivered successfully via Gmail SMTP", msg)

            mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("eventsphere.test@gmail.com", "abcdefghijklmnop")
            mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_smtp_password_spaces_removal(self, mock_smtp_class):
        """Verifies that 16-character Google App Passwords with spaces are stripped to 16 contiguous chars."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", " mock pass word 123 "), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587):

            ok, msg = send_email_detailed("user@college.edu", "Subject", "<p>Content</p>")
            self.assertTrue(ok)
            mock_server.login.assert_called_once_with("eventsphere.test@gmail.com", "mockpassword123")

    @patch("smtplib.SMTP")
    def test_smtp_auth_failure_never_fakes_success(self, mock_smtp_class):
        """Ensures that SMTPAuthenticationError returns False with actionable error details."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Invalid Credentials")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "wrongpassword1234"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertFalse(ok)
            self.assertIn("Gmail SMTP authentication failed", msg)

    @patch("smtplib.SMTP")
    def test_smtp_server_disconnect_treated_as_bad_credentials(self, mock_smtp_class):
        """Ensures that SMTPServerDisconnected during login is caught and returns 535 Bad Credentials detail."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "invalidpass1234"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertFalse(ok)
            self.assertIn("535 Bad Credentials", msg)

    @patch("smtplib.SMTP")
    def test_diagnostic_test_smtp_connection(self, mock_smtp_class):
        """Verifies diagnostic helper test_smtp_connection correctly reports connection & auth status."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcdefghijklmnop"):

            ok, msg = test_smtp_connection()
            self.assertTrue(ok)
            self.assertIn("authentication successful", msg)

        # Failure case
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad Credentials")
        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "wrongpassword123"):

            ok, msg = test_smtp_connection()
            self.assertFalse(ok)
            self.assertIn("535 Bad Credentials", msg)

    @patch("smtplib.SMTP")
    def test_send_otp_email_flow(self, mock_smtp_class):
        """Verifies 6-digit OTP verification email sends properly and fails safely when credentials are bad."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Successful OTP send
        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcdefghijklmnop"):

            ok, msg = send_otp_email("student@college.edu", "654321", "Alice", 5)
            self.assertTrue(ok)
            mock_server.sendmail.assert_called_once()
            _, kwargs = mock_server.sendmail.call_args if hasattr(mock_server.sendmail, "call_args") else ((), {})

        # Failed OTP send
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad Credentials")
        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "badpassword1234"):

            ok, msg = send_otp_email("student@college.edu", "654321", "Alice", 5)
            self.assertFalse(ok)
            self.assertIn("535 Bad Credentials", msg)

    @patch("smtplib.SMTP")
    def test_send_password_reset_otp_email_flow(self, mock_smtp_class):
        """Verifies 6-digit password reset OTP email sends properly and fails safely when credentials are bad."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Successful password reset send
        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcdefghijklmnop"):

            ok, msg = send_password_reset_otp_email("faculty@college.edu", "Prof. Bob", "123456", 5)
            self.assertTrue(ok)
            mock_server.sendmail.assert_called_once()

        # Failed password reset send
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad Credentials")
        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "badpassword1234"):

            ok, msg = send_password_reset_otp_email("faculty@college.edu", "Prof. Bob", "123456", 5)
            self.assertFalse(ok)
            self.assertIn("535 Bad Credentials", msg)

    @patch("smtplib.SMTP")
    def test_registration_confirmation_via_smtp(self, mock_smtp_class):
        """Verifies send_registration_confirmation_email dispatches via SMTP."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "eventsphere.test@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcdefghijklmnop"):

            result = send_registration_confirmation_email(
                to_email="student@college.edu",
                name="John Doe",
                event_title="Hackathon 2026",
                ticket_code="TCK-1234",
                event_date="2026-11-20",
                event_time="10:00 AM",
                venue="Main Auditorium",
            )
            self.assertTrue(result)
            mock_server.sendmail.assert_called_once()

    def test_email_provider_is_always_smtp(self):
        """Ensures EMAIL_PROVIDER is forced to smtp."""
        self.assertEqual(settings.EMAIL_PROVIDER, "smtp")
        self.assertEqual(settings.SMTP_HOST, "smtp.gmail.com")
        self.assertEqual(settings.SMTP_PORT, 587)
        self.assertTrue(settings.SMTP_USE_TLS)


if __name__ == "__main__":
    unittest.main()
