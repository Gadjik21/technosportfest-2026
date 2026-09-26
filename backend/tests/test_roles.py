"""Тесты динамических ролей: каталог прав, CRUD ролей, назначение пользователям.

Проверяют ключевой сценарий фичи: master admin создаёт роль «Копирайтер» с
правами только на новости, назначает её пользователю — тот публикует новости,
но не может трогать соревнования. Плюс защита системных ролей и ролей в работе.
"""

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
from app.modules.identity.models import User
from app.modules.identity.permissions import ALL_PERMISSIONS, ROLE_ATHLETE, ROLE_MASTER_ADMIN, ROLE_ORGANIZER
from app.modules.identity.roles import ensure_system_roles, get_role_by_name
from app.modules.identity.security import COOKIE_NAME, create_token, password_hash
from app.modules.results import models as results_models  # noqa: F401: registers metadata

ORIGIN = {"Origin": "http://localhost:5173"}


class Env:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.app = create_app()

        def override_db():
            with self.sessions() as db:
                yield db

        self.app.dependency_overrides[get_db] = override_db
        self.client = TestClient(self.app)

    def login(self, role_name: str, permissions: list[str] | None = None) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, create_token(uuid4(), role_name, permissions or []), path="/api/v1")

    def create_user_with_role(self, email: str, role_name: str) -> User:
        ensure_system_roles_in_tests(self.sessions)
        with self.sessions() as db:
            role = get_role_by_name(db, role_name)
            assert role is not None
            user = User(email=email, password_hash=password_hash.hash("long-demo-password"), role_id=role.id)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

def ensure_system_roles_in_tests(sessions) -> None:
    with sessions() as db:
        ensure_system_roles(db)


def test_permission_catalog_and_auth_me_permissions():
    env = Env()
    ensure_system_roles_in_tests(env.sessions)
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)

    catalog = env.client.get("/api/v1/admin/permissions")
    assert catalog.status_code == 200
    sections = {group["section"] for group in catalog.json()}
    assert {"news", "documents", "competitions", "contests", "results", "users", "roles"} <= sections
    news = next(group for group in catalog.json() if group["section"] == "news")
    assert news["codes"] == ["news.view", "news.create", "news.edit", "news.delete"]

    # Регистрация всегда даёт роль athlete и пустой набор прав.
    registered = env.client.post(
        "/api/v1/auth/register",
        json={"email": "athlete@example.com", "password": "long-demo-password", "fullName": "Амина Алиева"},
        headers=ORIGIN,
    )
    assert registered.status_code == 201
    body = registered.json()
    assert body["role"] == ROLE_ATHLETE
    assert body["permissions"] == []
    me = env.client.get("/api/v1/auth/me")
    assert me.json()["role"] == ROLE_ATHLETE
    assert me.json()["permissions"] == []


def test_auth_me_refreshes_permissions_after_role_change():
    env = Env()
    user = env.create_user_with_role("admin@example.com", ROLE_ORGANIZER)
    login = env.client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "long-demo-password"},
        headers=ORIGIN,
    )
    assert login.status_code == 200
    assert env.client.get("/api/v1/admin/permissions").status_code == 403

    with env.sessions() as db:
        admin_role = get_role_by_name(db, ROLE_MASTER_ADMIN)
        assert admin_role is not None
        db.get(User, user.id).role_id = admin_role.id
        db.commit()

    me = env.client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == ROLE_MASTER_ADMIN
    assert "roles.manage" in me.json()["permissions"]
    assert env.client.get("/api/v1/admin/permissions").status_code == 200


