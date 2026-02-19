"""
JWT Authentication Routes for DynoAI.

Endpoints:
  POST /api/auth/register  — owner only, create a user
  POST /api/auth/login     — public, returns JWT
  POST /api/auth/logout    — requires JWT, stateless (client discards token)
  GET  /api/auth/me        — requires JWT, returns current user
  GET  /api/users          — requires owner or tech role
  POST /api/users          — requires owner role, create user
  PUT  /api/users/<id>     — requires owner role, update user
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, g, jsonify, request

from api.services.database import SessionLocal

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

_VALID_ROLES = {"owner", "tech", "customer"}
_TOKEN_EXPIRY_HOURS = 24


def _jwt_secret() -> str:
    """Return the JWT signing secret from environment."""
    secret = os.environ.get("SECRET_KEY") or os.environ.get(
        "JWT_SECRET_KEY", "")
    if not secret:
        logger.warning(
            "SECRET_KEY / JWT_SECRET_KEY not set; using insecure fallback. "
            "Set a strong secret in production.")
        secret = "dynoai-insecure-dev-secret"
    return secret


def _encode_token(user_id: str) -> str:
    """Create a signed JWT for the given user ID."""
    payload = {
        "sub": user_id,
        "exp":
        datetime.now(tz=timezone.utc) + timedelta(hours=_TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT.  Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])


# ---------------------------------------------------------------------------
# Decorator helpers
# ---------------------------------------------------------------------------


def require_jwt(f):
    """Decorator: endpoint requires a valid Bearer JWT."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(
                {"error": "Authorization header missing or invalid"}), 401
        token = auth_header[len("Bearer "):]
        try:
            payload = _decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.PyJWTError:
            return jsonify({"error": "Invalid token"}), 401

        # Load user and stash on Flask g
        from api.models.user import User

        with SessionLocal() as session:
            user = session.get(User, payload["sub"])
            if user is None:
                return jsonify({"error": "User not found"}), 401
            # Detach a plain dict so we don't hold the session open
            g.current_user = user.to_dict()

        return f(*args, **kwargs)

    return wrapper


def require_roles(*roles):
    """Decorator: endpoint requires the current user to have one of *roles*.

    Must be applied *after* @require_jwt so that g.current_user is set.
    """

    def decorator(f):

        @wraps(f)
        @require_jwt
        def wrapper(*args, **kwargs):
            if g.current_user.get("role") not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_user_payload(data: dict, require_password: bool = True) -> tuple:
    """Return (error_message, None) or (None, cleaned_data)."""
    if not isinstance(data, dict):
        return "Request body must be JSON", None

    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "customer").strip().lower()

    if not email or "@" not in email:
        return "Valid email is required", None
    if require_password and not password:
        return "Password is required", None
    if require_password and len(password) < 8:
        return "Password must be at least 8 characters", None
    if not name:
        return "Name is required", None
    if role not in _VALID_ROLES:
        return f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}", None

    return None, {
        "email": email,
        "password": password,
        "name": name,
        "role": role
    }


def _create_user_from_data(cleaned: dict):
    """Create and persist a new User from validated payload.  Returns Flask response tuple."""
    from sqlalchemy.exc import IntegrityError

    from api.models.user import User

    with SessionLocal() as session:
        existing = session.query(User).filter_by(
            email=cleaned["email"]).first()
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        user = User(
            email=cleaned["email"],
            name=cleaned["name"],
            role=cleaned["role"],
        )
        user.set_password(cleaned["password"])
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return jsonify({"error": "Email already registered"}), 409

        session.refresh(user)
        return jsonify({"user": user.to_dict()}), 201


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@auth_bp.route("/auth/register", methods=["POST"])
@require_roles("owner")
def register():
    """POST /api/auth/register — owner only, creates a new user account."""
    data = request.get_json(silent=True) or {}
    err, cleaned = _validate_user_payload(data)
    if err:
        return jsonify({"error": err}), 400
    return _create_user_from_data(cleaned)


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """POST /api/auth/login — public, returns JWT on valid credentials."""
    from api.models.user import User

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email).first()
        if user is None or not user.check_password(password):
            return jsonify({"error": "Invalid email or password"}), 401

        token = _encode_token(user.id)
        return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
@require_jwt
def logout():
    """POST /api/auth/logout — stateless; instructs client to discard token."""
    return jsonify({"message": "logged out"}), 200


@auth_bp.route("/auth/me", methods=["GET"])
@require_jwt
def me():
    """GET /api/auth/me — returns the currently authenticated user."""
    return jsonify({"user": g.current_user}), 200


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------


@auth_bp.route("/users", methods=["GET"])
@require_roles("owner", "tech")
def list_users():
    """GET /api/users — owner or tech may list all users."""
    from api.models.user import User

    with SessionLocal() as session:
        users = session.query(User).order_by(User.created_at).all()
        return jsonify({"users": [u.to_dict() for u in users]}), 200


@auth_bp.route("/users", methods=["POST"])
@require_roles("owner")
def create_user():
    """POST /api/users — owner only, creates a new user account."""
    data = request.get_json(silent=True) or {}
    err, cleaned = _validate_user_payload(data)
    if err:
        return jsonify({"error": err}), 400
    return _create_user_from_data(cleaned)


@auth_bp.route("/users/<user_id>", methods=["PUT"])
@require_roles("owner")
def update_user(user_id: str):
    """PUT /api/users/<id> — owner only, update name, role, or password."""
    from api.models.user import User

    data = request.get_json(silent=True) or {}

    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            return jsonify({"error": "User not found"}), 404

        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return jsonify({"error": "Name cannot be empty"}), 400
            user.name = name

        if "role" in data:
            role = (data["role"] or "").strip().lower()
            if role not in _VALID_ROLES:
                return (
                    jsonify({
                        "error":
                        f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}"
                    }),
                    400,
                )
            user.role = role

        if "active" in data:
            user.active = bool(data["active"])

        if "password" in data:
            password = data["password"]
            if len(password) < 8:
                return jsonify(
                    {"error": "Password must be at least 8 characters"}), 400
            user.set_password(password)

        session.commit()
        session.refresh(user)
        return jsonify({"user": user.to_dict()}), 200
