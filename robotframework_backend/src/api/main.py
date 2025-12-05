from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.core.settings import settings
from src.db.database import init_db, get_db, get_engine_url
from src.api.routes import router as robot_router

app = FastAPI(
    title="RobotFramework Backend API",
    description="Backend API for orchestrating Robot Framework test execution, logs, and state.",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Health and diagnostics"},
        {"name": "db", "description": "Database operations and diagnostics"},
        {"name": "robot", "description": "Robot run orchestration, logs, config, and state APIs"},
    ],
)

# Configure CORS from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database at startup
@app.on_event("startup")
def on_startup() -> None:
    """Application startup hook to initialize resources like the database."""
    init_db()


# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check", description="Simple liveness probe that returns a healthy message.")
def health_check():
    """Return a simple health status."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/db_info",
    tags=["db"],
    summary="Database Info",
    description="Returns information about the configured database engine URL.",
)
def db_info():
    """Return the effective SQLAlchemy engine URL."""
    return {"engine_url": get_engine_url()}


# PUBLIC_INTERFACE
@app.get(
    "/db_check",
    tags=["db"],
    summary="Database Check",
    description="Verify that a DB session can be created and a simple query executed.",
)
def db_check(db: Session = Depends(get_db)):
    """Open a session and run a minimal query to verify DB connectivity."""
    # SQLAlchemy 2.0 will accept text SQL in execute for simple checks
    db.execute("SELECT 1")
    return {"ok": True}


# Include robot orchestration routes
app.include_router(robot_router)
