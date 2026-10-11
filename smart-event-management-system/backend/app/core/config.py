"""
Central application configuration.
All values are loaded from environment variables (.env file).
"""
import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


_backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_default_env_path = os.path.join(_backend_root, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_default_env_path, ".env"),
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

    # Email Provider (Resend API)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    EMAIL_PROVIDER: str = "resend"

    # AI Chatbot Configuration
    AI_PROVIDER: str = "gemini"
    AI_MODEL: str = "gemini-1.5-flash"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Legacy SMTP fallback (if configured)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "EventSphere"
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

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
