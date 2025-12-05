from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Float,
    Index,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.db.database import Base


class TestRun(Base):
    """Represents a single Robot Framework test run execution session."""
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project: Mapped[Optional[str]] = mapped_column(String(200), index=True, nullable=True)
    suite_name: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)  # running|passed|failed|stopped|error
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    logs_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    case_results: Mapped[list["TestCaseResult"]] = relationship(
        "TestCaseResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    batch_logs: Mapped[list["BatchLog"]] = relationship(
        "BatchLog",
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fail_logs: Mapped[list["FailLog"]] = relationship(
        "FailLog",
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_test_runs_status_start_time", "status", "start_time"),
    )


class TestCaseResult(Base):
    """Represents the result of an individual test case within a run."""
    __tablename__ = "test_case_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    case_name: Mapped[str] = mapped_column(String(255), index=True)
    suite_name: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)  # passed|failed|skipped
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relations
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="case_results")

    __table_args__ = (
        Index("ix_case_results_run_status", "test_run_id", "status"),
        Index("ix_case_results_suite_case", "suite_name", "case_name"),
    )


class BatchLog(Base):
    """Represents line-by-line or chunked batch logs emitted during a test run."""
    __tablename__ = "batch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO", index=True)
    message: Mapped[str] = mapped_column(Text)

    # Relations
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="batch_logs")

    __table_args__ = (
        Index("ix_batch_logs_run_time", "test_run_id", "timestamp"),
        Index("ix_batch_logs_run_level", "test_run_id", "level"),
    )


class FailLog(Base):
    """Represents failure logs and diagnostics for test failures."""
    __tablename__ = "fail_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    case_result_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("test_case_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relations
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="fail_logs")
    case_result: Mapped[Optional["TestCaseResult"]] = relationship("TestCaseResult")

    __table_args__ = (
        Index("ix_fail_logs_run_time", "test_run_id", "timestamp"),
        Index("ix_fail_logs_run_error", "test_run_id", "error_type"),
    )
