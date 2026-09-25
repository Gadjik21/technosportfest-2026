from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.modules.competitions.ports import CompetitionPort
from app.modules.identity.ports import IdentityPort
from app.modules.identity.security import Principal, get_current_principal, require_role
from app.modules.results import service
from app.modules.results.deps import get_competition_port, get_identity_port
from app.modules.results.models import Result

router = APIRouter(tags=["Results", "Rating"])


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class ResultDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    place: int = Field(ge=1)
    scoreText: str | None = Field(default=None, max_length=500)


class ResultDraftResponse(BaseModel):
    id: UUID
    registrationId: UUID
    competitionId: UUID
    athleteId: UUID
    fullName: str
    place: int
    scoreText: str | None
    status: str
    updatedAt: str


class ResultDraftPageResponse(BaseModel):
    items: list[ResultDraftResponse]
    page: int
    pageSize: int
    total: int


class ResultResponse(BaseModel):
    id: UUID
    registrationId: UUID
    competitionId: UUID
    athleteId: UUID
    fullName: str
    place: int
    scoreText: str | None
    points: int
    publishedAt: str


class ResultPageResponse(BaseModel):
    items: list[ResultResponse]
    page: int
    pageSize: int
    total: int


class PublishResultsResponse(BaseModel):
    competitionId: UUID
    status: str
    publishedCount: int
    publishedAt: str


class RatingRowResponse(BaseModel):
    athleteId: UUID
    fullName: str
    points: int
    rank: int
    resultsCount: int


class RatingResponse(BaseModel):
    disciplineId: UUID | None
    formula: str
    items: list[RatingRowResponse]
    page: int
    pageSize: int
    total: int


class MyRatingResponse(BaseModel):
    athleteId: UUID
    disciplineId: UUID | None
    points: int
    rank: int | None
    resultsCount: int


RATING_FORMULA = "1 место — 100, 2 — 70, 3 — 50, остальные — 20; сумма опубликованных результатов"


def _draft_response(result: Result, full_name: str) -> ResultDraftResponse:
    return ResultDraftResponse(
        id=result.id,
        registrationId=result.registration_id,
        competitionId=result.competition_id,
        athleteId=result.athlete_id,
        fullName=full_name,
        place=result.place,
        scoreText=result.score_text,
        status=result.status,
        updatedAt=iso_z(result.updated_at),
    )


def _result_response(result: Result, full_name: str) -> ResultResponse:
    return ResultResponse(
        id=result.id,
        registrationId=result.registration_id,
        competitionId=result.competition_id,
        athleteId=result.athlete_id,
        fullName=full_name,
        place=result.place,
        scoreText=result.score_text,
        points=result.points(),
        publishedAt=iso_z(result.published_at),
    )


PageQuery = Query(default=1, ge=1)
PageSizeQuery = Query(default=20, ge=1, le=100, alias="pageSize")


@router.get("/competitions/{competitionId}/results/drafts", response_model=ResultDraftPageResponse)
def list_result_drafts(
    competitionId: UUID,
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    _: Principal = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> ResultDraftPageResponse:
    if competition_port.get_competition_status(competitionId, db) is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    items, total = service.list_drafts(db, identity_port, competitionId, page, pageSize)
    return ResultDraftPageResponse(items=[_draft_response(r, name) for r, name in items], page=page, pageSize=pageSize, total=total)


@router.post("/competitions/{competitionId}/results/publish", response_model=PublishResultsResponse)
def publish_results(
    competitionId: UUID,
    _: Principal = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> PublishResultsResponse:
    published_count, published_at = service.publish_results(db, competition_port, competitionId)
    return PublishResultsResponse(competitionId=competitionId, status="completed", publishedCount=published_count, publishedAt=iso_z(published_at))


@router.get("/competitions/{competitionId}/results", response_model=ResultPageResponse)
def list_competition_results(
    competitionId: UUID,
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> ResultPageResponse:
    status_ = competition_port.get_competition_status(competitionId, db)
    if status_ is None or status_ == "draft":
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    items, total = service.list_public_results(db, identity_port, competitionId, page, pageSize)
    return ResultPageResponse(items=[_result_response(r, name) for r, name in items], page=page, pageSize=pageSize, total=total)


@router.get("/me/results", response_model=ResultPageResponse)
def list_my_results(
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> ResultPageResponse:
    items, total = service.list_my_results(db, identity_port, principal.user_id, page, pageSize)
    return ResultPageResponse(items=[_result_response(r, name) for r, name in items], page=page, pageSize=pageSize, total=total)


@router.put("/competitions/{competitionId}/results/{registrationId}", response_model=ResultDraftResponse)
def upsert_result_draft(
    competitionId: UUID,
    registrationId: UUID,
    body: ResultDraftRequest,
    _: Principal = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> ResultDraftResponse:
    result = service.upsert_draft(db, competition_port, competitionId, registrationId, body.place, body.scoreText)
    names = identity_port.get_athlete_summaries([result.athlete_id], db)
    full_name = names[result.athlete_id].full_name if result.athlete_id in names else ""
    return _draft_response(result, full_name)


@router.get("/ratings", response_model=RatingResponse)
def get_ratings(
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    disciplineId: UUID | None = None,
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> RatingResponse:
    ranked, total = service.list_ratings(db, competition_port, identity_port, disciplineId, page, pageSize)
    items = [RatingRowResponse(athleteId=row.athlete_id, fullName=row.full_name, points=row.points, rank=rank, resultsCount=row.results_count) for row, rank in ranked]
    return RatingResponse(disciplineId=disciplineId, formula=RATING_FORMULA, items=items, page=page, pageSize=pageSize, total=total)


@router.get("/me/rating", response_model=MyRatingResponse)
def get_my_rating(
    disciplineId: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
    identity_port: IdentityPort = Depends(get_identity_port),
) -> MyRatingResponse:
    points, rank, results_count = service.my_rating(db, competition_port, identity_port, principal.user_id, disciplineId)
    return MyRatingResponse(athleteId=principal.user_id, disciplineId=disciplineId, points=points, rank=rank, resultsCount=results_count)
