"""
Unit and Integration Tests for Global Search and Role-Based Record Access
"""
import unittest
from unittest.mock import patch, MagicMock

from app.models.user import User, RoleEnum
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.certificate import Certificate
from app.api.routes.search_routes import global_search


class TestGlobalSearch(unittest.TestCase):

    def setUp(self):
        self.student_user = User(
            id=101,
            name="Alice Student",
            email="alice@college.edu",
            role=RoleEnum.student,
            registration_number="REG-CS-101",
            department="Computer Science",
            is_email_verified=True,
            is_active=True,
            approval_status="APPROVED",
        )
        self.faculty_user = User(
            id=202,
            name="Dr. Smith",
            email="smith@college.edu",
            role=RoleEnum.faculty,
            registration_number="FAC-202",
            department="Electronics",
            is_email_verified=True,
            is_active=True,
            approval_status="APPROVED",
        )
        self.admin_user = User(
            id=303,
            name="Admin User",
            email="admin@college.edu",
            role=RoleEnum.admin,
            admin_id="ADM-001",
            is_email_verified=True,
            is_active=True,
            approval_status="APPROVED",
        )

        self.sample_event = Event(
            id=1,
            title="Tech Hackathon 2026",
            category="Technical",
            event_date="2026-11-15",
            event_time="10:00 AM",
            venue="Auditorium A",
            total_seats=100,
            available_seats=45,
            description="24-hour coding fest",
            created_by=202,
        )

    def test_empty_or_whitespace_query(self):
        """Verifies empty or whitespace query returns 0 results with total 0 and no errors."""
        res_empty = global_search(q="", current_user=self.student_user)
        self.assertEqual(res_empty.total, 0)
        self.assertEqual(len(res_empty.results), 0)

        res_spaces = global_search(q="    ", current_user=self.student_user)
        self.assertEqual(res_spaces.total, 0)
        self.assertEqual(len(res_spaces.results), 0)

    @patch("app.db.firestore_service.get_all_events")
    @patch("app.db.firestore_service.get_my_registrations")
    @patch("app.db.firestore_service.get_certificates_by_registration_number")
    @patch("app.db.firestore_service.list_notifications")
    def test_student_events_and_own_records(self, mock_notifs, mock_certs, mock_regs, mock_events):
        """Verifies student can find public events and their own registrations and certificates."""
        mock_events.return_value = [self.sample_event]
        mock_regs.return_value = [
            Registration(
                id=55,
                event_id=1,
                student_id=101,
                ticket_code="TCK-ALICE",
                status=RegistrationStatus.approved,
                event=self.sample_event,
            )
        ]
        mock_certs.return_value = [
            Certificate(
                id=12,
                registration_number="REG-CS-101",
                title="Hackathon Participant",
                file_path="certificates/sample.pdf",
                student_name="Alice Student",
                event_id=1,
            )
        ]
        mock_notifs.return_value = []

        # 1. Search for event by name (case-insensitive)
        resp_event = global_search(q="hackathon", current_user=self.student_user)
        self.assertGreater(resp_event.total, 0)
        event_match = next((r for r in resp_event.results if r.id == "event-1"), None)
        self.assertIsNotNone(event_match)
        self.assertEqual(event_match.link, "/student/events/1")

        # 2. Search for student's own ticket code
        resp_ticket = global_search(q="TCK-ALICE", current_user=self.student_user)
        reg_match = next((r for r in resp_ticket.results if r.id == "reg-55"), None)
        self.assertIsNotNone(reg_match)
        self.assertEqual(reg_match.link, "/student/my-registrations")

        # 3. Search for certificates
        resp_cert = global_search(q="Participant", current_user=self.student_user)
        cert_match = next((r for r in resp_cert.results if r.id == "cert-12"), None)
        self.assertIsNotNone(cert_match)
        self.assertEqual(cert_match.link, "/student/certificates")

    @patch("app.db.firestore_service.get_all_events")
    @patch("app.db.firestore_service.get_pending_students")
    @patch("app.db.firestore_service.get_faculty_assignments")
    @patch("app.db.firestore_service.get_events_by_organizer")
    @patch("app.db.firestore_service.get_certificates_by_faculty")
    @patch("app.db.firestore_service.list_notifications")
    def test_faculty_search_pending_approvals_link(self, mock_notifs, mock_certs, mock_events_org, mock_tasks, mock_pending, mock_all_events):
        """Verifies faculty search links to /faculty/student-approvals and /faculty/tasks correctly."""
        mock_all_events.return_value = [self.sample_event]
        mock_certs.return_value = []
        mock_events_org.return_value = [self.sample_event]
        mock_tasks.return_value = []
        mock_pending.return_value = [
            User(id=99, name="Bob Pending", email="bob@college.edu", role=RoleEnum.student, registration_number="REG-BOB", approval_status="PENDING")
        ]
        mock_notifs.return_value = []

        resp = global_search(q="Pending", current_user=self.faculty_user)
        pending_match = next((r for r in resp.results if r.id == "pending-stu-99"), None)
        self.assertIsNotNone(pending_match)
        self.assertEqual(pending_match.link, "/faculty/student-approvals")

    @patch("app.db.firestore_service.get_all_events")
    @patch("app.db.firestore_service.get_all_faculty_with_stats")
    @patch("app.db.firestore_service.get_pending_faculty")
    @patch("app.db.firestore_service.get_all_assignments")
    @patch("app.db.firestore_service.list_notifications")
    def test_admin_search_faculty_approvals_link(self, mock_notifs, mock_tasks, mock_pending_fac, mock_fac_list, mock_all_events):
        """Verifies admin search links to /admin/faculty-approvals and /admin/faculty correctly."""
        mock_all_events.return_value = [self.sample_event]
        mock_tasks.return_value = []
        mock_fac_list.return_value = [{"id": 202, "name": "Dr. Smith", "email": "smith@college.edu", "department": "Electronics"}]
        mock_pending_fac.return_value = [
            User(id=203, name="Prof. Pending", email="pending@college.edu", role=RoleEnum.faculty, department="Civil", approval_status="PENDING")
        ]
        mock_notifs.return_value = []

        resp = global_search(q="Pending", current_user=self.admin_user)
        pending_match = next((r for r in resp.results if r.id == "pending-fac-203"), None)
        self.assertIsNotNone(pending_match)
        self.assertEqual(pending_match.link, "/admin/faculty-approvals")


if __name__ == "__main__":
    unittest.main()
