import re
from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.user import RoleEnum


def validate_password_complexity(v: str) -> str:
    if not v:
        raise ValueError("Password is required.")
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return v


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    registration_number: Optional[str] = Field(None, max_length=50)
    admin_id: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    semester: Optional[str] = Field(None, max_length=20)
    course: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: Optional[str] = None
    role: RoleEnum = RoleEnum.student

    @field_validator("registration_number", "admin_id", "phone", "department", "semester", "course", "designation", mode="before")
    @classmethod
    def normalize_empty_strings(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("password")
    @classmethod
    def validate_password_rules(cls, v):
        return validate_password_complexity(v)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v is not None and "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @model_validator(mode="after")
    def validate_role_fields(self):
        if self.role == RoleEnum.student and not self.registration_number:
            raise ValueError("Registration number is required for students")
        if self.role == RoleEnum.admin and not (self.admin_id or self.registration_number):
            raise ValueError("Admin ID is required for admins")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum
    remember_me: bool = False


class EmailSendOtpRequest(BaseModel):
    email: EmailStr
    role: RoleEnum = RoleEnum.student


class EmailVerifyOtpRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=4, max_length=10)
    role: RoleEnum = RoleEnum.student
    remember_me: bool = False


class FirebaseRegisterRequest(BaseModel):
    id_token: str = Field(..., min_length=20)
    name: str = Field(..., min_length=2, max_length=150)
    registration_number: Optional[str] = Field(None, max_length=50)
    admin_id: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    semester: Optional[str] = Field(None, max_length=20)
    course: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    role: RoleEnum = RoleEnum.student


class FirebaseSessionRequest(BaseModel):
    id_token: str = Field(..., min_length=20)
    role: RoleEnum
    remember_me: bool = False


class FirebasePasswordResetPrepareRequest(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    id: Union[int, str]
    name: str
    registration_number: Optional[str] = None
    admin_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[str] = None
    course: Optional[str] = None
    designation: Optional[str] = None
    email: EmailStr
    role: RoleEnum
    profile_picture: Optional[str] = None
    is_email_verified: bool
    is_active: bool = True
    approval_status: str = "APPROVED"
    approved_by: Optional[Union[int, str]] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[Union[int, str]] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notification_preferences: Optional[dict] = Field(default_factory=lambda: {"in_app": True, "email": True})
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    semester: Optional[str] = Field(None, max_length=20)
    course: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_pwd(cls, v):
        return validate_password_complexity(v)

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class EmailUpdateRequest(BaseModel):
    new_email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp_code: str


class ResendOtpRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    otp_code: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_reset_pwd(cls, v):
        return validate_password_complexity(v)

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class NotificationPreferencesUpdate(BaseModel):
    in_app: Optional[bool] = None
    email: Optional[bool] = None
    allow_in_app: Optional[bool] = None
    allow_email: Optional[bool] = None

    def get_in_app(self, default: bool = True) -> bool:
        if self.in_app is not None:
            return self.in_app
        if self.allow_in_app is not None:
            return self.allow_in_app
        return default

    def get_email(self, default: bool = True) -> bool:
        if self.email is not None:
            return self.email
        if self.allow_email is not None:
            return self.allow_email
        return default


class AdminAvailabilityOut(BaseModel):
    available: bool
    active_admin_count: int
    message: Optional[str] = None


