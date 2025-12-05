# TASK-010: Database Persistence Layer

**Status:** 🟡 Ready for Work  
**Priority:** Medium  
**Estimated Effort:** 4-6 hours  
**Dependencies:** None

## Objective

Replace JSON file storage with SQLite/PostgreSQL database for run state persistence, enabling better querying, concurrent access, and data integrity.

## Deliverables

### 1. Add Dependencies

```bash
# Add to requirements.txt
sqlalchemy>=2.0.0
alembic>=1.13.0
# Optional for PostgreSQL
psycopg2-binary>=2.9.0
```

### 2. Create Database Models (`api/models/`)

```python
# api/models/run.py
"""Database models for DynoAI runs."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, JSON, Enum, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Run(Base):
    """Analysis run record."""
    
    __tablename__ = "runs"
    
    id = Column(String(64), primary_key=True)
    status = Column(String(20), nullable=False, index=True)
    source = Column(String(20), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Jetstream integration
    jetstream_id = Column(String(64), index=True, nullable=True)
    
    # Progress tracking
    current_stage = Column(String(50))
    progress_percent = Column(Integer, default=0)
    
    # Results
    results_summary = Column(JSON, nullable=True)
    error_info = Column(JSON, nullable=True)
    
    # Metadata
    input_filename = Column(String(255))
    config_snapshot = Column(JSON, nullable=True)


class RunFile(Base):
    """Output file from a run."""
    
    __tablename__ = "run_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))  # csv, json, txt
    size_bytes = Column(Integer)
    storage_path = Column(Text)  # Local path or S3 key
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3. Create Database Service (`api/services/database.py`)

```python
"""Database connection and session management."""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from api.models.run import Base


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "sqlite:///./dynoai.db"
    )


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Session:
    """Get database session context manager."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

### 4. Migration Support (Alembic)

```bash
# Initialize alembic
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial run tables"

# Apply migrations
alembic upgrade head
```

### 5. Update Run Manager

Modify `api/services/run_manager.py` to use database instead of JSON files.

### 6. Add Environment Variables

```bash
# SQLite (default)
DATABASE_URL=sqlite:///./dynoai.db

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/dynoai
```

## Acceptance Criteria

- [ ] SQLAlchemy models defined
- [ ] Database service with connection pooling
- [ ] Alembic migrations configured
- [ ] Run manager updated to use database
- [ ] Backward compatible with existing JSON data
- [ ] Migration script from JSON to DB
- [ ] PostgreSQL support tested
- [ ] Concurrent access tested
- [ ] Query performance acceptable

## Files to Create/Modify

- `/api/models/__init__.py` (new)
- `/api/models/run.py` (new)
- `/api/services/database.py` (new)
- `/api/services/run_manager.py` (modify)
- `/migrations/` (new directory)
- `/alembic.ini` (new)
- `/scripts/migrate_json_to_db.py` (new)

## Migration Strategy

1. Deploy with both JSON and DB support
2. Run migration script to copy existing data
3. Verify data integrity
4. Switch to DB-only mode
5. Archive JSON files

## Testing

```bash
# Run database tests
pytest tests/api/test_database.py -v

# Test migration
python scripts/migrate_json_to_db.py --dry-run
python scripts/migrate_json_to_db.py --execute
```

