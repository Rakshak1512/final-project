"""
Unit and Integration Tests for Resend Email Authentication and OTP Workflows
Validates:
- Resend REST API delivery and status code verification
- Domain & sender configuration requirements
- 6-digit OTP generation and secure hashing
- Missing credentials error handling (never fakes success)
- Error details extraction from Resend API
- SMTP secondary fallback mode
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


class TestResendEmailAuth(unittest.TestCase):

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

    def test_missing_resend_api_key_never_reports_success(self):
        """Ensures that missing RESEND_API_KEY returns (False, error) and never simulates success."""
        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", ""):
            ok, msg = send_email_detailed("test@college.edu", "Subject", "<p>Body</p>")
            self.assertFalse(ok)
            self.assertIn("RESEND_API_KEY is not configured", msg)

    @patch("requests.post")
    def test_resend_http_api_success(self, mock_post):
        """Verifies successful Resend delivery via HTTP POST returning message id."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_msg_12345"}
        mock_post.return_value = mock_resp

        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", "re_test_key_123"), \
             patch.object(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertTrue(ok)
            self.assertIn("Email delivered successfully via Resend", msg)

            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(args[0], "https://api.resend.com/emails")
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test_key_123")
            self.assertEqual(kwargs["json"]["to"], ["user@college.edu"])

    @patch("requests.post")
    def test_resend_http_api_failure_never_fakes_success(self, mock_post):
        """Ensures that Resend API errors return False with the exact error details."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"message": "Domain not verified"}
        mock_resp.text = '{"message": "Domain not verified"}'
        mock_post.return_value = mock_resp

        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", "re_test_key_123"):

            ok, msg = send_email_detailed("user@college.edu", "Test Subject", "<p>Hello</p>")
            self.assertFalse(ok)
            self.assertIn("Domain not verified", msg)

    @patch("requests.post")
    def test_resend_otp_email_flow(self, mock_post):
        """Verifies 6-digit OTP email dispatches via Resend API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_otp_98765"}
        mock_post.return_value = mock_resp

        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", "re_test_key_123"):

            ok, msg = send_otp_email("student@college.edu", "654321", "Alice", 5)
            self.assertTrue(ok)
            self.assertIn("delivered successfully via Resend", msg)
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertIn("654321", kwargs["json"]["html"])

    @patch("requests.post")
    def test_resend_password_reset_otp_flow(self, mock_post):
        """Verifies password reset OTP email dispatches via Resend API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_reset_11223"}
        mock_post.return_value = mock_resp

        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", "re_test_key_123"):

            ok, msg = send_password_reset_otp_email("faculty@college.edu", "Prof. Bob", "123456", 5)
            self.assertTrue(ok)
            self.assertIn("delivered successfully via Resend", msg)
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertIn("123456", kwargs["json"]["html"])

    @patch("requests.post")
    def test_registration_confirmation_via_resend(self, mock_post):
        """Verifies send_registration_confirmation_email returns boolean status via Resend."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_confirm_999"}
        mock_post.return_value = mock_resp

        with patch.object(settings, "EMAIL_PROVIDER", "resend"), \
             patch.object(settings, "RESEND_API_KEY", "re_test_key_123"):

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

    @patch("smtplib.SMTP")
    def test_smtp_fallback_mode(self, mock_smtp_class):
        """Verifies that when EMAIL_PROVIDER is set to smtp, delivery dispatches via SMTP."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "EMAIL_PROVIDER", "smtp"), \
             patch.object(settings, "SMTP_USER", "smart.event.system2026@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcdefghijklmnop"), \
             patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 587):

            ok, msg = send_email_detailed("user@college.edu", "Subject", "<p>Hello</p>")
            self.assertTrue(ok)
            mock_server.sendmail.assert_called_once()


if __name__ == "__main__":
    unittest.main()
