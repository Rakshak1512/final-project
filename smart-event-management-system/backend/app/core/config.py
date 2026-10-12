"""
Central application configuration.
All values are loaded from environment variables (.env file).
"""
import os
from functools import lru_cache
from typing import Any, List

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_default_env_path = os.path.join(_backend_root, ".env")
_candidate_env_paths = [
    _default_env_path,
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "smart-event-management-system", "backend", ".env"),
    os.path.join(os.getcwd(), "backend", ".env"),
]
_active_env_files = tuple(dict.fromkeys([p for p in _candidate_env_paths if os.path.exists(p)])) or (_default_env_path, ".env")

# Preload local backend .env to ensure local backend configuration takes precedence
# and prevents ambient environment variables or other providers from overriding credentials.
for _candidate in _candidate_env_paths:
    if os.path.exists(_candidate):
        load_dotenv(_candidate, override=True)
        break


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_active_env_files,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "EventSphere"
    APP_ENV: str = "development"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    # Security
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Firebase / Firestore Configuration
    # Option 1: Path to Firebase Service Account JSON file (e.g. "./firebase_credentials.json")
    FIREBASE_CREDENTIALS_PATH: str = ""
    # Option 2: Individual Service Account credentials from env vars
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""
    # Option 3: Local Firestore Emulator (e.g. "localhost:8080")
    FIRESTORE_EMULATOR_HOST: str = ""

    # Email Provider (Resend HTTP API as primary default; SMTP supported)
    EMAIL_PROVIDER: str = "resend"
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"

    # SMTP Settings (optional fallback/secondary provider)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "smart.event.system2026@gmail.com"
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "EventSphere"
    SMTP_FROM_EMAIL: str = "smart.event.system2026@gmail.com"
    SMTP_USE_TLS: bool = True

    @field_validator("EMAIL_PROVIDER", mode="before")
    @classmethod
    def clean_email_provider(cls, v: Any) -> str:
        s = str(v).strip().lower() if v else ""
        return s or "resend"

    @field_validator("RESEND_API_KEY", mode="before")
    @classmethod
    def clean_resend_api_key(cls, v: Any) -> str:
        return str(v).strip().strip("\"'") if v else ""

    @field_validator("RESEND_FROM_EMAIL", mode="before")
    @classmethod
    def clean_resend_from_email(cls, v: Any) -> str:
        s = str(v).strip().strip("\"'") if v else ""
        return s or "onboarding@resend.dev"

    @field_validator("SMTP_HOST", mode="before")
    @classmethod
    def clean_smtp_host(cls, v: Any) -> str:
        s = str(v).strip() if v else ""
        return s or "smtp.gmail.com"

    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def clean_smtp_port(cls, v: Any) -> int:
        try:
            return int(v) if v else 587
        except Exception:
            return 587

    @field_validator("SMTP_USER", mode="before")
    @classmethod
    def clean_smtp_user(cls, v: Any) -> str:
        s = str(v).strip().strip("\"'") if v else ""
        return s or "smart.event.system2026@gmail.com"

    @field_validator("SMTP_FROM_EMAIL", mode="before")
    @classmethod
    def clean_smtp_from_email(cls, v: Any) -> str:
        s = str(v).strip().strip("\"'") if v else ""
        return s or "smart.event.system2026@gmail.com"

    @field_validator("SMTP_PASSWORD", mode="before")
    @classmethod
    def clean_smtp_password(cls, v: Any) -> str:
        if not v:
            return ""
        # Remove accidental spaces (e.g. Google's 4x4 grouping 'abcd efgh ijkl mnop') and outer quotes
        return str(v).replace(" ", "").strip().strip("\"'")

    @field_validator("SMTP_USE_TLS", mode="before")
    @classmethod
    def clean_smtp_use_tls(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return True

    @property
    def is_resend_configured(self) -> bool:
        return bool(self.RESEND_API_KEY and self.RESEND_API_KEY.strip())

    @property
    def is_smtp_configured(self) -> bool:
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def is_google_app_password_valid_length(self) -> bool:
        return len(self.SMTP_PASSWORD) == 16 if self.SMTP_PASSWORD else False

    # AI Chatbot Configuration
    AI_PROVIDER: str = "gemini"
    AI_MODEL: str = "gemini-1.5-flash"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # OTP
    OTP_EXPIRE_MINUTES: int = 5
    OTP_LENGTH: int = 6
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 5
    UPLOAD_DIR: str = "uploads"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Demo/test accounts. Keep enabled only when demo accounts are desired.
    SEED_TEST_USERS: bool = False

    @property
    def upload_dir_abs(self) -> str:
        if os.environ.get("VERCEL"):
            return "/tmp/uploads"
        if os.path.isabs(self.UPLOAD_DIR):
            return self.UPLOAD_DIR
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, self.UPLOAD_DIR)

    @property
    def cors_origin_list(self) -> List[str]:
        raw_list = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if "*" in raw_list:
            return ["*"]
        if self.FRONTEND_URL and self.FRONTEND_URL.strip():
            clean_fe = self.FRONTEND_URL.strip().rstrip("/")
            if clean_fe and clean_fe not in raw_list:
                raw_list.append(clean_fe)
        # Always include localhost in development for convenience
        if self.APP_ENV == "development":
            for default_origin in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]:
                if default_origin not in raw_list:
                    raw_list.append(default_origin)
        return raw_list


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
