"""Тесты Б1: дисциплины, соревнования, заявки, участники, профиль.

Проверяют критерии PR из docs/work-items.md:
- повторная заявка не создаёт дубль (409 ALREADY_REGISTERED);
- после дедлайна заявка закрыта (409 REGISTRATION_CLOSED);
- спортсмен не вызывает организаторские методы (403);
- интеграция реального CompetitionPort с публикацией результатов Б2.
"""

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.modules.competitions.models import AthleteDiscipline, Competition, Discipline, Registration  # noqa: F401: registers metadata
from app.modules.content import models as content_models  # noqa: F401: registers metadata
from app.modules.identity.models import AthleteProfile, User  # noqa: F401: registers metadata
from app.modules.identity.security import COOKIE_NAME, create_token
from app.modules.results import models as results_models  # noqa: F401: registers metadata

ORIGIN = {"Origin": "http://localhost:5173"}


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def future(hours: float = 24) -> str:
    return iso_z(datetime.now(timezone.utc) + timedelta(hours=hours))


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

    def seed_discipline(self, name: str = "Алгоритмическое программирование") -> str:
        with self.sessions() as db:
            discipline = Discipline(name=name)
            db.add(discipline)
            db.commit()
            db.refresh(discipline)
            return str(discipline.id)

    def seed_competition_raw(self, discipline_id: str, status: str = "published") -> str:
        now = datetime.now(timezone.utc)
        with self.sessions() as db:
            competition = Competition(
                title="Прошедший турнир",
                discipline_id=UUID(discipline_id),
                starts_at=now - timedelta(days=1),
                ends_at=now - timedelta(days=1, hours=-3),
                registration_deadline=now - timedelta(days=2),
                format="online",
                description="Соревнование с закрытой регистрацией",
                status=status,
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)
            return str(competition.id)

    def register_athlete(self, email: str, full_name: str) -> str:
        body = {"email": email, "password": "long-demo-password", "fullName": full_name}
        response = self.client.post("/api/v1/auth/register", json=body, headers=ORIGIN)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def login_organizer(self) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, create_token(uuid4(), "organizer"), path="/api/v1")

    def login_as(self, user_id: str, role: str) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, create_token(UUID(user_id), role), path="/api/v1")

    def create_published_competition(self, discipline_id: str) -> str:
        self.login_organizer()
        body = {
            "title": "Турнир по алгоритмам",
            "disciplineId": discipline_id,
            "startsAt": future(48),
            "endsAt": future(51),
            "registrationDeadline": future(24),
            "format": "online",
            "description": "Описание турнира",
        }
        created = self.client.post("/api/v1/competitions", json=body, headers=ORIGIN)
        assert created.status_code == 201, created.text
        competition_id = created.json()["id"]
        published = self.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN)
        assert published.status_code == 200, published.text
        return competition_id


def test_disciplines_and_competition_lifecycle():
    env = Env()
    discipline_id = env.seed_discipline()

    disciplines = env.client.get("/api/v1/disciplines")
    assert disciplines.status_code == 200
    assert disciplines.json()[0]["name"] == "Алгоритмическое программирование"

    # Гость не создаёт соревнование (нет cookie), спортсмен тоже не может.
    env.register_athlete("athlete@example.com", "Спортсмен Тест")
    body = {
        "title": "Турнир по алгоритмам",
        "disciplineId": discipline_id,
        "startsAt": future(48),
        "endsAt": future(51),
        "registrationDeadline": future(24),
        "format": "online",
        "description": "Описание турнира",
    }
    assert env.client.post("/api/v1/competitions", json=body, headers=ORIGIN).status_code == 403

    env.login_organizer()
    created = env.client.post("/api/v1/competitions", json=body, headers=ORIGIN)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft"
    assert created.json()["registrationOpen"] is False
    competition_id = created.json()["id"]

    # Черновик не публикуется никому, кроме организатора.
    env.client.cookies.clear()
    assert env.client.get(f"/api/v1/competitions/{competition_id}").status_code == 404
    catalogue = env.client.get("/api/v1/competitions")
    assert catalogue.status_code == 200
    assert catalogue.json()["items"] == []
    assert env.client.get("/api/v1/competitions", params={"status": "draft"}).status_code == 403

    env.login_organizer()
    assert env.client.get(f"/api/v1/competitions/{competition_id}").status_code == 200
    draft_catalogue = env.client.get("/api/v1/competitions", params={"status": "draft"})
    assert draft_catalogue.status_code == 200
    assert len(draft_catalogue.json()["items"]) == 1

    # Редактирование только черновика.
    patched = env.client.patch(f"/api/v1/competitions/{competition_id}", json={"title": "Новый заголовок"}, headers=ORIGIN)
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "Новый заголовок"

    published = env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert env.client.patch(f"/api/v1/competitions/{competition_id}", json={"title": "Новое"}, headers=ORIGIN).status_code == 409
    assert env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN).json()["code"] == "INVALID_STATE"

    env.client.cookies.clear()
    assert env.client.get(f"/api/v1/competitions/{competition_id}").status_code == 200
    assert len(env.client.get("/api/v1/competitions").json()["items"]) == 1


