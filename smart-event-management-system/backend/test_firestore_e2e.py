"""
End-to-End Test Suite for Smart Event Management System with Firestore
Simulates complete user journeys: Registration -> Verification -> Login -> Event Management -> Registration -> Certificates -> Analytics.
"""
import os
from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Mock firestore collections in-memory for testing if no cloud project is active
class InMemoryFirestoreDoc:
    def __init__(self, doc_id, data=None):
        self.id = str(doc_id)
        self._data = data.copy() if data else {}
        self.exists = data is not None

    def to_dict(self):
        return self._data.copy() if self.exists else None

    def get(self, field=None, default=None, transaction=None):
        if field is not None and isinstance(field, str):
            return self._data.get(field, default)
        return self

    def set(self, data):
        self._data = data.copy()
        self.exists = True

    def update(self, data):
        if self._data is None:
            self._data = {}
        self._data.update(data)
        self.exists = True

    def delete(self):
        self._data = {}
        self.exists = False


class InMemoryFirestoreCollection:
    def __init__(self, name, db):
        self.name = name
        self.db = db
        self.docs = {}

    def document(self, doc_id):
        doc_id = str(doc_id)
        if doc_id not in self.docs:
            self.docs[doc_id] = InMemoryFirestoreDoc(doc_id, None)
        return self.docs[doc_id]

    def stream(self):
        return [doc for doc in self.docs.values() if doc.exists]

    def where(self, field, op, value):
        class Query:
            def __init__(self, collection, filters):
                self.collection = collection
                self.filters = filters

            def where(self, f, o, v):
                return Query(self.collection, self.filters + [(f, o, v)])

            def limit(self, n):
                self._limit = n
                return self

            def stream(self):
                matches = []
                for doc in self.collection.docs.values():
                    if not doc.exists:
                        continue
                    data = doc.to_dict()
                    match = True
                    for f, o, v in self.filters:
                        val = data.get(f)
                        if o == "==" and val != v:
                            match = False
                            break
                    if match:
                        matches.append(doc)
                return matches

        return Query(self, [(field, op, value)])


class MockFirestoreClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = InMemoryFirestoreCollection(name, self)
        return self.collections[name]

    def transaction(self):
        mock_txn = MagicMock()
        return mock_txn

    def batch(self):
        mock_batch = MagicMock()
        return mock_batch


# Set up mock DB
mock_db = MockFirestoreClient()
counters = {}

def mock_get_next_id(collection_name: str) -> int:
    counters[collection_name] = counters.get(collection_name, 0) + 1
    return counters[collection_name]

captured_otps = {}


def mock_send_otp_fn(email, otp, *args, **kwargs):
    captured_otps[email] = str(otp)
    return (True, "Delivered")


