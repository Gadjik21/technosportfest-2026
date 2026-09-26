"""Seed-данные: справочник дисциплин, организатор и демоданные.

Публичного эндпоинта выдачи роли организатора нет — организатор создаётся
только этим CLI. Демоданные используют вымышленные персональные данные,
настоящие данные третьих лиц в репозиторий не попадают.

Примеры:
    python -m app.seed --email organizer@example.com   # организатор
    python -m app.seed --demo                          # демонстрационные данные
    python -m app.seed --contest-demo                  # демо-контест кейса №2
"""

import argparse
import getpass
from datetime import datetime, timedelta, timezone

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_sessionmaker
from app.modules.competitions.models import Competition, Discipline, Registration
from app.modules.contests.models import Submission, Task
from app.modules.identity.models import AthleteProfile, User
from app.modules.identity.security import password_hash

DISCIPLINES = [
    "Алгоритмическое программирование",
    "Продуктовое программирование",
    "Робототехническое программирование",
]

DEMO_PASSWORD = "demo-password-123"
DEMO_ATHLETES = [
    {"email": "amina.aliyeva@example.com", "full_name": "Амина Алиева", "education": "Школа № 1", "locality": "Махачкала"},
    {"email": "timur.gadzhiev@example.com", "full_name": "Тимур Гаджиев", "education": "Лицей № 2", "locality": "Дербент"},
    {"email": "saida.ramazanova@example.com", "full_name": "Саида Рамазанова", "education": "Гимназия № 5", "locality": "Каспийск"},
]


def seed_disciplines(db) -> None:
    existing = {name for (name,) in db.execute(select(Discipline.name)).all()}
    for name in DISCIPLINES:
        if name not in existing:
            db.add(Discipline(name=name))
    db.commit()


def seed_organizer(db, email: str) -> None:
    try:
        normalized_email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    except ValidationError:
        raise SystemExit("A valid organizer email is required")
    password = getpass.getpass("Organizer password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    db.add(User(email=normalized_email, password_hash=password_hash.hash(password), role="organizer"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SystemExit("Email is already registered")
    print("Organizer created")


def seed_demo(db) -> None:
    athletes: list[tuple[User, Discipline]] = []
    for row in DEMO_ATHLETES:
        user = db.scalar(select(User).where(User.email == row["email"]))
        if user is None:
            user = User(email=row["email"], password_hash=password_hash.hash(DEMO_PASSWORD), role="athlete")
            db.add(user)
            db.flush()
            db.add(AthleteProfile(user_id=user.id, full_name=row["full_name"], education=row["education"], locality=row["locality"]))
        else:
            profile = db.get(AthleteProfile, user.id)
            if profile is not None:
                profile.full_name = row["full_name"]
                profile.education = row["education"]
                profile.locality = row["locality"]
        athletes.append((user, row))
    db.commit()

    now = datetime.now(timezone.utc)
    published = db.scalar(
        select(Competition).where(Competition.title == "Тестовый турнир по алгоритмам")
    )
    if published is None:
        algorithms = db.scalar(select(Discipline).where(Discipline.name == "Алгоритмическое программирование"))
        published = Competition(
            title="Тестовый турнир по алгоритмам",
            discipline_id=algorithms.id,
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2, hours=3),
            registration_deadline=now + timedelta(days=1),
            format="online",
            description="Демонстрационное соревнование для сквозного сценария.",
            status="published",
        )
        db.add(published)
        db.flush()

    for user, _ in athletes:
        existing = db.scalar(
            select(Registration).where(
                Registration.competition_id == published.id, Registration.athlete_id == user.id
            )
        )
        if existing is None:
            db.add(Registration(competition_id=published.id, athlete_id=user.id))
    db.commit()
    print(f"Demo data ready: {len(athletes)} athletes, 1 published competition")


CONTEST_TASKS = [
    {"title": "Сумма двух чисел", "statement": "Считайте два целых числа и выведите их сумму.", "max_score": 100},
    {"title": "Поиск максимума в массиве", "statement": "Дан массив целых чисел, выведите наибольшее значение.", "max_score": 100},
    {"title": "Быстрая сортировка", "statement": "Реализуйте сортировку массива и выведите отсортированный результат.", "max_score": 100},
]


