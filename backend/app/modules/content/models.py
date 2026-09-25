from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (Index("ix_news_published_at", "published_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(20000), nullable=False)
    author_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_published_at", "published_at"), Index("ix_documents_category", "category"))

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    author_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
