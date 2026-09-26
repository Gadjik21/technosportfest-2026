"""Create tasks and submissions tables (кейс №2: модуль проведения соревнований).

Revision ID: 0005_contests
Revises: 0004_competitions
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_contests"
down_revision = "0004_competitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("competition_id", sa.Uuid(as_uuid=True), sa.ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.String(length=10000), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_score >= 1", name="ck_tasks_max_score_positive"),
    )
    op.create_index("ix_tasks_competition_order", "tasks", ["competition_id", "order_index"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("task_id", sa.Uuid(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registration_id", sa.Uuid(as_uuid=True), sa.ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("content", sa.String(length=10000), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_id", "registration_id", name="uq_submissions_task_registration"),
        sa.CheckConstraint("kind IN ('text', 'link')", name="ck_submissions_kind"),
        sa.CheckConstraint("score IS NULL OR score >= 0", name="ck_submissions_score_non_negative"),
    )
    op.create_index("ix_submissions_registration", "submissions", ["registration_id"])


def downgrade() -> None:
    op.drop_index("ix_submissions_registration", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_tasks_competition_order", table_name="tasks")
    op.drop_table("tasks")
