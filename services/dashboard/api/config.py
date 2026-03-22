"""
Configuration management for the dashboard API.

Loads settings from environment variables and provides
type-safe configuration access throughout the application.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Email Management Dashboard"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Database (SQLite for development, set DATABASE_URL for production)
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./email_dashboard.db"
    )

    # Email IMAP (reuse from existing .env)
    email_server: str = os.getenv("EMAIL_SERVER", "imap.gmail.com")
    email_port: int = int(os.getenv("EMAIL_PORT", "993"))
    email_address: str = os.getenv("EMAIL_ADDRESS", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")

    # OpenAI (reuse from existing .env)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Authentication (SESSION_SECRET required in production)
    session_secret: str = os.getenv("SESSION_SECRET", "")
    session_expiry_hours: int = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))
    admin_password_hash: Optional[str] = os.getenv("ADMIN_PASSWORD_HASH")
    stakeholder_password_hash: Optional[str] = os.getenv("STAKEHOLDER_PASSWORD_HASH")

    # CORS
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Rate Limiting
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))

    class Config:
        env_file = ".env"
        case_sensitive = False

    def validate_production_settings(self):
        """Validate that required secrets are set in production."""
        if self.environment == "production":
            if not self.session_secret:
                raise ValueError("SESSION_SECRET is required in production environment")
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required in production environment")


settings = Settings()
# Validate settings on startup
settings.validate_production_settings()