with patch("app.core.firebase.get_firestore_db", return_value=mock_db), \
     patch("app.db.firestore_service.get_firestore_db", return_value=mock_db), \
     patch("app.core.firebase.get_next_id", side_effect=mock_get_next_id), \
     patch("app.db.firestore_service.get_next_id", side_effect=mock_get_next_id), \
     patch("app.api.routes.auth_routes.send_otp_email", side_effect=mock_send_otp_fn), \
     patch("app.services.email_service.send_email", return_value=True):

    from app.main import app
    from app.db import firestore_service as db_service
    client = TestClient(app)

    print("=" * 60)
    print("RUNNING END-TO-END FIRESTORE TEST SUITE")
    print("=" * 60)

    def get_otp_for(email):
        if email in captured_otps:
            return captured_otps[email]
        for doc in mock_db.collection("pending_registrations").stream():
            d = doc.to_dict() or {}
            if d.get("email") == email and d.get("otp_code"):
                return str(d.get("otp_code"))
        for doc in mock_db.collection("email_verifications").stream():
            d = doc.to_dict() or {}
            if d.get("email") == email and d.get("otp_code"):
                return str(d.get("otp_code"))
        return "123456"

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    assert res.json() == {"status": "healthy", "database": "firestore"}
    print("[PASS] 1. /api/health -> 200 OK with Firestore database")

    # 2. Register Student
    student_payload = {
        "name": "Jane Student",
        "email": "jane.student@college.edu",
        "registration_number": "STU12345",
        "department": "Computer Science",
        "semester": "6",
        "password": "Password@123",
        "confirm_password": "Password@123",
        "role": "student",
    }
    res = client.post("/api/auth/register", json=student_payload)
    assert res.status_code == 201, f"Student register failed: {res.text}"
    student_data = res.json()
    assert student_data["email"] == "jane.student@college.edu"
    assert student_data["registration_number"] == "STU12345"
    assert student_data["is_email_verified"] is False
    print("[PASS] 2. Student registration -> 201 Created")

    # Verify Email with OTP
    otp_code = get_otp_for("jane.student@college.edu")
    res = client.post("/api/auth/verify-email", json={"email": "jane.student@college.edu", "otp_code": otp_code})
    assert res.status_code == 200, f"Email verification failed: {res.text}"
    assert res.json()["is_email_verified"] is True
    student_id = res.json()["id"]
    print("[PASS] 3. Student email OTP verification -> 200 OK")

    # 3. Student Login
    res = client.post("/api/auth/login", json={
        "email": "jane.student@college.edu",
        "password": "Password@123",
        "role": "student",
    })
    assert res.status_code == 200, f"Student login failed: {res.text}"
    student_token = res.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    print("[PASS] 4. Student login & JWT Token generation -> 200 OK")

    # 4. Register Faculty
    faculty_payload = {
        "name": "Dr. Alan Turing",
        "email": "alan.turing@college.edu",
        "department": "Computer Science",
        "password": "FacultyPassword@123",
        "confirm_password": "FacultyPassword@123",
        "role": "faculty",
    }
    res = client.post("/api/auth/register", json=faculty_payload)
    assert res.status_code == 201, f"Faculty register failed: {res.text}"

    # Verify faculty email
    f_otp = get_otp_for("alan.turing@college.edu")
    res_f = client.post("/api/auth/verify-email", json={"email": "alan.turing@college.edu", "otp_code": f_otp})
    assert res_f.status_code == 200
    faculty_id = res_f.json()["id"]

    res = client.post("/api/auth/login", json={
        "email": "alan.turing@college.edu",
        "password": "FacultyPassword@123",
        "role": "faculty",
    })
    assert res.status_code == 200
    faculty_token = res.json()["access_token"]
    faculty_headers = {"Authorization": f"Bearer {faculty_token}"}
    print("[PASS] 5. Faculty registration, OTP verify & login -> 200 OK")

    # 5. Faculty Creates Event
    event_payload = {
        "title": "Annual AI & Web Hackathon 2026",
        "description": "A 24-hour campus hackathon to innovate next-gen smart applications.",
        "category": "Technical",
        "venue": "Main Campus Auditorium",
        "event_date": (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d"),
        "event_time": "09:00 AM",
        "total_seats": 50,
    }
    # Pending Faculty cannot create events -> 403 ACCOUNT_PENDING_APPROVAL
    res = client.post("/api/events", data=event_payload, headers=faculty_headers)
    assert res.status_code == 403 and res.json()["detail"] == "ACCOUNT_PENDING_APPROVAL", f"Pending faculty should be blocked: {res.text}"
    print("[PASS] 5b. Pending faculty event creation correctly blocked -> 403 ACCOUNT_PENDING_APPROVAL")

    # Admin approves Faculty
    db_service.approve_user(faculty_id, approver_id=1)
    res = client.post("/api/events", data=event_payload, headers=faculty_headers)
    assert res.status_code == 201, f"Event creation failed: {res.text}"
    event_data = res.json()
    event_id = event_data["id"]
    assert event_data["title"] == "Annual AI & Web Hackathon 2026"
    assert event_data["available_seats"] == 50
    assert event_data["organizer_name"] == "Dr. Alan Turing"
    print("[PASS] 6. Approved faculty event creation with organizer metadata -> 201 Created")

    # 6. Browse Events & Categories
    res = client.get("/api/events")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert len(res.json()["items"]) == 1

    res = client.get("/api/events/categories/list")
    assert res.status_code == 200
    assert "Technical" in res.json()["categories"]
    print("[PASS] 7. Event listing, pagination, and category extraction -> 200 OK")

    # 6b. Register Faculty B and test cross-faculty event edit
    faculty_b_payload = {
        "name": "Prof. Ada Lovelace",
        "email": "ada.lovelace@college.edu",
        "department": "Information Technology",
        "password": "FacultyPassword@123",
        "confirm_password": "FacultyPassword@123",
        "role": "faculty",
    }
    res = client.post("/api/auth/register", json=faculty_b_payload)
    assert res.status_code == 201
    fb_otp = get_otp_for("ada.lovelace@college.edu")
    res_fb = client.post("/api/auth/verify-email", json={"email": "ada.lovelace@college.edu", "otp_code": fb_otp})
    assert res_fb.status_code == 200
    faculty_b_id = res_fb.json()["id"]
    res = client.post("/api/auth/login", json={"email": "ada.lovelace@college.edu", "password": "FacultyPassword@123", "role": "faculty"})
    faculty_b_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    # Faculty B is pending -> edit rejected with 403 ACCOUNT_PENDING_APPROVAL
    res = client.put(f"/api/events/{event_id}", data={
        "venue": "Grand Campus Convention Hall",
        "description": "Updated description by Faculty B.",
    }, headers=faculty_b_headers)
    assert res.status_code == 403 and res.json()["detail"] == "ACCOUNT_PENDING_APPROVAL"
    print("[PASS] 7a. Pending Faculty B edit correctly blocked -> 403 ACCOUNT_PENDING_APPROVAL")

    # Admin approves Faculty B
    db_service.approve_user(faculty_b_id, approver_id=1)
    res = client.put(f"/api/events/{event_id}", data={
        "venue": "Grand Campus Convention Hall",
        "description": "Updated description by Faculty B.",
    }, headers=faculty_b_headers)
    assert res.status_code == 200
    updated_ev = res.json()
    assert updated_ev["venue"] == "Grand Campus Convention Hall"
    assert updated_ev["created_by"] == faculty_id
    assert updated_ev["updated_by"] == faculty_b_id
    print("[PASS] 7b. Approved Faculty B edits Faculty A's event -> 200 OK")

    # Student attempts to edit event -> 403 Forbidden (role permission)
    res = client.put(f"/api/events/{event_id}", data={"venue": "Hacked Hall"}, headers=student_headers)
    assert res.status_code == 403
    print("[PASS] 7c. Student event edit attempt correctly rejected -> 403 Forbidden")

    # 7. Pending Student attempts event registration -> 403 ACCOUNT_PENDING_APPROVAL
    res = client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
    assert res.status_code == 403 and res.json()["detail"] == "ACCOUNT_PENDING_APPROVAL"
    print("[PASS] 7d. Pending student event registration correctly blocked -> 403 ACCOUNT_PENDING_APPROVAL")

    # Faculty approves student
    db_service.approve_user(student_id, approver_id=faculty_id)

    # 8. Approved Student Event Registration
    res = client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
    assert res.status_code == 201, f"Registration failed: {res.text}"
    reg_data = res.json()
    reg_id = reg_data["id"]
    ticket_code = reg_data["ticket_code"]
    assert reg_data["status"] == "registered"
    assert len(ticket_code) > 0
    print(f"[PASS] 8. Student event registration with QR ticket code ({ticket_code}) -> 201 Created")

    # 8. Duplicate Registration Rejection
    res = client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
    assert res.status_code == 400
    assert "already" in res.json()["detail"].lower() and "registered" in res.json()["detail"].lower()
    print("[PASS] 9. Duplicate registration correctly rejected -> 400 Bad Request")

    # 9. Student Registration List
    res = client.get("/api/registrations/my", headers=student_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == reg_id
    print("[PASS] 10. Student 'My Registrations' retrieval -> 200 OK")

    # 10. Faculty Views Event Registrations
    res = client.get(f"/api/registrations/event/{event_id}", headers=faculty_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["student"]["name"] == "Jane Student"
    print("[PASS] 11. Faculty event participants inspection -> 200 OK")

    # 11. Student Notifications
    res = client.get("/api/notifications", headers=student_headers)
    assert res.status_code == 200
    notifs = res.json()
    assert len(notifs) >= 1
    notif_id = notifs[0]["id"]
    assert notifs[0]["is_read"] is False

    # Mark Notification Read
    res = client.put(f"/api/notifications/{notif_id}/read", headers=student_headers)
    assert res.status_code == 200
    assert res.json()["is_read"] is True
    print("[PASS] 12. Student notification dispatch & mark-read -> 200 OK")

    # 12. Faculty Uploads Certificate for Student
    res = client.get(f"/api/certificates/student/details/STU12345", headers=faculty_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "jane.student@college.edu"

    # Create dummy certificate file
    cert_dir = os.path.join(os.path.dirname(__file__), "uploads", "certificates")
    os.makedirs(cert_dir, exist_ok=True)
    dummy_cert_path = os.path.join(cert_dir, "test_cert.pdf")
    with open(dummy_cert_path, "wb") as f:
        f.write(b"%PDF-1.4 test certificate binary content")

    # Manually insert certificate record into firestore mock
    cert_obj = db_service.create_certificate(
        registration_number="STU12345",
        event_id=event_id,
        title="Web Dev Bootcamp - Certificate of Completion",
        file_path=dummy_cert_path,
        uploaded_by=faculty_id,
    )
    cert_id = cert_obj.id

    # Student retrieves my certificates
    res = client.get("/api/certificates/my", headers=student_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == cert_id

    # Student downloads/previews certificate with Authorization Bearer header -> 200 OK
    res = client.get(f"/api/certificates/{cert_id}/download", headers=student_headers)
    assert res.status_code == 200
    assert b"%PDF-1.4" in res.content
    print("[PASS] 13. Certificate retrieval & authenticated download/preview -> 200 OK")

    # Unauthenticated certificate download -> 401 Unauthorized
    res = client.get(f"/api/certificates/{cert_id}/download")
    assert res.status_code == 401
    print("[PASS] 14. Unauthenticated certificate request correctly rejected -> 401 Unauthorized")

    # 15. Student & Faculty Analytics
    res = client.get("/api/analytics/student", headers=student_headers)
    assert res.status_code == 200
    s_analytics = res.json()
    assert s_analytics["total_registrations"] == 1
    assert s_analytics["upcoming_events"] == 1

    res = client.get("/api/analytics/faculty", headers=faculty_headers)
    assert res.status_code == 200
    f_analytics = res.json()
    assert f_analytics["total_events_created"] == 1
    assert f_analytics["total_registrations_received"] == 1
    print("[PASS] 15. Real-time Student & Faculty analytics calculation -> 200 OK")

    # 16. Student Profile Update
    res = client.put("/api/users/profile", json={"name": "Jane Doe Student", "semester": "7"}, headers=student_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Jane Doe Student"
    assert res.json()["semester"] == "7"
    print("[PASS] 16. User profile update -> 200 OK")

    print("=" * 60)
    print("ALL E2E FIRESTORE & CERTIFICATE TESTS PASSED SUCCESSFULLY! (16/16)")
    print("=" * 60)
