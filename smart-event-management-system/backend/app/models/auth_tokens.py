from datetime import datetime
from typing import Optional


class PasswordReset:
    def __init__(
        self,
        id: int,
        user_id: int,
        otp_code: str,
        expires_at: datetime,
        is_used: bool = False,
        hashed_otp: Optional[str] = None,
        attempts: int = 0,
        max_attempts: int = 5,
        created_at: Optional[datetime] = None,
    ):
        self.id = int(id)
        self.user_id = int(user_id)
        self.otp_code = otp_code
        self.expires_at = expires_at
        self.is_used = is_used
        self.hashed_otp = hashed_otp
        self.attempts = int(attempts)
        self.max_attempts = int(max_attempts)
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "otp_code": self.otp_code,
            "hashed_otp": self.hashed_otp,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "is_used": self.is_used,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PasswordReset":
        if not data:
            return None
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id"),
            otp_code=data.get("otp_code", ""),
            hashed_otp=data.get("hashed_otp"),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 5),
            is_used=data.get("is_used", False),
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at"),
        )


class EmailVerification:
    def __init__(
        self,
        id: int,
        user_id: int,
        otp_code: str,
        expires_at: datetime,
        is_used: bool = False,
        created_at: Optional[datetime] = None,
    ):
        self.id = int(id)
        self.user_id = int(user_id)
        self.otp_code = otp_code
        self.expires_at = expires_at
        self.is_used = is_used
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "otp_code": self.otp_code,
            "is_used": self.is_used,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmailVerification":
        if not data:
            return None
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id"),
            otp_code=data.get("otp_code", ""),
            is_used=data.get("is_used", False),
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at"),
        )
