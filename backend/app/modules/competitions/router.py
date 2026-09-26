"""Маршруты Б1: дисциплины, соревнования, заявки, участники, мои заявки.

Формы соответствуют `contracts/openapi.json`: camelCase, UTC `Z`, списки
с `items/page/pageSize/total`. Каталог сортируется по startsAt,id;
участники по fullName,registrationId; мои заявки по createdAt DESC,id DESC.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.modules.competitions.models import Competition, Discipline, Registration
from app.modules.identity.models import AthleteProfile
from app.modules.identity.security import Principal, require_permission, require_role

router = APIRouter(tags=["Competitions"])

PageQuery = Query(default=1, ge=1)
PageSizeQuery = Query(default=20, ge=1, le=100, alias="pageSize")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return as_utc(value).isoformat().replace("+00:00", "Z")


def optional_principal(request: Request) -> Principal | None:
    return getattr(request.state, "principal", None)


# ---------- Схемы ответов ----------


class DisciplineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str


class CompetitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    disciplineId: UUID
    startsAt: datetime
    endsAt: datetime
    registrationDeadline: datetime
    format: str = Field(pattern="^(online|offline)$")
    description: str = Field(min_length=1, max_length=10000)


class CompetitionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    disciplineId: UUID | None = None
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    registrationDeadline: datetime | None = None
    format: str | None = Field(default=None, pattern="^(online|offline)$")
    description: str | None = Field(default=None, min_length=1, max_length=10000)

    @property
    def has_fields(self) -> bool:
        return any(
            value is not None
            for value in (self.title, self.disciplineId, self.startsAt, self.endsAt, self.registrationDeadline, self.format, self.description)
        )


class CompetitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    discipline: DisciplineResponse
    startsAt: str
    endsAt: str
    registrationDeadline: str
    format: str
    description: str
    status: str
    registrationOpen: bool
    viewerRegistrationId: UUID | None
    createdAt: str


class CompetitionPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompetitionResponse]
    page: int
    pageSize: int
    total: int


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    competition: CompetitionResponse
    athleteId: UUID
    createdAt: str


class RegistrationPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RegistrationResponse]
    page: int
    pageSize: int
    total: int


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registrationId: UUID
    athleteId: UUID
    fullName: str
    education: str | None
    locality: str | None
    registeredAt: str


class ParticipantPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ParticipantResponse]
    page: int
    pageSize: int
    total: int


# ---------- Построение ответов без N+1 ----------


def _discipline_response(discipline: Discipline) -> DisciplineResponse:
    return DisciplineResponse(id=discipline.id, name=discipline.name)


def _competition_response(
    competition: Competition,
    disciplines: dict[UUID, Discipline],
    viewer_registration_ids: dict[UUID, UUID],
) -> CompetitionResponse:
    return CompetitionResponse(
        id=competition.id,
        title=competition.title,
        discipline=_discipline_response(disciplines[competition.discipline_id]),
        startsAt=iso_z(competition.starts_at),
        endsAt=iso_z(competition.ends_at),
        registrationDeadline=iso_z(competition.registration_deadline),
        format=competition.format,
        description=competition.description,
        status=competition.status,
        registrationOpen=competition.status == "published" and as_utc(competition.registration_deadline) > now_utc(),
        viewerRegistrationId=viewer_registration_ids.get(competition.id),
        createdAt=iso_z(competition.created_at),
    )


def build_competition_responses(
    db: Session, competitions: list[Competition], principal: Principal | None
) -> list[CompetitionResponse]:
    """Один запрос за дисциплинами и один за заявками текущего спортсмена."""
    if not competitions:
        return []
    disciplines = {
        d.id: d
        for d in db.scalars(select(Discipline).where(Discipline.id.in_({c.discipline_id for c in competitions}))).all()
    }
    viewer_registration_ids: dict[UUID, UUID] = {}
    if principal is not None and principal.role == "athlete":
        rows = db.execute(
            select(Registration.competition_id, Registration.id).where(
                Registration.athlete_id == principal.user_id,
                Registration.competition_id.in_([c.id for c in competitions]),
            )
        ).all()
        viewer_registration_ids = {competition_id: registration_id for competition_id, registration_id in rows}
    return [_competition_response(c, disciplines, viewer_registration_ids) for c in competitions]


def _registration_response(
    registration: Registration, competition_response: CompetitionResponse, athlete_id: UUID
) -> RegistrationResponse:
    return RegistrationResponse(id=registration.id, competition=competition_response, athleteId=athlete_id, createdAt=iso_z(registration.created_at))


# ---------- Валидация дат и дисциплин ----------


def validate_dates(registration_deadline: datetime, starts_at: datetime, ends_at: datetime) -> None:
    if not (as_utc(registration_deadline) <= as_utc(starts_at) < as_utc(ends_at)):
        raise ApiError(422, "VALIDATION_ERROR", "Даты должны удовлетворять: registrationDeadline <= startsAt < endsAt.")


def require_existing_discipline(db: Session, discipline_id: UUID) -> Discipline:
    discipline = db.get(Discipline, discipline_id)
    if discipline is None:
        raise ApiError(422, "VALIDATION_ERROR", "Дисциплина не найдена.")
    return discipline


# ---------- Дисциплины ----------


@router.get("/disciplines", response_model=list[DisciplineResponse])
def list_disciplines(db: Session = Depends(get_db)) -> list[DisciplineResponse]:
    rows = db.scalars(select(Discipline).order_by(Discipline.name)).all()
    return [_discipline_response(d) for d in rows]


# ---------- Каталог и карточка соревнований ----------


@router.get("/competitions", response_model=CompetitionPageResponse)
def list_competitions(
    request: Request,
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    disciplineId: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> CompetitionPageResponse:
    principal = optional_principal(request)
    query = select(Competition)
    count_query = select(func.count()).select_from(Competition)
    if disciplineId is not None:
        query = query.where(Competition.discipline_id == disciplineId)
        count_query = count_query.where(Competition.discipline_id == disciplineId)
    if status is not None:
        if status == "draft" and (principal is None or not principal.has("competitions.view")):
            raise ApiError(403, "FORBIDDEN", "Недостаточно прав.")
        query = query.where(Competition.status == status)
        count_query = count_query.where(Competition.status == status)
    else:
        query = query.where(Competition.status.in_(["published", "completed"]))
        count_query = count_query.where(Competition.status.in_(["published", "completed"]))
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Competition.starts_at, Competition.id).offset((page - 1) * pageSize).limit(pageSize)
    ).all()
    items = build_competition_responses(db, list(rows), principal)
    return CompetitionPageResponse(items=items, page=page, pageSize=pageSize, total=total)


@router.get("/competitions/{competitionId}", response_model=CompetitionResponse)
def get_competition(
    competitionId: UUID, request: Request, db: Session = Depends(get_db)
) -> CompetitionResponse:
    competition = db.get(Competition, competitionId)
    if competition is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    principal = optional_principal(request)
    if competition.status == "draft" and (principal is None or not principal.has("competitions.view")):
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    return build_competition_responses(db, [competition], principal)[0]


@router.post("/competitions", response_model=CompetitionResponse, status_code=201)
def create_competition(
    body: CompetitionCreate,
    principal: Principal = Depends(require_permission("competitions.create")),
    db: Session = Depends(get_db),
) -> CompetitionResponse:
    require_existing_discipline(db, body.disciplineId)
    validate_dates(body.registrationDeadline, body.startsAt, body.endsAt)
    competition = Competition(
        title=body.title.strip(),
        discipline_id=body.disciplineId,
        starts_at=as_utc(body.startsAt),
        ends_at=as_utc(body.endsAt),
        registration_deadline=as_utc(body.registrationDeadline),
        format=body.format,
        description=body.description,
        status="draft",
    )
    db.add(competition)
    db.commit()
    db.refresh(competition)
    return build_competition_responses(db, [competition], principal)[0]


@router.patch("/competitions/{competitionId}", response_model=CompetitionResponse)
def update_competition(
    competitionId: UUID,
    body: CompetitionPatch,
    principal: Principal = Depends(require_permission("competitions.edit")),
    db: Session = Depends(get_db),
) -> CompetitionResponse:
    if not body.has_fields:
        raise ApiError(422, "VALIDATION_ERROR", "Нужно передать хотя бы одно поле.")
    competition = db.get(Competition, competitionId)
    if competition is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if competition.status != "draft":
        raise ApiError(409, "INVALID_STATE", "Редактировать можно только черновик соревнования.")
    if body.title is not None:
        competition.title = body.title.strip()
    if body.disciplineId is not None:
        require_existing_discipline(db, body.disciplineId)
        competition.discipline_id = body.disciplineId
    if body.startsAt is not None:
        competition.starts_at = as_utc(body.startsAt)
    if body.endsAt is not None:
        competition.ends_at = as_utc(body.endsAt)
    if body.registrationDeadline is not None:
        competition.registration_deadline = as_utc(body.registrationDeadline)
    if body.format is not None:
        competition.format = body.format
    if body.description is not None:
        competition.description = body.description
    validate_dates(competition.registration_deadline, competition.starts_at, competition.ends_at)
    db.commit()
    db.refresh(competition)
    return build_competition_responses(db, [competition], principal)[0]


@router.post("/competitions/{competitionId}/publish", response_model=CompetitionResponse)
def publish_competition(
    competitionId: UUID,
    principal: Principal = Depends(require_permission("competitions.publish")),
    db: Session = Depends(get_db),
) -> CompetitionResponse:
    competition = db.get(Competition, competitionId)
    if competition is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if competition.status != "draft":
        raise ApiError(409, "INVALID_STATE", "Публиковать можно только черновик соревнования.")
    if as_utc(competition.registration_deadline) <= now_utc():
        raise ApiError(409, "REGISTRATION_CLOSED", "Дедлайн регистрации уже прошёл, открыть регистрацию нельзя.")
    competition.status = "published"
    db.commit()
    db.refresh(competition)
    return build_competition_responses(db, [competition], principal)[0]


# ---------- Заявки ----------


@router.post("/competitions/{competitionId}/registrations", response_model=RegistrationResponse, status_code=201)
def create_registration(
    competitionId: UUID,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
) -> RegistrationResponse:
    competition = db.get(Competition, competitionId)
    if competition is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if competition.status != "published" or as_utc(competition.registration_deadline) <= now_utc():
        raise ApiError(409, "REGISTRATION_CLOSED", "Регистрация на это соревнование закрыта.")
    existing = db.scalar(
        select(Registration.id).where(
            Registration.competition_id == competitionId, Registration.athlete_id == principal.user_id
        )
    )
    if existing is not None:
        raise ApiError(409, "ALREADY_REGISTERED", "Вы уже зарегистрированы на это соревнование.")
    registration = Registration(competition_id=competitionId, athlete_id=principal.user_id)
    db.add(registration)
    db.commit()
    db.refresh(registration)
    competition_response = build_competition_responses(db, [competition], principal)[0]
    return _registration_response(registration, competition_response, principal.user_id)


@router.delete("/competitions/{competitionId}/registrations/{registrationId}", status_code=204)
def remove_registration(
    competitionId: UUID,
    registrationId: UUID,
    _: Principal = Depends(require_permission("competitions.edit")),
    db: Session = Depends(get_db),
) -> None:
    competition = db.get(Competition, competitionId)
    if competition is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if competition.status == "completed":
        raise ApiError(409, "INVALID_STATE", "Нельзя убрать участника завершённого соревнования.")
    registration = db.get(Registration, registrationId)
    if registration is None or registration.competition_id != competitionId:
        raise ApiError(404, "NOT_FOUND", "Заявка не найдена.")
    db.delete(registration)
    db.commit()


@router.get("/me/registrations", response_model=RegistrationPageResponse)
def list_my_registrations(
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
) -> RegistrationPageResponse:
    query = (
        select(Registration, Competition)
        .join(Competition, Competition.id == Registration.competition_id)
        .where(Registration.athlete_id == principal.user_id)
    )
    total = (
        db.scalar(
            select(func.count()).select_from(Registration).where(Registration.athlete_id == principal.user_id)
        )
        or 0
    )
    rows = db.execute(
        query.order_by(Registration.created_at.desc(), Registration.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    ).all()
    competitions = [competition for _, competition in rows]
    disciplines = {
        d.id: d
        for d in db.scalars(select(Discipline).where(Discipline.id.in_({c.discipline_id for c in competitions}))).all()
    }
    items = [
        _registration_response(
            registration,
            _competition_response(
                competition,
                disciplines,
                {competition.id: registration.id},  # это и есть заявка текущего спортсмена
            ),
            principal.user_id,
        )
        for registration, competition in rows
    ]
    return RegistrationPageResponse(items=items, page=page, pageSize=pageSize, total=total)


# ---------- Участники ----------


@router.get("/competitions/{competitionId}/participants", response_model=ParticipantPageResponse)
def list_participants(
    competitionId: UUID,
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    _: Principal = Depends(require_permission("competitions.view")),
    db: Session = Depends(get_db),
) -> ParticipantPageResponse:
    if db.get(Competition, competitionId) is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    total = (
        db.scalar(select(func.count()).select_from(Registration).where(Registration.competition_id == competitionId)) or 0
    )
    rows = db.execute(
        select(Registration, AthleteProfile)
        .join(AthleteProfile, AthleteProfile.user_id == Registration.athlete_id)
        .where(Registration.competition_id == competitionId)
        .order_by(AthleteProfile.full_name, Registration.id)
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    ).all()
    items = [
        ParticipantResponse(
            registrationId=registration.id,
            athleteId=registration.athlete_id,
            fullName=profile.full_name,
            education=profile.education,
            locality=profile.locality,
            registeredAt=iso_z(registration.created_at),
        )
        for registration, profile in rows
    ]
    return ParticipantPageResponse(items=items, page=page, pageSize=pageSize, total=total)
