"""Seed-данные: справочник дисциплин, организатор и демоданные.

Публичного эндпоинта выдачи роли организатора нет — организатор создаётся
только этим CLI. Демоданные используют вымышленные персональные данные,
настоящие данные третьих лиц в репозиторий не попадают.

Примеры:
    python -m app.seed --email organizer@example.com   # организатор
    python -m app.seed --demo                          # демонстрационные данные
"""

import argparse
import getpass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_sessionmaker
from app.modules.competitions.models import Competition, Discipline, Registration
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
    password = getpass.getpass("Organizer password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    db.add(User(email=email.strip().lower(), password_hash=password_hash.hash(password), role="organizer"))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed disciplines, an organizer and demo data")
    parser.add_argument("--email", help="Organizer email (creates organizer)")
    parser.add_argument("--demo", action="store_true", help="Create demo athletes, competition and registrations")
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        seed_disciplines(db)
        if args.email:
            seed_organizer(db, args.email)
        if args.demo:
            seed_demo(db)
        if not args.email and not args.demo:
            parser.print_help()


if __name__ == "__main__":
    main()
