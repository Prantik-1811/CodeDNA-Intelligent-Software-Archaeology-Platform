"""Database layer for CodeDNA backend.

SQLAlchemy models and session management for storing repositories,
analysis jobs, risk results, and impact reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="registered")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), default="email", nullable=False)
    provider_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RepositorySnapshot(Base):
    __tablename__ = "repository_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False, unique=True, index=True
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="pending")
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModuleRisk(Base):
    __tablename__ = "module_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    risk_score: Mapped[float] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="low")
    features_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ImpactReport(Base):
    __tablename__ = "impact_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    risk_score: Mapped[float] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="low")
    report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


# ---------------------------------------------------------------------------
# Engine / session helpers
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def init_db(database_url: str = "sqlite:///./codna.db") -> None:
    """Initialize the SQLAlchemy engine and create all tables."""
    global _engine, _SessionLocal
    _engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=_engine
    )


def get_session():
    """Return a new SQLAlchemy session."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def get_engine():
    if _engine is None:
        init_db()
    return _engine
