from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.config import get_settings
from app.errors import ApiError

COOKIE_NAME = "tsf_access"
COOKIE_PATH = "/api/v1"
password_hash = PasswordHash.recommended()
cookie_scheme = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    role: str


def create_token(user_id: UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    settings = get_settings()
    return jwt.encode(
        {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=settings.jwt_ttl_hours)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str | None) -> Principal | None:
    if not token:
        return None
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "iat", "exp"]},
        )
        role = claims["role"]
        if role not in {"athlete", "organizer"}:
            return None
        return Principal(user_id=UUID(claims["sub"]), role=role)
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return None


def get_current_principal(request: Request, _: str | None = Security(cookie_scheme)) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise ApiError(401, "UNAUTHENTICATED", "Нужно войти в аккаунт.")
    return principal


def require_role(role: str):
    def check(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role != role:
            raise ApiError(403, "FORBIDDEN", "Недостаточно прав.")
        return principal

    return check
