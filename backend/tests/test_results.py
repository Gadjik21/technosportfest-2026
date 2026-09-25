"""Тесты Б2: черновики, атомарная публикация, рейтинг.

CompetitionPort реализован фейком в памяти (Б1 ещё не подключил настоящий
адаптер) — см. docs/architecture.md, «Параллельный старт». Публикацию и
блокировки строк в проде проверяют на PostgreSQL: SQLite не проверяет
блокировки так же, как PostgreSQL (см. docs/work-items.md).
"""

import os
from dataclasses import dataclass
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.errors import ApiError
from app.main import create_app
from app.modules.competitions.ports import CompetitionPort, ParticipantSummary
from app.modules.content import models as content_models  # noqa: F401: registers metadata
from app.modules.identity.adapter import identity_port
from app.modules.identity.models import AthleteProfile, User  # noqa: F401: registers metadata
from app.modules.results import models as results_models  # noqa: F401: registers metadata
from app.modules.results.deps import get_competition_port, get_identity_port

ORIGIN = {"Origin": "http://localhost:5173"}


@dataclass
class _FakeCompetition:
    status: str
    discipline_id: UUID | None = None


@dataclass
class _FakeRegistration:
    competition_id: UUID
    athlete_id: UUID


class FakeCompetitionPort(CompetitionPort):
    def __init__(self) -> None:
        self.competitions: dict[UUID, _FakeCompetition] = {}
        self.registrations: dict[UUID, _FakeRegistration] = {}

    def add_competition(self, competition_id: UUID, status: str = "published", discipline_id: UUID | None = None) -> None:
        self.competitions[competition_id] = _FakeCompetition(status=status, discipline_id=discipline_id)

    def add_registration(self, registration_id: UUID, competition_id: UUID, athlete_id: UUID) -> None:
        self.registrations[registration_id] = _FakeRegistration(competition_id=competition_id, athlete_id=athlete_id)

    def lock_for_result_publication(self, competition_id: UUID, db) -> None:
        competition = self.competitions.get(competition_id)
        if competition is None:
            raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
        if competition.status != "published":
            raise ApiError(409, "INVALID_STATE", "Соревнование не в статусе published.")

    def get_registration(self, competition_id: UUID, registration_id: UUID, db) -> ParticipantSummary:
        registration = self.registrations.get(registration_id)
        if registration is None or registration.competition_id != competition_id:
            raise ApiError(404, "NOT_FOUND", "Заявка не найдена.")
        return ParticipantSummary(registration_id=registration_id, athlete_id=registration.athlete_id, full_name="")

    def list_participants(self, competition_id: UUID, db) -> list[ParticipantSummary]:
        return [
            ParticipantSummary(registration_id=rid, athlete_id=reg.athlete_id, full_name="")
            for rid, reg in self.registrations.items()
            if reg.competition_id == competition_id
        ]

    def complete_competition(self, competition_id: UUID, db) -> None:
        self.competitions[competition_id].status = "completed"

    def get_competition_disciplines(self, competition_ids: list[UUID], db) -> dict[UUID, UUID]:
        return {cid: self.competitions[cid].discipline_id for cid in competition_ids if cid in self.competitions and self.competitions[cid].discipline_id}

    def get_competition_status(self, competition_id: UUID, db) -> str | None:
        competition = self.competitions.get(competition_id)
        return competition.status if competition else None


def client_with_fake_port():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    fake_port = FakeCompetitionPort()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_competition_port] = lambda: fake_port
    app.dependency_overrides[get_identity_port] = lambda: identity_port
    return TestClient(app), fake_port


