"""Create disciplines, athlete_disciplines, competitions and registrations.

Revision ID: 0004_competitions
Revises: 0003_content
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_competitions"
down_revision = "0003_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "disciplines",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_index("ix_disciplines_name", "disciplines", ["name"], unique=True)

    op.create_table(
        "athlete_disciplines",
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("discipline_id", sa.Uuid(as_uuid=True), sa.ForeignKey("disciplines.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "competitions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("discipline_id", sa.Uuid(as_uuid=True), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=10000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'completed')", name="ck_competitions_status"),
        sa.CheckConstraint("format IN ('online', 'offline')", name="ck_competitions_format"),
    )
    op.create_index("ix_competitions_status", "competitions", ["status"])
    op.create_index("ix_competitions_starts_id", "competitions", ["starts_at", "id"])
    op.create_index("ix_competitions_discipline", "competitions", ["discipline_id"])

    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("competition_id", sa.Uuid(as_uuid=True), sa.ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("competition_id", "athlete_id", name="uq_registrations_competition_athlete"),
    )
    op.create_index("ix_registrations_athlete", "registrations", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_registrations_athlete", table_name="registrations")
    op.drop_table("registrations")
    op.drop_index("ix_competitions_discipline", table_name="competitions")
    op.drop_index("ix_competitions_starts_id", table_name="competitions")
    op.drop_index("ix_competitions_status", table_name="competitions")
    op.drop_table("competitions")
    op.drop_table("athlete_disciplines")
    op.drop_index("ix_disciplines_name", table_name="disciplines")
    op.drop_table("disciplines")