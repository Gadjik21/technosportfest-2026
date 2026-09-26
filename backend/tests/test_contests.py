"""Кейс №2: задания, отправка решения, проверка, завершение контеста.

Проверяет ровно тот сквозной сценарий, который команда должна показать на
защите (см. docs/case2-contest-module.md):
организатор создаёт задания -> публикует -> спортсмен отправляет решение ->
организатор проверяет -> завершает контест -> результат и баллы видны в
`results`/`my results` без единой новой строчки логики подсчёта очков —
финал контеста публикуется через существующий `results.service`.
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
from app.modules.competitions.models import Competition, Discipline, Registration
from app.modules.contests import models as contests_models  # noqa: F401: registers metadata
from app.modules.content import models as content_models  # noqa: F401: registers metadata
from app.modules.identity.models import AthleteProfile, User
from app.modules.identity.permissions import ALL_PERMISSIONS
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

    def login_organizer(self) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, create_token(uuid4(), "organizer", ALL_PERMISSIONS), path="/api/v1")

    def login_as(self, user_id: str, role: str) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, create_token(UUID(user_id), role), path="/api/v1")

    def seed_draft_competition_with_registration(self, athlete_email: str, athlete_name: str) -> tuple[str, str]:
        """Черновик соревнования (даты валидны для публикации) с готовой заявкой спортсмена.

        Регистрацию создаём напрямую в БД, а не через `/registrations`, чтобы
        не зависеть от порядка публикации — тест сфокусирован на модуле
        Contests, а не на регистрации (её проверяет test_competitions.py).
        """
        now = datetime.now(timezone.utc)
        with self.sessions() as db:
            discipline = Discipline(name="Алгоритмическое программирование")
            db.add(discipline)
            db.flush()
            competition = Competition(
                title="Тестовый контест",
                discipline_id=discipline.id,
                starts_at=now + timedelta(hours=1),
                ends_at=now + timedelta(hours=4),
                registration_deadline=now + timedelta(minutes=30),
                format="online",
                description="Контест кейса №2",
                status="draft",
            )
            db.add(competition)
            db.flush()
            ensure_system_roles(db)
            athlete_role = get_role_by_name(db, "athlete")
            assert athlete_role is not None
            user = User(email=athlete_email, password_hash=password_hash.hash("long-demo-password"), role_id=athlete_role.id)
            db.add(user)
            db.flush()
            db.add(AthleteProfile(user_id=user.id, full_name=athlete_name))
            registration = Registration(competition_id=competition.id, athlete_id=user.id)
            db.add(registration)
            db.commit()
            return str(competition.id), str(user.id)

    def fast_forward_to_ongoing(self, competition_id: str) -> None:
        """Двигает старт соревнования в прошлое, имитируя, что контест уже идёт.

        В реальном сценарии между публикацией и стартом проходит время само
        по себе; в тесте вместо ожидания сдвигаем `starts_at`, не трогая
        остальную бизнес-логику (даты после публикации API не редактирует —
        это прямая правка строки, только для теста).
        """
        now = datetime.now(timezone.utc)
        with self.sessions() as db:
            competition = db.get(Competition, UUID(competition_id))
            competition.starts_at = now - timedelta(hours=1)
            db.commit()


def test_contest_full_scenario_publishes_result_and_rating():
    env = Env()
    competition_id, athlete_id = env.seed_draft_competition_with_registration("athlete@example.com", "Спортсмен Тестов")

    # Спортсмен не создаёт задания.
    env.login_as(athlete_id, "athlete")
    forbidden = env.client.post(
        f"/api/v1/competitions/{competition_id}/tasks",
        json={"title": "Задача 1", "statement": "Условие", "maxScore": 100},
        headers=ORIGIN,
    )
    assert forbidden.status_code == 403

    # Организатор добавляет два задания, пока соревнование в черновике.
    env.login_organizer()
    task1 = env.client.post(
        f"/api/v1/competitions/{competition_id}/tasks",
        json={"title": "Задача 1", "statement": "Условие 1", "maxScore": 100},
        headers=ORIGIN,
    )
    assert task1.status_code == 201, task1.text
    task1_id = task1.json()["id"]
    task2 = env.client.post(
        f"/api/v1/competitions/{competition_id}/tasks",
        json={"title": "Задача 2", "statement": "Условие 2", "maxScore": 50},
        headers=ORIGIN,
    )
    assert task2.status_code == 201, task2.text

    # Гость/спортсмен не видит задания черновика.
    env.login_as(athlete_id, "athlete")
    hidden = env.client.get(f"/api/v1/competitions/{competition_id}/tasks")
    assert hidden.status_code == 404

    # Организатор публикует соревнование.
    env.login_organizer()
    published = env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN)
    assert published.status_code == 200, published.text
    env.fast_forward_to_ongoing(competition_id)

    # Теперь задания видны спортсмену.
    env.login_as(athlete_id, "athlete")
    visible = env.client.get(f"/api/v1/competitions/{competition_id}/tasks")
    assert visible.status_code == 200
    assert [t["title"] for t in visible.json()] == ["Задача 1", "Задача 2"]

    # Спортсмен отправляет решение только по первой задаче.
    submitted = env.client.put(
        f"/api/v1/competitions/{competition_id}/tasks/{task1_id}/submission",
        json={"kind": "text", "content": "def solve(): return 42"},
        headers=ORIGIN,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["score"] is None

    my_submissions = env.client.get(f"/api/v1/competitions/{competition_id}/my-submissions", headers=ORIGIN)
    assert my_submissions.status_code == 200
    assert len(my_submissions.json()) == 1

    # Организатор видит решение в очереди и проверяет его.
    env.login_organizer()
    queue = env.client.get(f"/api/v1/competitions/{competition_id}/submissions", headers=ORIGIN)
    assert queue.status_code == 200, queue.text
    assert len(queue.json()) == 1
    submission_id = queue.json()[0]["id"]
    assert queue.json()[0]["athleteFullName"] == "Спортсмен Тестов"

    # Балл выше максимума задания отклоняется.
    invalid_score = env.client.patch(
        f"/api/v1/competitions/{competition_id}/submissions/{submission_id}", json={"score": 999}, headers=ORIGIN
    )
    assert invalid_score.status_code == 422

    graded = env.client.patch(
        f"/api/v1/competitions/{competition_id}/submissions/{submission_id}", json={"score": 80}, headers=ORIGIN
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()["score"] == 80

    # Организатор завершает контест: считает баллы и публикует результат существующим механизмом Results.
    finished = env.client.post(f"/api/v1/competitions/{competition_id}/finish-contest", headers=ORIGIN)
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["publishedCount"] == 1

    # Повторное завершение уже невозможно (соревнование не в published).
    repeat = env.client.post(f"/api/v1/competitions/{competition_id}/finish-contest", headers=ORIGIN)
    assert repeat.status_code == 409

    # Результат виден публично на странице соревнования...
    public_results = env.client.get(f"/api/v1/competitions/{competition_id}/results")
    assert public_results.status_code == 200
    assert public_results.json()["items"][0]["place"] == 1
    assert public_results.json()["items"][0]["points"] == 100  # 1 место -> 100 баллов по формуле рейтинга
    assert public_results.json()["items"][0]["scoreText"] == "80/150 баллов по заданиям"  # 100 (Задача 1) + 50 (Задача 2)

    # Таблица результатов по заданиям (как в Codeforces) видна публично после завершения.
    standings = env.client.get(f"/api/v1/competitions/{competition_id}/standings")
    assert standings.status_code == 200, standings.text
    assert standings.json()["maxTotalScore"] == 150
    assert [t["title"] for t in standings.json()["tasks"]] == ["Задача 1", "Задача 2"]
    row = standings.json()["items"][0]
    assert row["fullName"] == "Спортсмен Тестов"
    assert row["place"] == 1
    assert row["totalScore"] == 80
    assert row["taskScores"] == [80, None]  # вторую задачу не отправляли

    # ...и в профиле спортсмена, и в общем рейтинге — бесплатно, без правок Results/Rating.
    env.login_as(athlete_id, "athlete")
    my_results = env.client.get("/api/v1/me/results", headers=ORIGIN)
    assert my_results.status_code == 200
    assert my_results.json()["items"][0]["points"] == 100

    rating = env.client.get("/api/v1/ratings")
    assert rating.status_code == 200
    assert rating.json()["items"][0]["fullName"] == "Спортсмен Тестов"
    assert rating.json()["items"][0]["points"] == 100


def test_finish_contest_blocks_on_ungraded_submission():
    env = Env()
    competition_id, athlete_id = env.seed_draft_competition_with_registration("second@example.com", "Второй Спортсмен")
    env.login_organizer()
    task = env.client.post(
        f"/api/v1/competitions/{competition_id}/tasks",
        json={"title": "Задача", "statement": "Условие", "maxScore": 100},
        headers=ORIGIN,
    )
    task_id = task.json()["id"]
    env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN)
    env.fast_forward_to_ongoing(competition_id)

    env.login_as(athlete_id, "athlete")
    env.client.put(
        f"/api/v1/competitions/{competition_id}/tasks/{task_id}/submission",
        json={"kind": "link", "content": "https://example.com/solution"},
        headers=ORIGIN,
    )

    env.login_organizer()
    blocked = env.client.post(f"/api/v1/competitions/{competition_id}/finish-contest", headers=ORIGIN)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "UNGRADED_SUBMISSIONS"


def test_tasks_locked_after_publish():
    env = Env()
    competition_id, _ = env.seed_draft_competition_with_registration("third@example.com", "Третий Спортсмен")
    env.login_organizer()
    env.client.post(f"/api/v1/competitions/{competition_id}/publish", headers=ORIGIN)
    blocked = env.client.post(
        f"/api/v1/competitions/{competition_id}/tasks",
        json={"title": "Поздняя задача", "statement": "Условие", "maxScore": 10},
        headers=ORIGIN,
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "INVALID_STATE"
