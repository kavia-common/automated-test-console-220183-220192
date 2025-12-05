from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.db.database import init_db, get_db, get_engine_url

app = FastAPI(
    title="RobotFramework Backend API",
    description="Backend API for orchestrating Robot Framework test execution, logs, and state.",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Health and diagnostics"},
        {"name": "db", "description": "Database operations and diagnostics"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production via env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database at startup
@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", tags=["health"], summary="Health Check", description="Simple liveness probe that returns a healthy message.")
def health_check():
    return {"message": "Healthy"}


@app.get(
    "/db_info",
    tags=["db"],
    summary="Database Info",
    description="Returns information about the configured database engine URL.",
)
def db_info():
    return {"engine_url": get_engine_url()}


@app.get(
    "/db_check",
    tags=["db"],
    summary="Database Check",
    description="Verify that a DB session can be created and a simple query executed.",
)
def db_check(db: Session = Depends(get_db)):
    # Simple check by executing a lightweight statement
    db.execute("SELECT 1")
    return {"ok": True}
