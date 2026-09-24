"""Create users and athlete profiles.

Revision ID: 0001_auth
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('athlete', 'organizer')", name="ck_users_role"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "athlete_profiles",
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("education", sa.String(length=200)),
        sa.Column("locality", sa.String(length=150)),
    )


def downgrade() -> None:
    op.drop_table("athlete_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
