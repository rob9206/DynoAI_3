"""
User model for DynoAI authentication.

Stores user accounts with role-based access control.
Roles: owner, tech, customer
"""

import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import Column, DateTime, String

from api.models.base import Base


class User(Base):
    """
    User account record.

    Stores credentials and role information for JWT-based authentication.
    """

    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="User UUID",
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="customer",
        comment="Role: owner, tech, customer",
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password."""
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def to_dict(self) -> dict:
        """Return a safe, serialisable representation (no password_hash)."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User(id='{self.id}', email='{self.email}', role='{self.role}')>"
