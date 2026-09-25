"""Create news and documents tables.

Revision ID: 0003_content
Revises: 0002_results
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_content"
down_revision = "0002_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=20000), nullable=False),
        sa.Column("author_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_news_published_at", "news", ["published_at"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("file_url", sa.String(length=2048), nullable=False),
        sa.Column("author_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_published_at", "documents", ["published_at"])
    op.create_index("ix_documents_category", "documents", ["category"])


def downgrade() -> None:
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_index("ix_documents_published_at", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_news_published_at", table_name="news")
    op.drop_table("news")
