"""Admin API: управление ролями, правами ролей и назначение ролей пользователям.

Роли создаются master admin (`roles.manage`), назначение пользователям —
`users.manage`. Системные роли (`athlete`, `organizer`, `master-admin`) нельзя
переименовывать, менять их права или удалять. Роль, назначенную пользователю,
удалить нельзя (409 ROLE_IN_USE).
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.modules.competitions.models import AthleteDiscipline
from app.modules.identity.models import AthleteProfile, Role, RolePermission, User
from app.modules.identity.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_GROUPS,
    PERMISSION_LABELS,
    validate_permissions,
)
from app.modules.identity.roles import get_role_or_404, role_permissions
from app.modules.identity.security import Principal, require_permission

router = APIRouter(prefix="/admin", tags=["Admin"])

PageQuery = Query(default=1, ge=1)
PageSizeQuery = Query(default=20, ge=1, le=100, alias="pageSize")


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


# ---------- Схемы ----------


class PermissionGroupResponse(BaseModel):
    section: str
    label: str
    codes: list[str]


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    isSystem: bool
    permissions: list[str]
    createdAt: str


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    permissions: list[str] = Field(default_factory=list)


class RolePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=200)

    @property
    def has_fields(self) -> bool:
        return self.name is not None or self.description is not None


class PermissionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: list[str]


class AdminUser(BaseModel):
    id: UUID
    email: str
    fullName: str | None
    roleId: UUID
    roleName: str
    createdAt: str


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    page: int
    pageSize: int
    total: int


class MailingRecipient(BaseModel):
    id: UUID
    email: str
    fullName: str | None
    roleName: str
    locality: str | None
    education: str | None
    disciplineIds: list[UUID]


class AssignRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roleId: UUID


# ---------- Построение ответов ----------


def _role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        isSystem=role.is_system,
        permissions=role_permissions(role),
        createdAt=iso_z(role.created_at),
    )


def _admin_user_response(user: User, full_name: str | None) -> AdminUser:
    return AdminUser(
        id=user.id,
        email=user.email,
        fullName=full_name,
        roleId=user.role_id,
        roleName=user.role.name,
        createdAt=iso_z(user.created_at),
    )


def _load_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)).all())


# ---------- Каталог прав ----------


@router.get("/permissions", response_model=list[PermissionGroupResponse])
def list_permissions(_: Principal = Depends(require_permission("roles.manage"))) -> list[PermissionGroupResponse]:
    return [
        PermissionGroupResponse(section=section, label=PERMISSION_LABELS[section], codes=codes)
        for section, codes in PERMISSION_GROUPS.items()
    ]


# ---------- Роли ----------


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(_: Principal = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)) -> list[RoleResponse]:
    return [_role_response(role) for role in _load_roles(db)]


@router.post("/roles", response_model=RoleResponse, status_code=201)
def create_role(
    body: RoleCreate,
    _: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    try:
        validate_permissions(body.permissions)
    except ValueError as error:
        raise ApiError(422, "VALIDATION_ERROR", str(error))
    name = body.name.strip()
    if db.scalar(select(Role.id).where(Role.name == name)) is not None:
        raise ApiError(409, "ROLE_EXISTS", "Роль с таким названием уже существует.")
    role = Role(name=name, description=body.description, is_system=False)
    db.add(role)
    db.flush()
    for code in body.permissions:
        db.add(RolePermission(role_id=role.id, permission_code=code))
    db.commit()
    db.refresh(role)
    return _role_response(role)


@router.patch("/roles/{roleId}", response_model=RoleResponse)
def update_role(
    roleId: UUID,
    body: RolePatch,
    _: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    if not body.has_fields:
        raise ApiError(422, "VALIDATION_ERROR", "Нужно передать хотя бы одно поле.")
    role = get_role_or_404(db, roleId)
    if role.is_system:
        raise ApiError(403, "ROLE_SYSTEM", "Системную роль нельзя изменять.")
    if body.name is not None:
        name = body.name.strip()
        existing = db.scalar(select(Role.id).where(Role.name == name, Role.id != roleId))
        if existing is not None:
            raise ApiError(409, "ROLE_EXISTS", "Роль с таким названием уже существует.")
        role.name = name
    if body.description is not None:
        role.description = body.description
    db.commit()
    db.refresh(role)
    return _role_response(role)


@router.delete("/roles/{roleId}", status_code=204)
def delete_role(
    roleId: UUID,
    _: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
) -> None:
    role = get_role_or_404(db, roleId)
    if role.is_system:
        raise ApiError(403, "ROLE_SYSTEM", "Системную роль нельзя удалить.")
    if db.scalar(select(User.id).where(User.role_id == roleId)) is not None:
        raise ApiError(409, "ROLE_IN_USE", "Роль назначена пользователю, сначала переназначьте её.")
    db.delete(role)
    db.commit()


@router.put("/roles/{roleId}/permissions", response_model=RoleResponse)
def update_role_permissions(
    roleId: UUID,
    body: PermissionsUpdate,
    _: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    try:
        validate_permissions(body.permissions)
    except ValueError as error:
        raise ApiError(422, "VALIDATION_ERROR", str(error))
    role = get_role_or_404(db, roleId)
    if role.is_system:
        raise ApiError(403, "ROLE_SYSTEM", "Права системной роли менять нельзя.")
    if len(set(body.permissions)) != len(body.permissions):
        raise ApiError(422, "VALIDATION_ERROR", "Список прав не должен содержать дубликаты.")
    db.execute(delete(RolePermission).where(RolePermission.role_id == roleId))
    for code in body.permissions:
        db.add(RolePermission(role_id=roleId, permission_code=code))
    db.commit()
    db.refresh(role)
    return _role_response(role)


# ---------- Пользователи ----------


@router.get("/users", response_model=AdminUserPage)
def list_users(
    page: int = PageQuery,
    pageSize: int = PageSizeQuery,
    _: Principal = Depends(require_permission("users.manage")),
    db: Session = Depends(get_db),
) -> AdminUserPage:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.execute(
        select(User, AthleteProfile.full_name)
        .outerjoin(AthleteProfile, AthleteProfile.user_id == User.id)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    ).all()
    items = [_admin_user_response(user, full_name) for user, full_name in rows]
    return AdminUserPage(items=items, page=page, pageSize=pageSize, total=total)


@router.get("/mailing-recipients", response_model=list[MailingRecipient])
def list_mailing_recipients(
    _: Principal = Depends(require_permission("mailings.manage")),
    db: Session = Depends(get_db),
) -> list[MailingRecipient]:
    """Данные аудитории для подготовки рассылки. Письма этим endpoint не отправляются."""
    rows = db.execute(
        select(User, AthleteProfile)
        .outerjoin(AthleteProfile, AthleteProfile.user_id == User.id)
        .order_by(User.created_at.desc(), User.id.desc())
    ).all()
    user_ids = [user.id for user, _ in rows]
    discipline_rows = db.execute(
        select(AthleteDiscipline.user_id, AthleteDiscipline.discipline_id)
        .where(AthleteDiscipline.user_id.in_(user_ids))
    ).all() if user_ids else []
    discipline_ids: dict[UUID, list[UUID]] = {}
    for user_id, discipline_id in discipline_rows:
        discipline_ids.setdefault(user_id, []).append(discipline_id)
    return [
        MailingRecipient(
            id=user.id,
            email=user.email,
            fullName=profile.full_name if profile else None,
            roleName=user.role.name,
            locality=profile.locality if profile else None,
            education=profile.education if profile else None,
            disciplineIds=discipline_ids.get(user.id, []),
        )
        for user, profile in rows
    ]


@router.put("/users/{userId}/role", response_model=AdminUser)
def assign_user_role(
    userId: UUID,
    body: AssignRoleRequest,
    _: Principal = Depends(require_permission("users.manage")),
    db: Session = Depends(get_db),
) -> AdminUser:
    user = db.get(User, userId)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "Пользователь не найден.")
    role = get_role_or_404(db, body.roleId)
    user.role_id = role.id
    db.commit()
    db.refresh(user)
    profile = db.get(AthleteProfile, userId)
    return _admin_user_response(user, profile.full_name if profile else None)
