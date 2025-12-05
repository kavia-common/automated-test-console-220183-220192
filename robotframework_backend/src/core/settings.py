import os
from typing import List, Optional

from pydantic import BaseModel


class _Settings(BaseModel):
    """Application settings loaded from environment variables with sane defaults."""

    # Service
    PORT: int = int(os.getenv("PORT", "3001"))
    RUN_CONCURRENCY: int = int(os.getenv("RUN_CONCURRENCY", "1"))
    USE_SSE: bool = os.getenv("USE_SSE", "true").strip().lower() in {"1", "true", "yes", "on"}

    # CORS
    CORS_ALLOWED_ORIGINS: List[str] = []
    _cors_env: str = os.getenv("CORS_ALLOWED_ORIGINS", "")

    # Paths
    ROBOT_PROJECT_ROOT: str = os.getenv("ROBOT_PROJECT_ROOT", os.getcwd())
    CONFIG_DIR: str = os.getenv("CONFIG_DIR", os.path.join(ROBOT_PROJECT_ROOT, "config"))
    LOG_DIR: str = os.getenv("LOG_DIR", os.path.join(ROBOT_PROJECT_ROOT, "logs"))

    # Email (optional for reporting)
    EMAIL_SMTP_HOST: Optional[str] = os.getenv("EMAIL_SMTP_HOST") or None
    EMAIL_SMTP_PORT: Optional[int] = (
        int(os.getenv("EMAIL_SMTP_PORT")) if os.getenv("EMAIL_SMTP_PORT") else None
    )
    EMAIL_SMTP_USER: Optional[str] = os.getenv("EMAIL_SMTP_USER") or None
    EMAIL_SMTP_PASS: Optional[str] = os.getenv("EMAIL_SMTP_PASS") or None

    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None

    def __init__(self, **data):
        super().__init__(**data)
        # Parse CORS allowed origins from comma-separated env string
        cors = [o.strip() for o in (self._cors_env or "").split(",") if o.strip()]
        # Fallback to wildcard in dev if not explicitly set
        self.CORS_ALLOWED_ORIGINS = cors if cors else ["*"]

        # Ensure important directories exist
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
            os.makedirs(self.LOG_DIR, exist_ok=True)
        except Exception:
            # Do not crash on startup for directory creation failure; downstream will handle
            pass


# Create a single settings instance for app-wide import
settings = _Settings()