def test_role_crud_and_system_role_protection():
    env = Env()
    ensure_system_roles_in_tests(env.sessions)
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)

    created = env.client.post(
        "/api/v1/admin/roles",
        json={"name": "Копирайтер", "description": "Публикует новости", "permissions": ["news.view", "news.create", "news.edit"]},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    assert created.json()["isSystem"] is False
    assert created.json()["permissions"] == ["news.create", "news.edit", "news.view"]

    duplicate = env.client.post("/api/v1/admin/roles", json={"name": "Копирайтер", "permissions": []}, headers=ORIGIN)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ROLE_EXISTS"

    unknown_perm = env.client.post(
        "/api/v1/admin/roles", json={"name": "Сломанная", "permissions": ["news.hack"]}, headers=ORIGIN
    )
    assert unknown_perm.status_code == 422

    patched = env.client.patch(f"/api/v1/admin/roles/{role_id}", json={"name": "Контент-менеджер"}, headers=ORIGIN)
    assert patched.status_code == 200
    assert patched.json()["name"] == "Контент-менеджер"

    permissions_updated = env.client.put(
        f"/api/v1/admin/roles/{role_id}/permissions", json={"permissions": ["news.create", "news.delete"]}, headers=ORIGIN
    )
    assert permissions_updated.status_code == 200
    assert permissions_updated.json()["permissions"] == ["news.create", "news.delete"]

    listing = env.client.get("/api/v1/admin/roles")
    assert listing.status_code == 200
    names = {role["name"] for role in listing.json()}
    assert {"athlete", "organizer", "master-admin", "Контент-менеджер"} <= names

    # Системные роли нельзя менять и удалять.
    with env.sessions() as db:
        athlete_role = get_role_by_name(db, ROLE_ATHLETE)
        assert athlete_role is not None
        system_role_id = str(athlete_role.id)
    assert env.client.patch(f"/api/v1/admin/roles/{system_role_id}", json={"name": "new-name"}, headers=ORIGIN).json()["code"] == "ROLE_SYSTEM"
    assert env.client.put(f"/api/v1/admin/roles/{system_role_id}/permissions", json={"permissions": ["news.create"]}, headers=ORIGIN).status_code == 403
    assert env.client.delete(f"/api/v1/admin/roles/{system_role_id}", headers=ORIGIN).status_code == 403

    # Роль, назначенную пользователю, удалить нельзя.
    assert env.client.delete(f"/api/v1/admin/roles/{role_id}", headers=ORIGIN).status_code == 204
    judge_role_id = env.client.post(
        "/api/v1/admin/roles", json={"name": "Судья", "permissions": ["contests.grade"]}, headers=ORIGIN
    ).json()["id"]
    judge = env.create_user_with_role("judge@example.com", ROLE_ATHLETE)
    assigned = env.client.put(f"/api/v1/admin/users/{judge.id}/role", json={"roleId": judge_role_id}, headers=ORIGIN)
    assert assigned.status_code == 200
    blocked = env.client.delete(f"/api/v1/admin/roles/{judge_role_id}", headers=ORIGIN)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "ROLE_IN_USE"


def test_copywriter_can_publish_news_but_not_touch_competitions():
    env = Env()
    ensure_system_roles_in_tests(env.sessions)
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)

    copywriter_role_id = env.client.post(
        "/api/v1/admin/roles",
        json={"name": "Копирайтер", "permissions": ["news.view", "news.create", "news.edit"]},
        headers=ORIGIN,
    ).json()["id"]
    user = env.create_user_with_role("copy@example.com", ROLE_ATHLETE)
    assigned = env.client.put(f"/api/v1/admin/users/{user.id}/role", json={"roleId": copywriter_role_id}, headers=ORIGIN)
    assert assigned.status_code == 200
    assert assigned.json()["roleName"] == "Копирайтер"
    assert assigned.json()["fullName"] is None

    # Копирайтер работает от роли с правами новостей — как после релогина.
    env.login("Копирайтер", ["news.view", "news.create", "news.edit"])
    news = env.client.post("/api/v1/news", json={"title": "Новость фестиваля", "body": "Текст"}, headers=ORIGIN)
    assert news.status_code == 201
    edited = env.client.patch(f"/api/v1/news/{news.json()['id']}", json={"title": "Обновлённая"}, headers=ORIGIN)
    assert edited.status_code == 200

    # А вот соревнования недоступны: нет прав competitions.*.
    forbidden = env.client.post(
        "/api/v1/competitions",
        json={
            "title": "Турнир",
            "disciplineId": str(uuid4()),
            "startsAt": "2026-12-01T10:00:00Z",
            "endsAt": "2026-12-01T13:00:00Z",
            "registrationDeadline": "2026-11-30T10:00:00Z",
            "format": "online",
            "description": "Описание",
        },
        headers=ORIGIN,
    )
    assert forbidden.status_code == 403
    assert env.client.get("/api/v1/competitions", params={"status": "draft"}).status_code == 403


def test_users_list_shows_roles_and_full_names():
    env = Env()
    ensure_system_roles_in_tests(env.sessions)
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)

    registered = env.client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "long-demo-password", "fullName": "Спортсмен Тест"},
        headers=ORIGIN,
    )
    assert registered.status_code == 201
    # Регистрация залогинила нас спортсменом — возвращаемся под master admin.
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)

    page = env.client.get("/api/v1/admin/users")
    assert page.status_code == 200
    assert page.json()["total"] >= 1
    row = next(item for item in page.json()["items"] if item["email"] == "user@example.com")
    assert row["roleName"] == ROLE_ATHLETE
    assert row["fullName"] == "Спортсмен Тест"

    # Без users.manage список пользователей недоступен даже у организатора.
    env.login(ROLE_ORGANIZER, [code for code in ALL_PERMISSIONS if code not in {"users.manage", "roles.manage"}])
    assert env.client.get("/api/v1/admin/users").status_code == 403
    assert env.client.get("/api/v1/admin/roles").status_code == 403
    env.login(ROLE_MASTER_ADMIN, ALL_PERMISSIONS)
    assert env.client.get("/api/v1/admin/users").status_code == 200
