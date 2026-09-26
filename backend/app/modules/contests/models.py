from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_competition_order", "competition_id", "order_index"),
        CheckConstraint("max_score >= 1", name="ck_tasks_max_score_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    competition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(String(10000), nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "registration_id", name="uq_submissions_task_registration"),
        Index("ix_submissions_registration", "registration_id"),
        CheckConstraint("kind IN ('text', 'link')", name="ck_submissions_kind"),
        CheckConstraint("score IS NULL OR score >= 0", name="ck_submissions_score_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    registration_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(String(10000), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
