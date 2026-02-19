"""
Tests for the JWT authentication blueprint (api/routes/auth.py).

Covers:
- User registration (owner only)
- Login / logout
- GET /api/auth/me
- GET /api/users (owner or tech)
- POST /api/users (owner only)
- PUT /api/users/<id> (owner only)
- Role-based access control
- Input validation
"""

import os
import sys
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.base import Base
from api.models.user import User
from api.routes.auth import _encode_token, auth_bp

# Ensure project root is in path before any imports
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("DYNOAI_DEBUG", "false")
os.environ.setdefault("JETSTREAM_STUB_MODE", "true")
os.environ.setdefault("JETSTREAM_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-jwt-secret-key-for-testing-only")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_app(tmp_path):
    """Isolated Flask app with an in-memory SQLite DB for auth tests."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(auth_bp)

    # Use an isolated in-memory database for every test
    db_path = f"sqlite:///{tmp_path}/test_auth.db"
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    # Patch the SessionLocal used by the blueprint
    import api.routes.auth as auth_module

    original_session = auth_module.SessionLocal
    auth_module.SessionLocal = TestSession

    yield app

    auth_module.SessionLocal = original_session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(auth_app):
    with auth_app.test_client() as c:
        yield c


@pytest.fixture
def owner_user(auth_app):
    """Create an owner user and return (user_dict, token)."""
    import api.routes.auth as auth_module

    with auth_module.SessionLocal() as session:
        u = User(email="owner@example.com", name="Owner User", role="owner")
        u.set_password("ownerpassword1")
        session.add(u)
        session.commit()
        session.refresh(u)
        user_dict = u.to_dict()

    token = _encode_token(user_dict["id"])
    return user_dict, token


@pytest.fixture
def tech_user(auth_app, owner_user):
    """Create a tech user directly in the database."""
    import api.routes.auth as auth_module

    _, owner_token = owner_user
    with auth_module.SessionLocal() as session:
        u = User(email="tech@example.com", name="Tech User", role="tech")
        u.set_password("techpassword1")
        session.add(u)
        session.commit()
        session.refresh(u)
        user_dict = u.to_dict()

    token = _encode_token(user_dict["id"])
    return user_dict, token


@pytest.fixture
def customer_user(auth_app):
    """Create a customer user."""
    import api.routes.auth as auth_module

    with auth_module.SessionLocal() as session:
        u = User(email="customer@example.com",
                 name="Customer User",
                 role="customer")
        u.set_password("customerpassword1")
        session.add(u)
        session.commit()
        session.refresh(u)
        user_dict = u.to_dict()

    token = _encode_token(user_dict["id"])
    return user_dict, token


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:

    def test_login_success(self, client, owner_user):
        owner, _ = owner_user
        resp = client.post(
            "/api/auth/login",
            json={
                "email": owner["email"],
                "password": "ownerpassword1"
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == owner["email"]
        assert data["user"]["role"] == "owner"
        assert "password_hash" not in data["user"]

    def test_login_wrong_password(self, client, owner_user):
        owner, _ = owner_user
        resp = client.post(
            "/api/auth/login",
            json={
                "email": owner["email"],
                "password": "wrongpassword"
            },
        )
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post(
            "/api/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "password"
            },
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"email": "a@b.com"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------


class TestLogout:

    def test_logout_with_valid_token(self, client, owner_user):
        _, token = owner_user
        resp = client.post("/api/auth/logout",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "logged out"

    def test_logout_without_token(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_with_invalid_token(self, client):
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer bogus.token.here"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me tests
# ---------------------------------------------------------------------------


class TestMe:

    def test_me_returns_current_user(self, client, owner_user):
        user, token = owner_user
        resp = client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["id"] == user["id"]
        assert data["user"]["email"] == user["email"]

    def test_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/auth/register tests
# ---------------------------------------------------------------------------


class TestRegister:

    def test_register_as_owner_creates_user(self, client, owner_user):
        _, token = owner_user
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "strongpassword1",
                "name": "New User",
                "role": "tech",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["role"] == "tech"

    def test_register_without_token_is_401(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "anon@example.com",
                "password": "strongpassword1",
                "name": "Anon",
                "role": "customer",
            },
        )
        assert resp.status_code == 401

    def test_register_as_tech_is_403(self, client, tech_user):
        _, token = tech_user
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "another@example.com",
                "password": "strongpassword1",
                "name": "Another",
                "role": "customer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_register_duplicate_email_is_409(self, client, owner_user):
        owner, token = owner_user
        resp = client.post(
            "/api/auth/register",
            json={
                "email": owner["email"],
                "password": "strongpassword1",
                "name": "Dup",
                "role": "customer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_register_invalid_role_is_400(self, client, owner_user):
        _, token = owner_user
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "x@example.com",
                "password": "strongpassword1",
                "name": "X",
                "role": "superadmin",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_register_short_password_is_400(self, client, owner_user):
        _, token = owner_user
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "y@example.com",
                "password": "short",
                "name": "Y",
                "role": "customer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/users tests
# ---------------------------------------------------------------------------


class TestListUsers:

    def test_owner_can_list_users(self, client, owner_user):
        _, token = owner_user
        resp = client.get("/api/users",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        assert isinstance(data["users"], list)
        assert len(data["users"]) >= 1

    def test_tech_can_list_users(self, client, tech_user):
        _, token = tech_user
        resp = client.get("/api/users",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_customer_cannot_list_users(self, client, customer_user):
        _, token = customer_user
        resp = client.get("/api/users",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list_users(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/users tests
# ---------------------------------------------------------------------------


class TestCreateUser:

    def test_owner_can_create_user(self, client, owner_user):
        _, token = owner_user
        resp = client.post(
            "/api/users",
            json={
                "email": "created@example.com",
                "password": "createdpassword",
                "name": "Created User",
                "role": "customer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["email"] == "created@example.com"

    def test_tech_cannot_create_user(self, client, tech_user):
        _, token = tech_user
        resp = client.post(
            "/api/users",
            json={
                "email": "denied@example.com",
                "password": "deniedpassword",
                "name": "Denied",
                "role": "customer",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/users/<id> tests
# ---------------------------------------------------------------------------


class TestUpdateUser:

    def test_owner_can_update_name(self, client, owner_user, customer_user):
        _, token = owner_user
        customer, _ = customer_user
        resp = client.put(
            f"/api/users/{customer['id']}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["user"]["name"] == "Updated Name"

    def test_owner_can_update_role(self, client, owner_user, customer_user):
        _, token = owner_user
        customer, _ = customer_user
        resp = client.put(
            f"/api/users/{customer['id']}",
            json={"role": "tech"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["user"]["role"] == "tech"

    def test_update_nonexistent_user_is_404(self, client, owner_user):
        _, token = owner_user
        resp = client.put(
            "/api/users/00000000-0000-0000-0000-000000000000",
            json={"name": "Nobody"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_tech_cannot_update_user(self, client, tech_user, customer_user):
        _, token = tech_user
        customer, _ = customer_user
        resp = client.put(
            f"/api/users/{customer['id']}",
            json={"name": "Attempted"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_update_invalid_role_is_400(self, client, owner_user,
                                        customer_user):
        _, token = owner_user
        customer, _ = customer_user
        resp = client.put(
            f"/api/users/{customer['id']}",
            json={"role": "superadmin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