def test_registration_lifecycle_and_duplicate():
    env = Env()
    discipline_id = env.seed_discipline()
    athlete_id = env.register_athlete("amina@example.com", "Амина Алиева")
    competition_id = env.create_published_competition(discipline_id)
    env.login_as(athlete_id, "athlete")

    registered = env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)
    assert registered.status_code == 201, registered.text
    registration_id = registered.json()["id"]

    duplicate = env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ALREADY_REGISTERED"

    card = env.client.get(f"/api/v1/competitions/{competition_id}")
    assert card.json()["viewerRegistrationId"] == registration_id
    assert card.json()["registrationOpen"] is True

    mine = env.client.get("/api/v1/me/registrations")
    assert mine.status_code == 200, mine.text
    assert mine.json()["total"] == 1
    assert mine.json()["items"][0]["id"] == registration_id
    assert mine.json()["items"][0]["athleteId"] == athlete_id

    # Организатор не подаёт заявку.
    env.login_organizer()
    denied = env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)
    assert denied.status_code == 403


def test_registration_closed_after_deadline():
    env = Env()
    discipline_id = env.seed_discipline()
    competition_id = env.seed_competition_raw(discipline_id, status="published")
    env.register_athlete("late@example.com", "Опоздавший Спортсмен")

    response = env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)
    assert response.status_code == 409
    assert response.json()["code"] == "REGISTRATION_CLOSED"

    card = env.client.get(f"/api/v1/competitions/{competition_id}")
    assert card.json()["registrationOpen"] is False


def test_athlete_cannot_call_organizer_endpoints():
    env = Env()
    discipline_id = env.seed_discipline()
    env.register_athlete("athlete@example.com", "Спортсмен Тест")
    env.login_organizer()
    body = {
        "title": "Турнир по алгоритмам",
        "disciplineId": discipline_id,
        "startsAt": future(48),
        "endsAt": future(51),
        "registrationDeadline": future(24),
        "format": "online",
        "description": "Описание турнира",
    }
    competition_id = env.client.post("/api/v1/competitions", json=body, headers=ORIGIN).json()["id"]
    env.client.cookies.clear()
    env.register_athlete("second@example.com", "Второй Спортсмен")

    assert env.client.post("/api/v1/competitions", json=body, headers=ORIGIN).status_code == 403
    assert env.client.patch(f"/api/v1/competitions/{competition_id}", json={"title": "Новое"}, headers=ORIGIN).status_code == 403
    assert env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN).status_code == 403
    assert env.client.get(f"/api/v1/competitions/{competition_id}/participants").status_code == 403
    assert env.client.get("/api/v1/competitions", params={"status": "draft"}).status_code == 403


