"""
Unit and Integration Tests for Gmail SMTP Email Authentication and OTP Workflows
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
    _mask_email,
)
from app.core.security import generate_otp, hash_otp, verify_otp_hash


class TestSMTPEmailAuth(unittest.TestCase):

    def test_mask_email_utility(self):
        """Verifies emails are securely masked in logs without leaking user identity."""
        self.assertEqual(_mask_email(""), "***")
        self.assertEqual(_mask_email("invalid"), "***")
        self.assertEqual(_mask_email("ab@gmail.com"), "a*@gmail.com")
        self.assertEqual(_mask_email("rakshak@gmail.com"), "r*****k@gmail.com")

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

        with patch.object(settings, "SMTP_USER", "smart.event.system2026@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcd efgh ijkl mnop"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587), \
             patch.object(settings, "SMTP_USE_TLS", True):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertTrue(ok)
            self.assertIn("Email delivered successfully via Gmail SMTP", msg)

            mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("smart.event.system2026@gmail.com", "abcdefghijklmnop")
            mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_smtp_auth_failure_never_fakes_success(self, mock_smtp_class):
        """Ensures that SMTPAuthenticationError returns False with actionable error details."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Invalid Credentials")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "smart.event.system2026@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "wrongpassword1234"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertFalse(ok)
            self.assertIn("Gmail SMTP authentication failed", msg)

    @patch("smtplib.SMTP")
    def test_registration_confirmation_via_smtp(self, mock_smtp_class):
        """Verifies send_registration_confirmation_email dispatches via SMTP."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "SMTP_USER", "smart.event.system2026@gmail.com"), \
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


if __name__ == "__main__":
    unittest.main()

