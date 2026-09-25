from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        Index("ix_results_registration_id", "registration_id", unique=True),
        Index("ix_results_competition_status", "competition_id", "status"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_results_status"),
        CheckConstraint("place >= 1", name="ck_results_place_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    registration_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    competition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    athlete_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    place: Mapped[int] = mapped_column(Integer, nullable=False)
    score_text: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def points(self) -> int:
        return {1: 100, 2: 70, 3: 50}.get(self.place, 20)
