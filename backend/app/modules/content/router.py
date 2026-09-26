from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.modules.content.models import Document, News
from app.modules.identity.security import Principal, require_permission

router = APIRouter(tags=["Content"])


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


PageQuery = Query(default=1, ge=1)
PageSizeQuery = Query(default=20, ge=1, le=100, alias="pageSize")


class NewsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


class NewsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=20000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "NewsPatch":
        if self.title is None and self.body is None:
            raise ValueError("Нужно передать хотя бы одно поле.")
        return self


class NewsResponse(BaseModel):
    id: UUID
    title: str
    body: str
    authorId: UUID
    publishedAt: str


class NewsPageResponse(BaseModel):
    items: list[NewsResponse]
    page: int
    pageSize: int
    total: int


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    fileUrl: str = Field(pattern=r"^https://")


class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    fileUrl: str | None = Field(default=None, pattern=r"^https://")

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "DocumentPatch":
        if self.title is None and self.category is None and self.fileUrl is None:
            raise ValueError("Нужно передать хотя бы одно поле.")
        return self


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    category: str
    fileUrl: str
    authorId: UUID
    publishedAt: str


class DocumentPageResponse(BaseModel):
    items: list[DocumentResponse]
    page: int
    pageSize: int
    total: int


def _news_response(news: News) -> NewsResponse:
    return NewsResponse(id=news.id, title=news.title, body=news.body, authorId=news.author_id, publishedAt=iso_z(news.published_at))


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        category=document.category,
        fileUrl=document.file_url,
        authorId=document.author_id,
        publishedAt=iso_z(document.published_at),
    )


@router.get("/news", response_model=NewsPageResponse)
def list_news(page: int = PageQuery, pageSize: int = PageSizeQuery, db: Session = Depends(get_db)) -> NewsPageResponse:
    query = select(News).order_by(News.published_at.desc(), News.id.desc())
    total = db.scalar(select(func.count()).select_from(News)) or 0
    rows = db.scalars(query.offset((page - 1) * pageSize).limit(pageSize)).all()
    return NewsPageResponse(items=[_news_response(n) for n in rows], page=page, pageSize=pageSize, total=total)


@router.post("/news", response_model=NewsResponse, status_code=201)
def create_news(body: NewsCreate, principal: Principal = Depends(require_permission("news.create")), db: Session = Depends(get_db)) -> NewsResponse:
    news = News(id=uuid4(), title=body.title, body=body.body, author_id=principal.user_id)
    db.add(news)
    db.commit()
    db.refresh(news)
    return _news_response(news)


@router.get("/news/{id}", response_model=NewsResponse)
def get_news(id: UUID, db: Session = Depends(get_db)) -> NewsResponse:
    news = db.get(News, id)
    if news is None:
        raise ApiError(404, "NOT_FOUND", "Новость не найдена.")
    return _news_response(news)


@router.patch("/news/{id}", response_model=NewsResponse)
def update_news(id: UUID, body: NewsPatch, _: Principal = Depends(require_permission("news.edit")), db: Session = Depends(get_db)) -> NewsResponse:
    news = db.get(News, id)
    if news is None:
        raise ApiError(404, "NOT_FOUND", "Новость не найдена.")
    if body.title is not None:
        news.title = body.title
    if body.body is not None:
        news.body = body.body
    db.commit()
    db.refresh(news)
    return _news_response(news)


@router.get("/documents", response_model=DocumentPageResponse)
def list_documents(
    page: int = PageQuery, pageSize: int = PageSizeQuery, category: str | None = None, db: Session = Depends(get_db)
) -> DocumentPageResponse:
    query = select(Document)
    count_query = select(func.count()).select_from(Document)
    if category is not None:
        query = query.where(Document.category == category)
        count_query = count_query.where(Document.category == category)
    total = db.scalar(count_query) or 0
    rows = db.scalars(query.order_by(Document.published_at.desc(), Document.id.desc()).offset((page - 1) * pageSize).limit(pageSize)).all()
    return DocumentPageResponse(items=[_document_response(d) for d in rows], page=page, pageSize=pageSize, total=total)


@router.post("/documents", response_model=DocumentResponse, status_code=201)
def create_document(body: DocumentCreate, principal: Principal = Depends(require_permission("documents.create")), db: Session = Depends(get_db)) -> DocumentResponse:
    document = Document(id=uuid4(), title=body.title, category=body.category, file_url=body.fileUrl, author_id=principal.user_id)
    db.add(document)
    db.commit()
    db.refresh(document)
    return _document_response(document)


@router.patch("/documents/{id}", response_model=DocumentResponse)
def update_document(id: UUID, body: DocumentPatch, _: Principal = Depends(require_permission("documents.edit")), db: Session = Depends(get_db)) -> DocumentResponse:
    document = db.get(Document, id)
    if document is None:
        raise ApiError(404, "NOT_FOUND", "Документ не найден.")
    if body.title is not None:
        document.title = body.title
    if body.category is not None:
        document.category = body.category
    if body.fileUrl is not None:
        document.file_url = body.fileUrl
    db.commit()
    db.refresh(document)
    return _document_response(document)
