"""Хелперы работы с ролями: системные роли, права роли, токены.

Системные роли создаются идемпотентно (`ensure_system_roles`) — это позволяет
работать и после миграции, и в тестах/новых окружениях, где `create_all` ещё
не знает о ролях.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import Role, RolePermission
from app.modules.identity.permissions import (
    ROLE_ATHLETE,
    SYSTEM_ROLE_DESCRIPTIONS,
    SYSTEM_ROLE_PERMISSIONS,
)


def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.scalar(select(Role).where(Role.name == name))


def get_role_or_404(db: Session, role_id: UUID, message: str = "Роль не найдена.") -> Role:
    role = db.get(Role, role_id)
    if role is None:
        from app.errors import ApiError

        raise ApiError(404, "NOT_FOUND", message)
    return role


def ensure_system_roles(db: Session) -> None:
    """Создаёт системные роли и их права, если их ещё нет. Идемпотентно."""
    created = False
    for name, codes in SYSTEM_ROLE_PERMISSIONS.items():
        role = get_role_by_name(db, name)
        if role is None:
            role = Role(name=name, description=SYSTEM_ROLE_DESCRIPTIONS[name], is_system=True)
            db.add(role)
            db.flush()
            created = True
        existing = {permission.permission_code for permission in role.permissions}
        for code in codes:
            if code not in existing:
                db.add(RolePermission(role_id=role.id, permission_code=code))
                created = True
    if created:
        db.commit()


def get_athlete_role(db: Session) -> Role:
    ensure_system_roles(db)
    role = get_role_by_name(db, ROLE_ATHLETE)
    assert role is not None
    return role


def role_permissions(role: Role) -> list[str]:
    """Отсортированный список кодов прав роли."""
    return sorted(permission.permission_code for permission in role.permissions)