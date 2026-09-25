"""Профиль спортсмена: GET /me и PATCH /me.

Только для роли athlete. PATCH меняет только переданные поля; `null` очищает
nullable-поля education/locality. disciplineIds — полный новый набор без дублей;
все ID должны существовать в справочнике дисциплин.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.modules.competitions.models import AthleteDiscipline, Discipline
from app.modules.identity.models import AthleteProfile, User
from app.modules.identity.security import Principal, require_role

router = APIRouter(tags=["Profile"])


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: dict
    fullName: str
    education: str | None
    locality: str | None
    disciplineIds: list[UUID]


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str | None = Field(default=None, min_length=2, max_length=150)
    education: str | None = Field(default=None, max_length=200)
    locality: str | None = Field(default=None, max_length=150)
    disciplineIds: list[UUID] | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ProfilePatch":
        if not self.model_fields_set:
            raise ValueError("Нужно передать хотя бы одно поле.")
        return self


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "createdAt": iso_z(user.created_at),
    }


def _profile_response(db: Session, profile: AthleteProfile) -> ProfileResponse:
    user = db.get(User, profile.user_id)
    discipline_ids = list(
        db.scalars(
            select(AthleteDiscipline.discipline_id).where(AthleteDiscipline.user_id == profile.user_id)
        ).all()
    )
    return ProfileResponse(
        user=_user_response(user),
        fullName=profile.full_name,
        education=profile.education,
        locality=profile.locality,
        disciplineIds=discipline_ids,
    )


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    principal: Principal = Depends(require_role("athlete")), db: Session = Depends(get_db)
) -> ProfileResponse:
    profile = db.get(AthleteProfile, principal.user_id)
    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Профиль не найден.")
    return _profile_response(db, profile)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    body: ProfilePatch,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = db.get(AthleteProfile, principal.user_id)
    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Профиль не найден.")
    data = body.model_dump(exclude_unset=True)
    if "fullName" in data:
        profile.full_name = data["fullName"].strip()
    if "education" in data:
        profile.education = data["education"]
    if "locality" in data:
        profile.locality = data["locality"]
    if "disciplineIds" in data:
        discipline_ids = data["disciplineIds"]
        if len(set(discipline_ids)) != len(discipline_ids):
            raise ApiError(422, "VALIDATION_ERROR", "Список дисциплин не должен содержать дубликаты.")
        existing = set(
            db.scalars(select(Discipline.id).where(Discipline.id.in_(discipline_ids))).all()
        ) if discipline_ids else set()
        if existing != set(discipline_ids):
            raise ApiError(422, "VALIDATION_ERROR", "Одна или несколько дисциплин не найдены.")
        db.execute(delete(AthleteDiscipline).where(AthleteDiscipline.user_id == principal.user_id))
        for discipline_id in discipline_ids:
            db.add(AthleteDiscipline(user_id=principal.user_id, discipline_id=discipline_id))
    db.commit()
    db.refresh(profile)
    return _profile_response(db, profile)