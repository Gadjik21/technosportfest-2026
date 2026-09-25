"""Реализация CompetitionPort для Results/B2.

Методы работают на переданной SQLAlchemy Session — Б2 публикует результаты
и завершает соревнование в одной транзакции. Соглашение об ошибках описано
в `app/modules/competitions/ports.py`.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.modules.competitions.models import Competition, Registration
from app.modules.competitions.ports import ParticipantSummary
from app.modules.identity.models import AthleteProfile


class SqlCompetitionPort:
    def lock_for_result_publication(self, competition_id: UUID, db: Session) -> None:
        competition = db.execute(
            select(Competition).where(Competition.id == competition_id).with_for_update()
        ).scalar_one_or_none()
        if competition is None:
            raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
        if competition.status != "published":
            raise ApiError(409, "INVALID_STATE", "Соревнование не в статусе published.")

    def get_registration(self, competition_id: UUID, registration_id: UUID, db: Session) -> ParticipantSummary:
        registration = db.get(Registration, registration_id)
        if registration is None or registration.competition_id != competition_id:
            raise ApiError(404, "NOT_FOUND", "Заявка не найдена.")
        full_name = (
            db.scalar(select(AthleteProfile.full_name).where(AthleteProfile.user_id == registration.athlete_id)) or ""
        )
        return ParticipantSummary(
            registration_id=registration.id, athlete_id=registration.athlete_id, full_name=full_name
        )

    def list_participants(self, competition_id: UUID, db: Session) -> list[ParticipantSummary]:
        rows = db.execute(
            select(Registration, AthleteProfile)
            .join(AthleteProfile, AthleteProfile.user_id == Registration.athlete_id)
            .where(Registration.competition_id == competition_id)
            .order_by(AthleteProfile.full_name, Registration.id)
        ).all()
        return [
            ParticipantSummary(registration_id=registration.id, athlete_id=registration.athlete_id, full_name=profile.full_name)
            for registration, profile in rows
        ]

    def complete_competition(self, competition_id: UUID, db: Session) -> None:
        competition = db.get(Competition, competition_id)
        if competition is None:
            raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
        if competition.status != "published":
            raise ApiError(409, "INVALID_STATE", "Соревнование не в статусе published.")
        competition.status = "completed"

    def get_competition_disciplines(self, competition_ids: list[UUID], db: Session) -> dict[UUID, UUID]:
        if not competition_ids:
            return {}
        rows = db.execute(
            select(Competition.id, Competition.discipline_id).where(Competition.id.in_(set(competition_ids)))
        ).all()
        return {row.id: row.discipline_id for row in rows}

    def get_competition_status(self, competition_id: UUID, db: Session) -> str | None:
        return db.scalar(select(Competition.status).where(Competition.id == competition_id))


competition_port = SqlCompetitionPort()