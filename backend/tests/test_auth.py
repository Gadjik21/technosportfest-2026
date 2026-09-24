import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.modules.identity.models import AthleteProfile, User  # noqa: F401: registers metadata
from app.modules.identity.security import COOKIE_NAME, Principal, create_token, require_role


def client_with_db() -> TestClient:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    @app.get("/api/v1/test/organizer")
    def organizer_only(_: Principal = Depends(require_role("organizer"))):
        return {"ok": True}

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_registration_login_and_logout():
    client = client_with_db()
    origin = {"Origin": "http://localhost:5173"}
    body = {"email": "Athlete@Example.com", "password": "long-demo-password", "fullName": "Амина Алиева"}

    assert client.get("/api/v1/auth/me").status_code == 401
    registered = client.post("/api/v1/auth/register", json=body, headers=origin)
    assert registered.status_code == 201
    assert registered.json()["role"] == "athlete"
    assert registered.json()["email"] == "athlete@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/register", json=body, headers=origin).json()["code"] == "EMAIL_TAKEN"

    logout = client.post("/api/v1/auth/logout", headers=origin)
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": body["email"], "password": "bad"}, headers=origin).json()["code"] == "INVALID_CREDENTIALS"
    assert client.post("/api/v1/auth/login", json={"email": body["email"], "password": body["password"]}, headers=origin).status_code == 200


def test_mutation_requires_origin_and_public_registration_cannot_choose_role():
    client = client_with_db()
    body = {"email": "athlete@example.com", "password": "long-demo-password", "fullName": "Амина Алиева"}
    assert client.post("/api/v1/auth/register", json=body).json()["code"] == "ORIGIN_INVALID"
    assert client.post("/api/v1/auth/register", json={**body, "role": "organizer"}, headers={"Origin": "http://localhost:5173"}).status_code == 422


def test_role_guard_rejects_athlete_and_accepts_organizer_token():
    client = client_with_db()
    origin = {"Origin": "http://localhost:5173"}
    assert client.get("/api/v1/test/organizer").status_code == 401
    client.post("/api/v1/auth/register", json={"email": "athlete@example.com", "password": "long-demo-password", "fullName": "Амина Алиева"}, headers=origin)
    assert client.get("/api/v1/test/organizer").status_code == 403
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, create_token(uuid4(), "organizer"), path="/api/v1")
    assert client.get("/api/v1/test/organizer").status_code == 200
