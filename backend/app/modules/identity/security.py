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
    permissions: frozenset[str] = frozenset()

    def has(self, *codes: str) -> bool:
        return bool(self.permissions.intersection(codes))


def create_token(user_id: UUID, role: str, permissions: list[str] | None = None) -> str:
    now = datetime.now(timezone.utc)
    settings = get_settings()
    claims: dict = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=settings.jwt_ttl_hours)}
    if permissions is not None:
        claims["perms"] = list(permissions)
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


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
        if not isinstance(role, str) or not role:
            return None
        raw_permissions = claims.get("perms") or []
        permissions = frozenset(str(item) for item in raw_permissions) if isinstance(raw_permissions, list) else frozenset()
        return Principal(user_id=UUID(claims["sub"]), role=role, permissions=permissions)
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


def require_permission(*codes: str):
    """Разрешает запрос только при наличии хотя бы одного из переданных прав."""

    def check(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has(*codes):
            raise ApiError(403, "FORBIDDEN", "Недостаточно прав.")
        return principal

    return check
