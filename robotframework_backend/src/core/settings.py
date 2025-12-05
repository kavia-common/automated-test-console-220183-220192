import os
from typing import List, Optional

from pydantic import BaseModel
from dotenv import load_dotenv


# Load environment from a .env file if present (backend container root)
# This enables local development without needing to export variables.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"), override=False)


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
    # Default ROBOT_PROJECT_ROOT to ./robot inside the backend root for local dev
    ROBOT_PROJECT_ROOT: str = os.getenv(
        "ROBOT_PROJECT_ROOT",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "robot"),
    )
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
        # Fallback defaults for local development: include frontend origin explicitly
        if not cors:
            cors = ["http://localhost:3000"]
        self.CORS_ALLOWED_ORIGINS = cors

        # Avoid auto-creating directories during tests; consumers will ensure existence when writing.
        # This prevents tests from observing unexpected folders being created.
        # If needed at runtime, modules performing writes will create directories explicitly.
        # Intentionally do not create CONFIG_DIR or LOG_DIR here.
        ...


# Create a single settings instance for app-wide import
settings = _Settings()
