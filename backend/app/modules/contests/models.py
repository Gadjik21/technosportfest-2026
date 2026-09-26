from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_competition_order", "competition_id", "order_index"),
        CheckConstraint("max_score >= 1", name="ck_tasks_max_score_positive"),
        CheckConstraint("judging_mode IN ('manual', 'code')", name="ck_tasks_judging_mode"),
        CheckConstraint("time_limit_seconds BETWEEN 1 AND 60", name="ck_tasks_time_limit"),
        CheckConstraint("memory_limit_mb BETWEEN 32 AND 512", name="ck_tasks_memory_limit"),
        CheckConstraint("visible_test_count BETWEEN 0 AND 50", name="ck_tasks_visible_tests"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    competition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(String(10000), nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    judging_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=128)
    visible_test_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    test_cases: Mapped[list["TestCase"]] = relationship(cascade="all, delete-orphan", order_by="TestCase.order_index")


class TestCase(Base):
    __tablename__ = "task_test_cases"
    __table_args__ = (UniqueConstraint("task_id", "order_index", name="uq_task_test_case_order"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "registration_id", name="uq_submissions_task_registration"),
        Index("ix_submissions_registration", "registration_id"),
        CheckConstraint("kind IN ('text', 'link', 'code')", name="ck_submissions_kind"),
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
    language: Mapped[str | None] = mapped_column(String(20))
    verdict: Mapped[str | None] = mapped_column(String(30))
    failed_test_index: Mapped[int | None] = mapped_column(Integer)
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    judge_details: Mapped[list | None] = mapped_column(JSON)
    judge_message: Mapped[str | None] = mapped_column(String(4000))
    judge_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    judge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
