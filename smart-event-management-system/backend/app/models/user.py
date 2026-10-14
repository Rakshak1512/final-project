import enum
from datetime import datetime
from typing import Optional


class RoleEnum(str, enum.Enum):
    student = "student"
    faculty = "faculty"
    volunteer = "volunteer"
    admin = "admin"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower().strip():
                    return member
        return None


class User:
    def __init__(
        self,
        id: Optional[int] = 0,
        name: str = "",
        email: str = "",
        hashed_password: str = "",
        role: RoleEnum = RoleEnum.student,
        registration_number: Optional[str] = None,
        admin_id: Optional[str] = None,
        phone: Optional[str] = None,
        department: Optional[str] = None,
        semester: Optional[str] = None,
        course: Optional[str] = None,
        designation: Optional[str] = None,
        profile_picture: Optional[str] = None,
        is_email_verified: bool = False,
        is_active: bool = True,
        is_deleted: bool = False,
        approval_status: Optional[str] = None,
        approved_by: Optional[int] = None,
        approved_at: Optional[datetime] = None,
        rejected_by: Optional[int] = None,
        rejected_at: Optional[datetime] = None,
        rejection_reason: Optional[str] = None,
        notification_preferences: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        try:
            self.id = int(id) if id is not None else 0
        except (ValueError, TypeError):
            self.id = id

        self.name = name or ""
        self.email = email or ""
        self.phone = phone or None
        self.hashed_password = hashed_password or ""

        if isinstance(role, str):
            try:
                self.role = RoleEnum(role.lower().strip())
            except ValueError:
                self.role = RoleEnum.student
        elif isinstance(role, RoleEnum):
            self.role = role
        else:
            self.role = RoleEnum.student

        self.registration_number = registration_number or (admin_id if self.role == RoleEnum.admin else None)
        self.admin_id = admin_id or (registration_number if self.role == RoleEnum.admin else None)
        self.department = department
        self.semester = semester
        self.course = course or (f"{department} UG" if department and self.role in (RoleEnum.student, RoleEnum.volunteer) else ("B.Tech / Degree" if self.role in (RoleEnum.student, RoleEnum.volunteer) else None))
        self.designation = designation or ("Faculty Coordinator" if self.role == RoleEnum.faculty else None)
        self.profile_picture = profile_picture
        self.is_email_verified = bool(is_email_verified)
        self.is_active = bool(is_active)
        self.is_deleted = bool(is_deleted)
        self.notification_preferences = notification_preferences or {"in_app": True, "email": True}

        # Normalize approval_status to standard values: APPROVED, PENDING, REJECTED, REMOVED
        raw_status = str(approval_status or "").upper().strip()
        if raw_status in ("APPROVED", "ACTIVE"):
            self.approval_status = "APPROVED"
        elif raw_status in ("REJECTED", "DECLINED"):
            self.approval_status = "REJECTED"
        elif raw_status in ("REMOVED", "DELETED"):
            self.approval_status = "REMOVED"
        elif raw_status in ("PENDING", "PENDING_FACULTY_APPROVAL", "PENDING_ADMIN_APPROVAL"):
            self.approval_status = "PENDING"
        elif self.role == RoleEnum.admin:
            self.approval_status = "APPROVED"
        elif self.role in (RoleEnum.student, RoleEnum.faculty, RoleEnum.volunteer):
            self.approval_status = "PENDING"
        elif self.is_active:
            self.approval_status = "APPROVED"
        else:
            self.approval_status = "PENDING"

        try:
            self.approved_by = int(approved_by) if approved_by is not None else None
        except (ValueError, TypeError):
            self.approved_by = approved_by
        self.approved_at = approved_at
        try:
            self.rejected_by = int(rejected_by) if rejected_by is not None else None
        except (ValueError, TypeError):
            self.rejected_by = rejected_by
        self.rejected_at = rejected_at
        self.rejection_reason = rejection_reason
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "registration_number": self.registration_number,
            "admin_id": self.admin_id,
            "phone": self.phone,
            "department": self.department,
            "semester": self.semester,
            "course": self.course,
            "designation": self.designation,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "profile_picture": self.profile_picture,
            "is_email_verified": self.is_email_verified,
            "is_active": self.is_active,
            "is_deleted": getattr(self, "is_deleted", False),
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejected_by": self.rejected_by,
            "rejected_at": self.rejected_at,
            "rejection_reason": self.rejection_reason,
            "notification_preferences": self.notification_preferences or {"in_app": True, "email": True},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        if not data:
            return None
        st = data.get("approval_status")
        if not st:
            role_val = str(data.get("role", "")).lower()
            if role_val == "admin":
                st = "APPROVED"
            else:
                st = "APPROVED" if data.get("is_active", True) else "PENDING"
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone"),
            hashed_password=data.get("hashed_password", ""),
            role=data.get("role", RoleEnum.student),
            registration_number=data.get("registration_number"),
            admin_id=data.get("admin_id") or (data.get("registration_number") if str(data.get("role", "")).lower() == "admin" else None),
            department=data.get("department"),
            semester=data.get("semester"),
            course=data.get("course"),
            designation=data.get("designation"),
            profile_picture=data.get("profile_picture"),
            is_email_verified=data.get("is_email_verified", False),
            is_active=data.get("is_active", True),
            is_deleted=data.get("is_deleted", False),
            approval_status=st,
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            rejected_by=data.get("rejected_by"),
            rejected_at=data.get("rejected_at"),
            rejection_reason=data.get("rejection_reason"),
            notification_preferences=data.get("notification_preferences") or {"in_app": True, "email": True},
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
