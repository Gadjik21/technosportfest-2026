"""Create results table.

Revision ID: 0002_results
Revises: 0001_auth
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_results"
down_revision = "0001_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("registration_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("competition_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("athlete_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("place", sa.Integer(), nullable=False),
        sa.Column("score_text", sa.String(length=500)),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_results_status"),
        sa.CheckConstraint("place >= 1", name="ck_results_place_positive"),
    )
    op.create_index("ix_results_registration_id", "results", ["registration_id"], unique=True)
    op.create_index("ix_results_competition_status", "results", ["competition_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_results_competition_status", table_name="results")
    op.drop_index("ix_results_registration_id", table_name="results")
    op.drop_table("results")
