"""
Configuración central de la aplicación.
Usa Pydantic BaseSettings para validar variables de entorno.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────
    APP_NAME: str = "SaaS Clínicas"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ── Server ───────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Database ─────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clinicas_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/clinicas_db"

    # ── Redis ────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT (RS256) ──────────────────────────────────
    JWT_PRIVATE_KEY_PATH: str = "./keys/private.pem"
    JWT_PUBLIC_KEY_PATH: str = "./keys/public.pem"
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Encryption ───────────────────────────────────
    FERNET_KEY: str = "your-fernet-key-here"

    # ── CORS ─────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ── Celery ───────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── NubeFact (SUNAT) ─────────────────────────────
    NUBEFACT_API_URL: str = "https://api.nubefact.com/api/v1"
    NUBEFACT_API_TOKEN: str = "your-nubefact-token"

    # ── Twilio SMS / WhatsApp ──────────────────────────
    TWILIO_ACCOUNT_SID: str = "your-twilio-account-sid"
    TWILIO_AUTH_TOKEN: str = "your-twilio-auth-token"
    TWILIO_PHONE_NUMBER: str = "+15005550006"
    TWILIO_WHATSAPP_NUMBER: str = "+14155238886"

    # ── json.pe (Consultas DNI / RUC) ────────────────
    JSONPE_API_URL: str = "https://api.json.pe/api"
    JSONPE_API_TOKEN: str = "your-jsonpe-token"

    # ── JWT Keys (loaded at runtime) ─────────────────
    @property
    def jwt_private_key(self) -> str:
        path = Path(self.JWT_PRIVATE_KEY_PATH)
        if path.exists():
            return path.read_text()
        return ""

    @property
    def jwt_public_key(self) -> str:
        path = Path(self.JWT_PUBLIC_KEY_PATH)
        if path.exists():
            return path.read_text()
        return ""

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
