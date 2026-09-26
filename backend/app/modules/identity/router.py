from datetime import timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.modules.identity.models import AthleteProfile, User
from app.modules.identity.roles import get_athlete_role, role_permissions
from app.modules.identity.security import (
    COOKIE_NAME,
    COOKIE_PATH,
    Principal,
    create_token,
    get_current_principal,
    password_hash,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    fullName: str = Field(min_length=2, max_length=150)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    permissions: list[str]
    createdAt: str


def user_response(user: User) -> UserResponse:
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.name,
        permissions=role_permissions(user.role),
        createdAt=created_at.isoformat().replace("+00:00", "Z"),
    )


def set_access_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_token(user.id, user.role.name, role_permissions(user.role)),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    athlete_role = get_athlete_role(db)
    user = User(email=str(body.email).lower(), password_hash=password_hash.hash(body.password), role_id=athlete_role.id)
    try:
        db.add(user)
        db.flush()
        db.add(AthleteProfile(user_id=user.id, full_name=body.fullName.strip()))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "EMAIL_TAKEN", "Этот email уже зарегистрирован.")
    set_access_cookie(response, user)
    return user_response(user)


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not password_hash.verify(body.password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Неверный email или пароль.")
    set_access_cookie(response, user)
    return user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path=COOKIE_PATH, secure=get_settings().cookie_secure, httponly=True, samesite="lax")


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)) -> UserResponse:
    user = db.get(User, principal.user_id)
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Нужно войти в аккаунт.")
    return user_response(user)