def _register_athlete(client: TestClient, email: str, full_name: str) -> UUID:
    body = {"email": email, "password": "long-demo-password", "fullName": full_name}
    response = client.post("/api/v1/auth/register", json=body, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


def _login_as_organizer(client: TestClient) -> None:
    from app.modules.identity.security import COOKIE_NAME, create_token

    client.cookies.set(COOKIE_NAME, create_token(uuid4(), "organizer"), path="/api/v1")


def test_draft_is_private_and_excluded_from_rating():
    client, fake_port = client_with_fake_port()
    competition_id, registration_id = uuid4(), uuid4()
    athlete_id = _register_athlete(client, "amina@example.com", "Амина Алиева")
    fake_port.add_competition(competition_id, status="published")
    fake_port.add_registration(registration_id, competition_id, athlete_id)
    client.cookies.clear()
    _login_as_organizer(client)

    put = client.put(f"/api/v1/competitions/{competition_id}/results/{registration_id}", json={"place": 1, "scoreText": "4 задачи"}, headers=ORIGIN)
    assert put.status_code == 200, put.text
    assert put.json()["status"] == "draft"

    public_results = client.get(f"/api/v1/competitions/{competition_id}/results")
    assert public_results.status_code == 200
    assert public_results.json()["items"] == []

    ratings = client.get("/api/v1/ratings")
    assert ratings.json()["items"] == []

    drafts = client.get(f"/api/v1/competitions/{competition_id}/results/drafts")
    assert drafts.status_code == 200
    assert len(drafts.json()["items"]) == 1


def test_athlete_cannot_write_drafts_or_publish():
    client, fake_port = client_with_fake_port()
    competition_id, registration_id = uuid4(), uuid4()
    athlete_id = _register_athlete(client, "athlete@example.com", "Спортсмен")
    fake_port.add_competition(competition_id, status="published")
    fake_port.add_registration(registration_id, competition_id, athlete_id)

    put = client.put(f"/api/v1/competitions/{competition_id}/results/{registration_id}", json={"place": 1}, headers=ORIGIN)
    assert put.status_code == 403

    publish = client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert publish.status_code == 403


def test_publish_is_atomic_and_idempotent_and_updates_rating():
    client, fake_port = client_with_fake_port()
    competition_id = uuid4()
    reg1, reg2, reg3 = uuid4(), uuid4(), uuid4()
    athlete1 = _register_athlete(client, "first@example.com", "Первый Спортсмен")
    athlete2 = _register_athlete(client, "second@example.com", "Второй Спортсмен")
    athlete3 = _register_athlete(client, "third@example.com", "Третий Спортсмен")
    fake_port.add_competition(competition_id, status="published")
    fake_port.add_registration(reg1, competition_id, athlete1)
    fake_port.add_registration(reg2, competition_id, athlete2)
    fake_port.add_registration(reg3, competition_id, athlete3)
    client.cookies.clear()
    _login_as_organizer(client)

    for reg, place in [(reg1, 1), (reg2, 2), (reg3, 2)]:
        put = client.put(f"/api/v1/competitions/{competition_id}/results/{reg}", json={"place": place}, headers=ORIGIN)
        assert put.status_code == 200, put.text

    publish = client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert publish.status_code == 200, publish.text
    body = publish.json()
    assert body["status"] == "completed"
    assert body["publishedCount"] == 3
    assert fake_port.competitions[competition_id].status == "completed"

    again = client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_COMPLETED"

    results = client.get(f"/api/v1/competitions/{competition_id}/results")
    assert results.status_code == 200
    places = {item["athleteId"]: item["points"] for item in results.json()["items"]}
    assert places[str(athlete1)] == 100
    assert places[str(athlete2)] == 70
    assert places[str(athlete3)] == 70

    ratings = client.get("/api/v1/ratings").json()
    ranks = {row["athleteId"]: row["rank"] for row in ratings["items"]}
    assert ranks[str(athlete1)] == 1
    assert ranks[str(athlete2)] == 2
    assert ranks[str(athlete3)] == 2


def test_publish_without_drafts_returns_no_results():
    client, fake_port = client_with_fake_port()
    competition_id = uuid4()
    fake_port.add_competition(competition_id, status="published")
    _login_as_organizer(client)

    response = client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)
    assert response.status_code == 409
    assert response.json()["code"] == "NO_RESULTS"


def test_draft_rejected_after_competition_completed():
    client, fake_port = client_with_fake_port()
    competition_id, registration_id = uuid4(), uuid4()
    athlete_id = _register_athlete(client, "late@example.com", "Опоздавший")
    fake_port.add_competition(competition_id, status="published")
    fake_port.add_registration(registration_id, competition_id, athlete_id)
    client.cookies.clear()
    _login_as_organizer(client)

    client.put(f"/api/v1/competitions/{competition_id}/results/{registration_id}", json={"place": 1}, headers=ORIGIN)
    client.post(f"/api/v1/competitions/{competition_id}/results/publish", headers=ORIGIN)

    late_registration = uuid4()
    late_athlete = uuid4()
    fake_port.add_registration(late_registration, competition_id, late_athlete)
    retry = client.put(f"/api/v1/competitions/{competition_id}/results/{late_registration}", json={"place": 4}, headers=ORIGIN)
    assert retry.status_code == 409
    assert retry.json()["code"] == "INVALID_STATE"
