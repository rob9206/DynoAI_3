"""
DynoAI Database Connection and Session Management.

Provides SQLAlchemy engine configuration, session management, and
database initialization utilities.

Usage:
    from api.services.database import get_db, init_database

    # Initialize tables on startup
    init_database()

    # Use sessions
    with get_db() as db:
        runs = db.query(Run).filter(Run.status == "complete").all()
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.models.base import Base

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """
    Get database URL from environment.

    Supports:
        - SQLite (default): sqlite:///./dynoai.db
        - PostgreSQL: postgresql://user:pass@localhost:5432/dynoai

    Returns:
        Database connection URL
    """
    return os.getenv("DATABASE_URL", "sqlite:///./dynoai.db")


def _configure_sqlite_pragmas(dbapi_conn, connection_record) -> None:
    """
    Configure SQLite connection for better performance and reliability.

    Sets:
        - WAL mode for better concurrency
        - Foreign key enforcement
        - Synchronous mode for durability
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(database_url: Optional[str] = None) -> Engine:
    """
    Create SQLAlchemy engine with appropriate settings.

    Args:
        database_url: Optional override for database URL

    Returns:
        Configured SQLAlchemy Engine
    """
    url = database_url or get_database_url()

    # Engine configuration varies by database type
    if url.startswith("sqlite"):
        # SQLite-specific settings
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},  # Allow multi-threaded access
            pool_pre_ping=True,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )
        # Register SQLite pragma configuration
        event.listen(engine, "connect", _configure_sqlite_pragmas)
    else:
        # PostgreSQL and other databases
        engine = create_engine(
            url,
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
            pool_pre_ping=True,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )

    return engine


# Module-level engine and session factory (lazy initialization)
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """
    Get or create the database engine.

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        _engine = create_db_engine()
        logger.info(f"Database engine created: {get_database_url()}")
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get or create the session factory.

    Returns:
        SQLAlchemy sessionmaker instance
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def init_database(create_tables: bool = True) -> None:
    """
    Initialize the database.

    Creates all tables defined in the models if they don't exist.
    For production, use Alembic migrations instead.

    Args:
        create_tables: Whether to create tables (set False for Alembic-managed DBs)
    """
    engine = get_engine()

    if create_tables:
        # Import models to ensure they're registered
        from api.models import Run, RunFile  # noqa: F401

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session context manager.

    Handles session lifecycle, commit, and rollback automatically.

    Usage:
        with get_db() as db:
            run = db.query(Run).filter(Run.id == run_id).first()
            run.status = "complete"
            # Commits automatically on exit

    Yields:
        SQLAlchemy Session
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_engine() -> None:
    """
    Reset the database engine and session factory.

    Useful for testing or reconfiguration.
    """
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def check_database_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
