"""Реализация IdentityPort поверх таблиц Identity.

Протокол помечен как "Б1 реализует", но данные читаются только из уже
существующих users/athlete_profiles, поэтому Б2 подготовил рабочую реализацию,
чтобы Results/Rating можно было проверить сквозным сценарием. Б1 может
заменить или расширить этот файл без изменения сигнатуры порта.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import AthleteProfile
from app.modules.identity.ports import AthleteSummary


class SqlIdentityPort:
    def get_athlete_summaries(self, athlete_ids: list[UUID], db: Session) -> dict[UUID, AthleteSummary]:
        if not athlete_ids:
            return {}
        rows = db.execute(
            select(AthleteProfile.user_id, AthleteProfile.full_name).where(AthleteProfile.user_id.in_(set(athlete_ids)))
        ).all()
        return {row.user_id: AthleteSummary(athlete_id=row.user_id, full_name=row.full_name) for row in rows}


identity_port = SqlIdentityPort()
