from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+psycopg://workshop:workshop@127.0.0.1:5432/workshop"
    secret_key: str = Field(min_length=32)
    admin_email: str = "admin@taller.local"
    admin_password: str = Field(min_length=12)
    cors_origins: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]
    access_token_minutes: int = Field(default=120, ge=5, le=1440)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    telegram_bot_token: str = ""
    notification_worker: bool = True
    web_directory: str = str(Path(__file__).resolve().parents[2] / "build" / "web")

    @model_validator(mode="after")
    def production_security(self):
        if self.environment == "production":
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Producción requiere PostgreSQL")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("CORS de producción requiere orígenes HTTPS explícitos")
            if len(self.secret_key) < 48:
                raise ValueError("SECRET_KEY de producción debe tener al menos 48 caracteres")
            if self.smtp_host and not self.smtp_starttls:
                raise ValueError("SMTP en producción requiere STARTTLS")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
