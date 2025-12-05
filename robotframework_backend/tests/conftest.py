import os
import shutil
import tempfile
from contextlib import contextmanager

# Third-party imports at top to satisfy E402
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# IMPORTANT: Configure temp paths in env BEFORE importing app/settings-dependent modules.
# This ensures CONFIG_DIR/LOG_DIR/ROBOT_PROJECT_ROOT are isolated per test session.
_tmp_root = tempfile.mkdtemp(prefix="rf_backend_tests_")  # noqa: E402
os.environ.setdefault("ROBOT_PROJECT_ROOT", os.path.join(_tmp_root, "robot"))  # noqa: E402
os.environ.setdefault("CONFIG_DIR", os.path.join(_tmp_root, "configs"))  # noqa: E402
os.environ.setdefault("LOG_DIR", os.path.join(_tmp_root, "logs"))  # noqa: E402

# Now it's safe to import app and settings
from src.db.database import Base  # noqa: E402
from src.core.settings import settings  # noqa: E402
from src.api.main import app  # noqa: E402

# Note on settings:
# settings is instantiated on import reading env once. We still mutate specific fields below to
# guarantee they match the isolated temp directories for this pytest session.


@pytest.fixture(scope="session")
def tmp_workdir():
    """Session-scoped temp working directory to host LOG_DIR, CONFIG_DIR, and SQLite file."""
    # Use the precreated root so that imports above already read the correct env
    try:
        yield _tmp_root
    finally:
        shutil.rmtree(_tmp_root, ignore_errors=True)


@pytest.fixture(scope="session")
def test_paths(tmp_workdir):
    logs = os.path.join(tmp_workdir, "logs")
    configs = os.path.join(tmp_workdir, "configs")
    robot_root = os.path.join(tmp_workdir, "robot")
    os.makedirs(logs, exist_ok=True)
    os.makedirs(configs, exist_ok=True)
    os.makedirs(robot_root, exist_ok=True)
    return {"LOG_DIR": logs, "CONFIG_DIR": configs, "ROBOT_PROJECT_ROOT": robot_root}


@pytest.fixture(scope="session")
def test_db_engine(tmp_workdir):
    # Create isolated SQLite database for tests
    db_path = os.path.join(tmp_workdir, "test_app.db")
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(test_db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)


@contextmanager
def _test_db_session_factory(SessionLocal):
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def override_settings_and_env(test_paths, test_db_engine):
    """
    Override settings directories and simulate USE_SSE enabled by default for most tests.
    Some tests can toggle USE_SSE via monkeypatch.
    """
    # Ensure environment reflects isolated temp dirs (already set pre-import, but keep consistent)
    os.environ["LOG_DIR"] = test_paths["LOG_DIR"]
    os.environ["CONFIG_DIR"] = test_paths["CONFIG_DIR"]
    os.environ["ROBOT_PROJECT_ROOT"] = test_paths["ROBOT_PROJECT_ROOT"]

    # Mutate settings instance paths so code importing settings uses test directories
    settings.LOG_DIR = test_paths["LOG_DIR"]
    settings.CONFIG_DIR = test_paths["CONFIG_DIR"]
    settings.ROBOT_PROJECT_ROOT = test_paths["ROBOT_PROJECT_ROOT"]
    # generic defaults
    settings.USE_SSE = True
    # Ensure directories exist
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    os.makedirs(settings.CONFIG_DIR, exist_ok=True)
    os.makedirs(settings.ROBOT_PROJECT_ROOT, exist_ok=True)
    yield


@pytest.fixture()
def app_client(TestSessionLocal, monkeypatch):
    """
    Provide a FastAPI TestClient with DB dependency overridden to the test engine,
    and CORS configured to allow localhost origin for headers verification.
    """
    from src.db import database as db_module

    # Override SessionLocal used by the app code paths calling SessionLocal() directly
    monkeypatch.setattr(db_module, "SessionLocal", TestSessionLocal, raising=True)

    # Also ensure engine_url function reports sqlite memory-ish for safety
    def fake_get_engine_url() -> str:
        return "sqlite:///test_app.db"

    monkeypatch.setattr(db_module, "get_engine_url", fake_get_engine_url, raising=True)

    # Override FastAPI dependency get_db to use TestSessionLocal
    def get_db_override():
        with _test_db_session_factory(TestSessionLocal) as db:
            yield db

    from src.db.database import get_db as original_get_db
    app.dependency_overrides[original_get_db] = get_db_override

    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def db_session(TestSessionLocal):
    """Direct DB session for repository-level tests."""
    with _test_db_session_factory(TestSessionLocal) as db:
        yield db
