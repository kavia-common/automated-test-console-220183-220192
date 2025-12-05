import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# Load database URL from environment with fallback to local SQLite file
# Note: Ensure the environment variable DATABASE_URL is set by the orchestrator in .env.
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "app.db")
os.makedirs(os.path.dirname(DEFAULT_SQLITE_PATH), exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or DATABASE_URL.strip() == "":
    # SQLite URL format for SQLAlchemy
    DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"

# Create SQLAlchemy engine
# For SQLite, check_same_thread must be False for use with FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# PUBLIC_INTERFACE
def init_db() -> None:
    """Create database tables for all models imported into Base.metadata."""
    # Import models inside the function to ensure registration without unused import warnings.
    from src.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


# PUBLIC_INTERFACE
def get_engine_url() -> str:
    """Return the effective SQLAlchemy database URL (for diagnostics/logs)."""
    return DATABASE_URL
