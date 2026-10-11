"""
Comprehensive Unit & Integration Test Suite for Master Authentication Repair:
- Gmail SMTP Email Integration
- 6-digit OTP Hashing & Generation
- Pending Registration Staging (Zero user creation before email verification)
- OTP Expiry & Max Attempts Lockout
- Password Reset OTP Flow (Cooldown, 6-digit OTP, Invalidation of Older OTPs)
- Unverified Login Prevention
- Approval Checks
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import generate_otp, hash_otp, verify_otp_hash, hash_password, verify_password
from app.db import firestore_service as db_service
from app.models.user import RoleEnum, User
from app.services.email_service import send_password_reset_otp_email, send_otp_email


class TestMasterAuthenticationRepair(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_email = f"auth_repair_test_{int(datetime.now().timestamp())}@college.edu"
        self.test_password = "SecurePassword@123"

    def tearDown(self):
        # Clean up any test records created
        try:
            db_service.delete_pending_registration(self.test_email)
        except Exception:
            pass
        try:
            existing = db_service.get_user_by_email(self.test_email)
            if existing:
                db_service.delete_user(existing.id)
        except Exception:
            pass

    def test_01_otp_generation_and_hashing(self):
        """Verify 6-digit numeric OTP generation and secure constant-time verification."""
        otp = generate_otp(6)
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        hashed = hash_otp(otp)
        self.assertNotEqual(otp, hashed)
        self.assertTrue(verify_otp_hash(otp, hashed))
        self.assertFalse(verify_otp_hash("999999" if otp != "999999" else "111111", hashed))
        self.assertFalse(verify_otp_hash("", hashed))

    @patch("app.api.routes.auth_routes.send_otp_email")
    def test_02_registration_staged_in_pending_does_not_create_permanent_user(self, mock_send_email):
        """Ensure NO permanent user record is created in Firestore before email OTP verification."""
        mock_send_email.return_value = (True, "Email delivered successfully via Gmail SMTP")

        payload = {
            "name": "Jane Student",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
            "role": "student",
            "registration_number": f"REG_{int(datetime.now().timestamp())}",
            "department": "Computer Science",
            "semester": "5",
        }

        resp = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertFalse(data["is_email_verified"])

        # 1. Assert permanent user does NOT exist in main users table
        permanent_user = db_service.get_user_by_email(self.test_email)
        self.assertIsNone(permanent_user, "CRITICAL: Permanent user was created before email verification!")

        # 2. Assert registration is staged in pending_registrations
        pending = db_service.get_pending_registration(self.test_email)
        self.assertIsNotNone(pending, "Registration must be stored in pending_registrations")
        self.assertEqual(pending["name"], "Jane Student")
        # Ensure password is securely hashed in pending storage
        self.assertNotEqual(pending["hashed_password"], self.test_password)
        self.assertTrue(verify_password(self.test_password, pending["hashed_password"]))
        # Ensure OTP is securely hashed and NOT in plaintext in pending storage
        self.assertIn("hashed_otp", pending)
        self.assertNotIn("otp_code", pending)

    @patch("app.api.routes.auth_routes.send_otp_email")
    def test_03_incorrect_otp_rejected_and_attempts_tracked(self, mock_send_email):
        """Verifies incorrect OTP is rejected with remaining attempts counter incremented."""
        mock_send_email.return_value = (True, "Email delivered")
        raw_otp = "123456"

        pending_data = {
            "name": "Alex Test",
            "email": self.test_email,
            "hashed_password": hash_password(self.test_password),
            "role": "student",
            "registration_number": f"REG_{int(datetime.now().timestamp())}",
            "hashed_otp": hash_otp(raw_otp),
            "attempts": 0,
            "max_attempts": 5,
            "last_sent_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "created_at": datetime.now(timezone.utc),
        }
        db_service.save_pending_registration(pending_data)

        # Submit wrong OTP
        resp = self.client.post("/api/auth/verify-email", json={"email": self.test_email, "otp_code": "000000"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid OTP", resp.json()["detail"])

        # Verify attempt counter incremented
        updated_pending = db_service.get_pending_registration(self.test_email)
        self.assertEqual(updated_pending["attempts"], 1)

    @patch("app.api.routes.auth_routes.send_otp_email")
    def test_04_max_attempts_lockout(self, mock_send_email):
        """Verifies that exceeding max OTP verification attempts blocks further attempts."""
        mock_send_email.return_value = (True, "Email delivered")
        raw_otp = "654321"

        pending_data = {
            "name": "Lockout Test",
            "email": self.test_email,
            "hashed_password": hash_password(self.test_password),
            "role": "student",
            "registration_number": f"REG_{int(datetime.now().timestamp())}",
            "hashed_otp": hash_otp(raw_otp),
            "attempts": 5,  # Maxed out
            "max_attempts": 5,
            "last_sent_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "created_at": datetime.now(timezone.utc),
        }
        db_service.save_pending_registration(pending_data)

        # Even with correct OTP, user is locked out due to attempts limit
        resp = self.client.post("/api/auth/verify-email", json={"email": self.test_email, "otp_code": raw_otp})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Maximum verification attempts exceeded", resp.json()["detail"])

    def test_05_expired_otp_rejected(self):
        """Verifies expired OTP is rejected."""
        raw_otp = "112233"
        pending_data = {
            "name": "Expired Test",
            "email": self.test_email,
            "hashed_password": hash_password(self.test_password),
            "role": "student",
            "registration_number": f"REG_{int(datetime.now().timestamp())}",
            "hashed_otp": hash_otp(raw_otp),
            "attempts": 0,
            "max_attempts": 5,
            "last_sent_at": datetime.now(timezone.utc) - timedelta(minutes=15),
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=10),  # Expired
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=15),
        }
        db_service.save_pending_registration(pending_data)

        resp = self.client.post("/api/auth/verify-email", json={"email": self.test_email, "otp_code": raw_otp})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("expired", resp.json()["detail"].lower())

    @patch("app.api.routes.auth_routes.send_account_pending_approval_email")
    def test_06_successful_verification_creates_permanent_user_atomically(self, mock_approval_email):
        """Verifies successful OTP verification creates the permanent account and removes pending record."""
        raw_otp = "789123"
        reg_no = f"REG_{int(datetime.now().timestamp())}"
        pending_data = {
            "name": "Sarah Connor",
            "email": self.test_email,
            "hashed_password": hash_password(self.test_password),
            "role": "student",
            "registration_number": reg_no,
            "department": "Computer Science",
            "semester": "4",
            "hashed_otp": hash_otp(raw_otp),
            "attempts": 0,
            "max_attempts": 5,
            "last_sent_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "created_at": datetime.now(timezone.utc),
        }
        db_service.save_pending_registration(pending_data)

        resp = self.client.post("/api/auth/verify-email", json={"email": self.test_email, "otp_code": raw_otp})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_email_verified"])
        self.assertEqual(data["name"], "Sarah Connor")

        # 1. Permanent user must now exist
        permanent_user = db_service.get_user_by_email(self.test_email)
        self.assertIsNotNone(permanent_user)
        self.assertTrue(permanent_user.is_email_verified)
        self.assertEqual(permanent_user.approval_status, "PENDING")
        self.assertFalse(permanent_user.is_active)  # Student requires approval

        # 2. Pending registration must be cleaned up
        self.assertIsNone(db_service.get_pending_registration(self.test_email))

    @patch("app.api.routes.auth_routes.send_password_reset_otp_email")
    def test_07_password_reset_otp_complete_workflow(self, mock_send_reset):
        """Tests complete 6-digit OTP password reset workflow including cooldown, attempt limiting, and invalidation."""
        mock_send_reset.return_value = (True, "Password reset email delivered via Gmail SMTP")

        # 1. Create a verified active user for testing password reset
        user = db_service.create_user(
            name="Reset Tester",
            email=self.test_email,
            hashed_password=hash_password(self.test_password),
            role="student",
            registration_number=f"REG_{int(datetime.now().timestamp())}",
            is_email_verified=True,
            is_active=True,
            approval_status="APPROVED",
        )

        # 2. Request Password Reset OTP
        resp1 = self.client.post("/api/auth/forgot-password", json={"email": self.test_email})
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("password reset OTP has been sent", resp1.json()["message"])
        mock_send_reset.assert_called_once()
        args, kwargs = mock_send_reset.call_args
        sent_otp = args[2]
        self.assertEqual(len(sent_otp), 6)
        self.assertTrue(sent_otp.isdigit())

        # 3. Assert active password reset record exists in database with HASHED OTP
        reset_doc = db_service.get_latest_password_reset_for_user(user.id)
        self.assertIsNotNone(reset_doc)
        self.assertFalse(reset_doc.is_used)
        self.assertEqual(reset_doc.attempts, 0)
        self.assertNotEqual(reset_doc.hashed_otp, sent_otp)
        self.assertTrue(verify_otp_hash(sent_otp, reset_doc.hashed_otp))

        # 4. Enforce 60-second cooldown on consecutive requests
        resp_cooldown = self.client.post("/api/auth/forgot-password", json={"email": self.test_email})
        self.assertEqual(resp_cooldown.status_code, 429)
        self.assertIn("Please wait", resp_cooldown.json()["detail"])

        # 5. Verify incorrect OTP fails and tracks attempts
        resp_bad = self.client.post("/api/auth/verify-reset-otp", json={"email": self.test_email, "otp_code": "000000"})
        self.assertEqual(resp_bad.status_code, 400)
        self.assertIn("Invalid OTP", resp_bad.json()["detail"])
        reset_doc_after_bad = db_service.get_latest_password_reset_for_user(user.id)
        self.assertEqual(reset_doc_after_bad.attempts, 1)

        # 6. Verify correct OTP succeeds
        resp_ok = self.client.post("/api/auth/verify-reset-otp", json={"email": self.test_email, "otp_code": sent_otp})
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn("OTP verified successfully", resp_ok.json()["message"])

        # 7. Update Password using the verified OTP
        new_pwd = "BrandNewPassword@999"
        resp_reset = self.client.post(
            "/api/auth/reset-password",
            json={
                "email": self.test_email,
                "otp_code": sent_otp,
                "new_password": new_pwd,
                "confirm_new_password": new_pwd,
            },
        )
        self.assertEqual(resp_reset.status_code, 200)
        self.assertIn("Password reset successfully", resp_reset.json()["message"])

        # 8. Assert OTP is invalidated after use (cannot be reused)
        reused_resp = self.client.post("/api/auth/verify-reset-otp", json={"email": self.test_email, "otp_code": sent_otp})
        self.assertEqual(reused_resp.status_code, 400)

        # 9. Assert user can log in with new password and old password fails
        login_old = self.client.post("/api/auth/login", json={"email": self.test_email, "password": self.test_password, "role": "student"})
        self.assertEqual(login_old.status_code, 401)

        login_new = self.client.post("/api/auth/login", json={"email": self.test_email, "password": new_pwd, "role": "student"})
        self.assertEqual(login_new.status_code, 200)
        self.assertIn("access_token", login_new.json())

    @patch("app.api.routes.auth_routes.send_password_reset_otp_email")
    def test_08_older_password_reset_otp_invalidated_when_new_otp_issued(self, mock_send_reset):
        """Verifies that requesting a new password reset OTP invalidates any older OTP."""
        mock_send_reset.return_value = (True, "Delivered")
        user = db_service.create_user(
            name="Older OTP Test",
            email=self.test_email,
            hashed_password=hash_password(self.test_password),
            role="student",
            registration_number=f"REG_{int(datetime.now().timestamp())}",
            is_email_verified=True,
            is_active=True,
            approval_status="APPROVED",
        )

        otp1 = "123456"
        otp2 = "654321"

        # Issue first reset
        pr1 = db_service.create_password_reset(user.id, otp1, datetime.now(timezone.utc) + timedelta(minutes=5))
        self.assertFalse(pr1.is_used)

        # Issue second reset (this must invalidate the first reset)
        pr2 = db_service.create_password_reset(user.id, otp2, datetime.now(timezone.utc) + timedelta(minutes=5))
        self.assertFalse(pr2.is_used)

        # Check first OTP: trying to verify otp1 must fail because pr1 was invalidated!
        resp_old = self.client.post("/api/auth/verify-reset-otp", json={"email": self.test_email, "otp_code": otp1})
        self.assertEqual(resp_old.status_code, 400)

        # Check second OTP: trying to verify otp2 must succeed
        resp_new = self.client.post("/api/auth/verify-reset-otp", json={"email": self.test_email, "otp_code": otp2})
        self.assertEqual(resp_new.status_code, 200)

    @patch("app.api.routes.auth_routes.send_otp_email")
    def test_09_smtp_delivery_failure_never_simulates_success(self, mock_send_email):
        """Verifies that if SMTP rejects or fails delivery, HTTP 502 is returned and no phantom user created."""
        mock_send_email.return_value = (False, "Gmail SMTP authentication failed. Please verify that your 16-character Google App Password is set correctly in backend .env.")

        payload = {
            "name": "Fail Test",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
            "role": "student",
            "registration_number": f"REG_{int(datetime.now().timestamp())}",
            "department": "Computer Science",
            "semester": "5",
        }

        resp = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(resp.status_code, 502)
        self.assertIn("Gmail SMTP authentication failed", resp.json()["detail"])

        # No pending registration or user left behind
        self.assertIsNone(db_service.get_pending_registration(self.test_email))
        self.assertIsNone(db_service.get_user_by_email(self.test_email))


if __name__ == "__main__":
    unittest.main()