def test_profile_get_and_patch():
    env = Env()
    discipline_id = env.seed_discipline()
    env.register_athlete("profile@example.com", "Амина Алиева")

    profile = env.client.get("/api/v1/me")
    assert profile.status_code == 200, profile.text
    assert profile.json()["fullName"] == "Амина Алиева"
    assert profile.json()["disciplineIds"] == []

    updated = env.client.patch(
        "/api/v1/me",
        json={
            "fullName": "Амина М. Алиева",
            "education": "Школа № 1",
            "locality": "Махачкала",
            "disciplineIds": [discipline_id],
        },
        headers=ORIGIN,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["education"] == "Школа № 1"
    assert updated.json()["disciplineIds"] == [discipline_id]

    cleared = env.client.patch("/api/v1/me", json={"education": None, "locality": None}, headers=ORIGIN)
    assert cleared.status_code == 200
    assert cleared.json()["education"] is None
    assert cleared.json()["locality"] is None

    unknown = env.client.patch("/api/v1/me", json={"disciplineIds": [str(uuid4())]}, headers=ORIGIN)
    assert unknown.status_code == 422
    duplicates = env.client.patch("/api/v1/me", json={"disciplineIds": [discipline_id, discipline_id]}, headers=ORIGIN)
    assert duplicates.status_code == 422
    empty = env.client.patch("/api/v1/me", json={}, headers=ORIGIN)
    assert empty.status_code == 422

    # Организатор не имеет профиля спортсмена.
    env.login_organizer()
    assert env.client.get("/api/v1/me").status_code == 403


def test_participants_list():
    env = Env()
    discipline_id = env.seed_discipline()
    competition_id = env.create_published_competition(discipline_id)

    env.register_athlete("amina@example.com", "Амина Алиева")
    env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)
    env.register_athlete("timur@example.com", "Тимур Гаджиев")
    env.client.post(f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN)

    env.login_organizer()
    participants = env.client.get(f"/api/v1/competitions/{competition_id}/participants")
    assert participants.status_code == 200, participants.text
    names = [item["fullName"] for item in participants.json()["items"]]
    assert names == ["Амина Алиева", "Тимур Гаджиев"]
    assert participants.json()["total"] == 2

    missing = env.client.get(f"/api/v1/competitions/{uuid4()}/participants")
    assert missing.status_code == 404


def test_publish_results_via_real_competition_port():
    """Интеграция Б2->Б1: реальный CompetitionPort завершает соревнование."""
    env = Env()
    discipline_id = env.seed_discipline()
    winner_id = env.register_athlete("winner@example.com", "Победитель Тест")
    competition_id = env.create_published_competition(discipline_id)
    env.login_as(winner_id, "athlete")
    registration_id = env.client.post(
        f"/api/v1/competitions/{competition_id}/registrations", headers=ORIGIN
    ).json()["id"]

    env.login_organizer()
    draft = env.client.put(
        f"/api/v1/competitions/{competition_id}/results/{registration_id}",
        json={"place": 1, "scoreText": "5 задач"},
        headers=ORIGIN,
    )
    assert draft.status_code == 200, draft.text

    publish = env.client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert publish.status_code == 200, publish.text
    assert publish.json()["status"] == "completed"
    assert publish.json()["publishedCount"] == 1

    card = env.client.get(f"/api/v1/competitions/{competition_id}")
    assert card.json()["status"] == "completed"
    assert card.json()["registrationOpen"] is False

    results = env.client.get(f"/api/v1/competitions/{competition_id}/results")
    assert results.status_code == 200
    assert results.json()["items"][0]["points"] == 100

    ratings = env.client.get("/api/v1/ratings").json()
    assert ratings["items"][0]["points"] == 100
    assert ratings["items"][0]["rank"] == 1

    again = env.client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_COMPLETED"


def test_draft_status_filter_visible_only_to_organizer():
    env = Env()
    discipline_id = env.seed_discipline()
    env.login_organizer()
    body = {
        "title": "Черновик турнира",
        "disciplineId": discipline_id,
        "startsAt": future(48),
        "endsAt": future(51),
        "registrationDeadline": future(24),
        "format": "offline",
        "description": "Ещё не опубликован",
    }
    env.client.post("/api/v1/competitions", json=body, headers=ORIGIN)
    env.client.cookies.clear()

    guest = env.client.get("/api/v1/competitions", params={"status": "draft"})
    assert guest.status_code == 403

    env.register_athlete("athlete@example.com", "Спортсмен Тест")
    athlete = env.client.get("/api/v1/competitions", params={"status": "draft"})
    assert athlete.status_code == 403