def seed_contest_demo(db) -> None:
    """Демо-контест кейса №2: 3 задания, несколько участников, часть решений уже проверена.

    Одно решение намеренно оставлено без оценки — на защите можно вживую
    показать очередь проверки и завершение контеста, а не только готовый результат.
    """
    seed_demo(db)
    algorithms = db.scalar(select(Discipline).where(Discipline.name == "Алгоритмическое программирование"))
    now = datetime.now(timezone.utc)
    contest = db.scalar(select(Competition).where(Competition.title == "Тестовый контест по алгоритмическому программированию"))
    if contest is None:
        contest = Competition(
            title="Тестовый контест по алгоритмическому программированию",
            discipline_id=algorithms.id,
            starts_at=now - timedelta(minutes=30),
            ends_at=now + timedelta(hours=2),
            registration_deadline=now - timedelta(hours=1),
            format="online",
            description="Демонстрационный контест кейса №2: задания решаются прямо на платформе.",
            status="published",
        )
        db.add(contest)
        db.flush()

    tasks = list(db.scalars(select(Task).where(Task.competition_id == contest.id).order_by(Task.order_index)).all())
    if not tasks:
        for index, item in enumerate(CONTEST_TASKS):
            task = Task(competition_id=contest.id, title=item["title"], statement=item["statement"], max_score=item["max_score"], order_index=index)
            db.add(task)
        db.flush()
        tasks = list(db.scalars(select(Task).where(Task.competition_id == contest.id).order_by(Task.order_index)).all())

    athlete_ids = [db.scalar(select(User.id).where(User.email == row["email"])) for row in DEMO_ATHLETES]
    registrations: dict = {}
    for athlete_id in athlete_ids:
        registration = db.scalar(select(Registration).where(Registration.competition_id == contest.id, Registration.athlete_id == athlete_id))
        if registration is None:
            registration = Registration(competition_id=contest.id, athlete_id=athlete_id)
            db.add(registration)
            db.flush()
        registrations[athlete_id] = registration.id
    db.commit()

    # Спортсмен 1: обе задачи сданы и уже проверены.
    # Спортсмен 2: одна задача проверена, вторая ждёт проверки организатора.
    # Спортсмен 3: без решений — показывает, что итоговая таблица корректно учитывает 0 баллов.
    plan = [
        (registrations[athlete_ids[0]], tasks[0].id, "text", "print(a + b)", 90),
        (registrations[athlete_ids[0]], tasks[1].id, "text", "print(max(items))", 85),
        (registrations[athlete_ids[1]], tasks[0].id, "link", "https://example.com/solution-2", 60),
        (registrations[athlete_ids[1]], tasks[2].id, "text", "print(sorted(items))", None),
    ]
    for registration_id, task_id, kind, content, score in plan:
        submission = db.scalar(select(Submission).where(Submission.task_id == task_id, Submission.registration_id == registration_id))
        if submission is None:
            db.add(
                Submission(
                    task_id=task_id,
                    registration_id=registration_id,
                    kind=kind,
                    content=content,
                    submitted_at=now,
                    score=score,
                    graded_at=now if score is not None else None,
                )
            )
    db.commit()
    print("Contest demo ready: 1 published contest, 3 tasks, 4 submissions (1 awaiting review)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed disciplines, an organizer and demo data")
    parser.add_argument("--email", help="Organizer email (creates organizer)")
    parser.add_argument("--demo", action="store_true", help="Create demo athletes, competition and registrations")
    parser.add_argument("--contest-demo", action="store_true", help="Create demo contest with tasks and submissions (кейс №2)")
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        seed_disciplines(db)
        if args.email:
            seed_organizer(db, args.email)
        if args.demo:
            seed_demo(db)
        if args.contest_demo:
            seed_contest_demo(db)
        if not args.email and not args.demo and not args.contest_demo:
            parser.print_help()


if __name__ == "__main__":
    main()
