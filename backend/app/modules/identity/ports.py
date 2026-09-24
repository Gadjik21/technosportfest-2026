from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AthleteSummary:
    athlete_id: UUID
    full_name: str


class IdentityPort(Protocol):
    """Б1 реализует; Б2 запрашивает имена спортсменов пачкой."""

    def get_athlete_summaries(self, athlete_ids: list[UUID], db: Session) -> dict[UUID, AthleteSummary]: ...
