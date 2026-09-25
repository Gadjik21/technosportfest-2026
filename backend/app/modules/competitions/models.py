from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Discipline(Base):
    __tablename__ = "disciplines"
    __table_args__ = (Index("ix_disciplines_name", "name", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class AthleteDiscipline(Base):
    """Связь спортсмена с выбранными дисциплинами (набор в профиле)."""

    __tablename__ = "athlete_disciplines"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    discipline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("disciplines.id", ondelete="CASCADE"), primary_key=True)


class Competition(Base):
    __tablename__ = "competitions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'completed')", name="ck_competitions_status"),
        CheckConstraint("format IN ('online', 'offline')", name="ck_competitions_format"),
        Index("ix_competitions_status", "status"),
        Index("ix_competitions_starts_id", "starts_at", "id"),
        Index("ix_competitions_discipline", "discipline_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    discipline_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("disciplines.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(10000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("competition_id", "athlete_id", name="uq_registrations_competition_athlete"),
        Index("ix_registrations_athlete", "athlete_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    competition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )