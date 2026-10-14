import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.db import firestore_service as db_service
from app.models.user import User, RoleEnum
from app.core.security import create_access_token, hash_password
from app.services.email_service import _user_allows_email

class TestNewFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_email = "role_test_user@eventsphere.edu"
        cls.test_password = "SecurePassword123!"
        
        # Ensure test user exists in Firestore
        existing = db_service.get_user_by_email(cls.test_email)
        if not existing:
            cls.test_user = db_service.create_user(
                name="Role Test User",
                email=cls.test_email,
                hashed_password=hash_password(cls.test_password),
                role=RoleEnum.admin,
                is_email_verified=True,
                is_active=True,
                approval_status="APPROVED",
            )
        else:
            db_service.update_user(existing.id, {
                "hashed_password": hash_password(cls.test_password),
                "role": RoleEnum.admin,
                "is_email_verified": True,
                "is_active": True,
                "approval_status": "APPROVED",
            })
            cls.test_user = db_service.get_user_by_email(cls.test_email)

    @classmethod
    def tearDownClass(cls):
        # Clean up test user
        user = db_service.get_user_by_email(cls.test_email)
        if user:
            db_service.remove_user_account(user.id)

    def test_admin_availability_endpoint(self):
        """Test GET /api/auth/admin-availability returns correct schema and state."""
        response = self.client.get("/api/auth/admin-availability")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("available", data)
        self.assertIn("active_admin_count", data)
        self.assertIsInstance(data["available"], bool)
        self.assertIsInstance(data["active_admin_count"], int)

    def test_admin_registration_rejection_when_occupied(self):
        """Test that registering an Admin when one is active gets rejected."""
        payload = {
            "name": "Intruder Admin",
            "email": "intruder_admin_test@eventsphere.edu",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "admin",
            "admin_id": "ADM-9999",
        }
        response = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(response.status_code, 400)
        detail = response.json().get("detail", "")
        self.assertIn("Admin", detail)

    def test_role_mismatch_login_rejection(self):
        """Test that attempting to log in through a mismatching role returns 403 Forbidden."""
        # Authenticate with valid password but wrong role (student instead of admin)
        payload = {
            "email": self.test_email,
            "password": self.test_password,
            "role": "student",  # Deliberate mismatch
        }
        response = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(response.status_code, 403)
        detail = response.json().get("detail", "")
        self.assertIn("Selected role", detail)

    def test_email_preferences_filter(self):
        """Test that _user_allows_email respects user notification preferences."""
        user_with_email_disabled = User(
            id=9988,
            name="Opted Out",
            email="optout@test.com",
            role=RoleEnum.student,
            notification_preferences={"in_app": True, "email": False},
        )
        self.assertFalse(_user_allows_email(user_with_email_disabled))

        user_with_email_enabled = User(
            id=9989,
            name="Opted In",
            email="optin@test.com",
            role=RoleEnum.student,
            notification_preferences={"in_app": True, "email": True},
        )
        self.assertTrue(_user_allows_email(user_with_email_enabled))

        user_default = User(
            id=9990,
            name="Default User",
            email="default@test.com",
            role=RoleEnum.student,
        )
        self.assertTrue(_user_allows_email(user_default))

    def test_notification_preferences_endpoint(self):
        """Test PUT /api/users/notification-preferences updates user preferences."""
        if self.test_user:
            token = create_access_token({"sub": str(self.test_user.id), "role": "admin"})
            headers = {"Authorization": f"Bearer {token}"}
            
            # Update to disable email
            update_payload = {"in_app": True, "email": False}
            res = self.client.put("/api/users/notification-preferences", json=update_payload, headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data.get("notification_preferences"), {"in_app": True, "email": False})

            # Revert back to true
            revert_payload = {"in_app": True, "email": True}
            res_revert = self.client.put("/api/users/notification-preferences", json=revert_payload, headers=headers)
            self.assertEqual(res_revert.status_code, 200)
            self.assertEqual(res_revert.json().get("notification_preferences"), {"in_app": True, "email": True})

if __name__ == "__main__":
    unittest.main()
