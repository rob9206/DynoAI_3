"""
Database connection and session management for DynoAI.

Provides:
- Database initialization
- Connection pooling
- Session context managers
- SQLite and PostgreSQL support
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================


def get_database_url() -> str:
    """
    Get database URL from environment.

    Defaults to SQLite if DATABASE_URL not set.

    Returns:
        Database connection URL
    """
    return os.getenv("DATABASE_URL", "sqlite:///./dynoai.db")


def is_sqlite(url: str) -> bool:
    """Check if database URL is SQLite."""
    return url.startswith("sqlite")


# =============================================================================
# Engine Configuration
# =============================================================================


def create_db_engine() -> Engine:
    """
    Create SQLAlchemy engine with appropriate settings.

    Returns:
        Configured SQLAlchemy engine
    """
    url = get_database_url()

    # SQLite-specific settings
    if is_sqlite(url):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},  # Allow multi-threading
            poolclass=StaticPool,  # Use static pool for SQLite
            echo=False,  # Set to True for SQL debug logging
        )

        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info(f"Database initialized: SQLite ({url})")

    # PostgreSQL/MySQL settings
    else:
        engine = create_engine(
            url,
            pool_size=5,  # Connection pool size
            max_overflow=10,  # Max overflow connections
            pool_pre_ping=True,  # Verify connections before using
            echo=False,
        )

        logger.info(
            f"Database initialized: {url.split('@')[0]}..."
        )  # Don't log credentials

    return engine


# Create global engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# =============================================================================
# Initialization
# =============================================================================


def init_database():
    """
    Initialize database tables.

    Creates all tables defined in Base.metadata.
    Safe to call multiple times (won't recreate existing tables).
    """
    from api.models import Base

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


def drop_all_tables():
    """
    Drop all database tables.

    ⚠️ WARNING: This deletes all data! Only use for testing or development.
    """
    from api.models import Base

    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


# =============================================================================
# Session Management
# =============================================================================


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session context manager.

    Usage:
        with get_db() as db:
            run = Run(id="test", status="pending")
            db.add(run)
            # Auto-commits on success, rolls back on exception

    Yields:
        Database session

    Automatically commits on success, rolls back on exception.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session (manual management).

    Returns:
        Database session

    Note: Caller is responsible for committing and closing the session.
    Prefer using get_db() context manager when possible.
    """
    return SessionLocal()


# =============================================================================
# Utilities
# =============================================================================


def get_database_info() -> dict:
    """
    Get database connection information.

    Returns:
        Dictionary with database info (safe for logging)
    """
    url = get_database_url()

    if is_sqlite(url):
        return {
            "type": "sqlite",
            "url": url,
            "pool_size": "N/A (StaticPool)",
        }
    else:
        # Don't expose credentials
        safe_url = url.split("@")[0] if "@" in url else url
        return {
            "type": "postgresql" if "postgresql" in url else "other",
            "url": safe_url + "@...",
            "pool_size": engine.pool.size(),
        }


def test_connection() -> bool:
    """
    Test database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


# =============================================================================
# CLI Utilities
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "init":
            print("Initializing database...")
            init_database()
            print("✓ Database initialized")

        elif command == "info":
            info = get_database_info()
            print("\nDatabase Information:")
            print(f"  Type: {info['type']}")
            print(f"  URL: {info['url']}")
            print(f"  Pool Size: {info['pool_size']}")

        elif command == "test":
            print("Testing database connection...")
            if test_connection():
                print("✓ Connection successful")
            else:
                print("✗ Connection failed")
                sys.exit(1)

        elif command == "drop":
            confirm = input("⚠️  This will delete all data! Type 'yes' to confirm: ")
            if confirm.lower() == "yes":
                drop_all_tables()
                print("✓ All tables dropped")
            else:
                print("Cancelled")

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Usage: python -m api.services.database [init|info|test|drop]")
