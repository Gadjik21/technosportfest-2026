from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ParticipantSummary:
    registration_id: UUID
    athlete_id: UUID
    full_name: str


@dataclass(frozen=True)
class CompetitionTiming:
    status: str
    starts_at: datetime
    ends_at: datetime


class CompetitionPort(Protocol):
    """Б1 реализует; Б2 вызывает, не импортируя ORM-модели Б1.

    Соглашение об ошибках (Б2 полагается на него в сервисах results/rating):
    несуществующее соревнование или заявка, либо заявка из другого
    соревнования — ``ApiError(404, "NOT_FOUND", ...)``; соревнование не в
    статусе ``published`` на момент ``lock_for_result_publication`` —
    ``ApiError(409, "INVALID_STATE", ...)``.
    """

    def lock_for_result_publication(self, competition_id: UUID, db: Session) -> None: ...

    def get_registration(self, competition_id: UUID, registration_id: UUID, db: Session) -> ParticipantSummary: ...

    def list_participants(self, competition_id: UUID, db: Session) -> list[ParticipantSummary]: ...

    def complete_competition(self, competition_id: UUID, db: Session) -> None: ...

    def get_competition_disciplines(self, competition_ids: list[UUID], db: Session) -> dict[UUID, UUID]:
        """competitionId -> disciplineId для переданных соревнований.

        Добавлено Б2 для фильтра `/ratings?disciplineId=`: без дисциплины
        соревнования Results не может отфильтровать рейтинг, а Results не
        хранит эту связь у себя. TODO(Б1): реализовать одним запросом без N+1.
        """
        ...

    def get_competition_status(self, competition_id: UUID, db: Session) -> str | None:
        """Статус соревнования (draft/published/completed) или None, если не найдено.

        Добавлено Б2 для `GET /competitions/{id}/results`: публичный список
        результатов должен отдавать 404 для черновика соревнования, а Results
        не хранит статус соревнования у себя. TODO(Б1): реализовать.
        """
        ...

    def get_registration_by_athlete(self, competition_id: UUID, athlete_id: UUID, db: Session) -> ParticipantSummary | None:
        """Заявка спортсмена на конкретное соревнование, если она есть, иначе None.

        Добавлено для модуля Contests (кейс №2): спортсмен отправляет решение
        по `competitionId` из URL и своему `principal.user_id`, а не по
        `registrationId` — в отличие от организаторских маршрутов Results.
        """
        ...

    def get_competition_timing(self, competition_id: UUID, db: Session) -> CompetitionTiming | None:
        """Статус и временное окно соревнования, или None, если не найдено.

        Добавлено для модуля Contests: приём решений разрешён только пока
        `published` и `starts_at <= now < ends_at`; отдельного статуса
        «идёт» в БД нет — вычисляется на лету, чтобы не трогать общий
        контракт `competitions.status`.
        """
        ...
