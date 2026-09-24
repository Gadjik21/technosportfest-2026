from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ParticipantSummary:
    registration_id: UUID
    athlete_id: UUID
    full_name: str


class CompetitionPort(Protocol):
    """Б1 реализует; Б2 вызывает, не импортируя ORM-модели Б1."""

    def lock_for_result_publication(self, competition_id: UUID, db: Session) -> None: ...

    def get_registration(self, competition_id: UUID, registration_id: UUID, db: Session) -> ParticipantSummary: ...

    def list_participants(self, competition_id: UUID, db: Session) -> list[ParticipantSummary]: ...

    def complete_competition(self, competition_id: UUID, db: Session) -> None: ...
