import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.modules.content import models as content_models  # noqa: F401: registers metadata
from app.modules.identity.models import AthleteProfile, User  # noqa: F401: registers metadata
from app.modules.identity.security import COOKIE_NAME, create_token
from app.modules.results import models as results_models  # noqa: F401: registers metadata

ORIGIN = {"Origin": "http://localhost:5173"}


def client_with_db() -> TestClient:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _login_as_organizer(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, create_token(uuid4(), "organizer"), path="/api/v1")


def test_news_crud_and_public_listing():
    client = client_with_db()
    _login_as_organizer(client)

    created = client.post("/api/v1/news", json={"title": "Открытие фестиваля", "body": "Старт в 10:00"}, headers=ORIGIN)
    assert created.status_code == 201, created.text
    news_id = created.json()["id"]

    listing = client.get("/api/v1/news")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    patched = client.patch(f"/api/v1/news/{news_id}", json={"title": "Открытие перенесено"}, headers=ORIGIN)
    assert patched.status_code == 200
    assert patched.json()["title"] == "Открытие перенесено"
    assert patched.json()["body"] == "Старт в 10:00"

    empty_patch = client.patch(f"/api/v1/news/{news_id}", json={}, headers=ORIGIN)
    assert empty_patch.status_code == 422


def test_news_requires_organizer():
    client = client_with_db()
    body = {"email": "athlete@example.com", "password": "long-demo-password", "fullName": "Спортсмен"}
    client.post("/api/v1/auth/register", json=body, headers=ORIGIN)

    response = client.post("/api/v1/news", json={"title": "Новость", "body": "Текст"}, headers=ORIGIN)
    assert response.status_code == 403


def test_document_requires_https_url_and_supports_category_filter():
    client = client_with_db()
    _login_as_organizer(client)

    rejected = client.post("/api/v1/documents", json={"title": "Регламент", "category": "rules", "fileUrl": "http://example.com/doc.pdf"}, headers=ORIGIN)
    assert rejected.status_code == 422

    created = client.post("/api/v1/documents", json={"title": "Регламент", "category": "rules", "fileUrl": "https://example.com/doc.pdf"}, headers=ORIGIN)
    assert created.status_code == 201, created.text

    filtered = client.get("/api/v1/documents", params={"category": "rules"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    other = client.get("/api/v1/documents", params={"category": "other"})
    assert other.json()["total"] == 0
