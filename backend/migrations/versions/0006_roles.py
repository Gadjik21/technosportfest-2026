"""Dynamic roles: roles, role_permissions, users.role_id.

Заменяет строковую роль users.role (athlete/organizer) ссылкой на таблицу roles.
Системные роли (athlete, organizer, master-admin) создаются здесь же и бэкфиллят
существующих пользователей; публичный API выдаёт права роли в JWT.

Revision ID: 0006_roles
Revises: 0005_contests
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0006_roles"
down_revision = "0005_contests"
branch_labels = None
depends_on = None

ATHLETE = "athlete"
ORGANIZER = "organizer"
MASTER_ADMIN = "master-admin"

ORGANIZER_PERMISSIONS = [
    "news.view", "news.create", "news.edit", "news.delete",
    "documents.view", "documents.create", "documents.edit", "documents.delete",
    "competitions.view", "competitions.create", "competitions.edit", "competitions.delete", "competitions.publish",
    "contests.tasks", "contests.grade",
    "results.view", "results.save", "results.publish",
]

MASTER_ADMIN_PERMISSIONS = ORGANIZER_PERMISSIONS + ["users.manage", "roles.manage"]

DESCRIPTIONS = {
    ATHLETE: "Спортсмен: заявки, профиль, решения, свои результаты.",
    ORGANIZER: "Организатор: соревнования, контесты, результаты, новости и документы.",
    MASTER_ADMIN: "Администратор платформы: полный доступ и управление ролями и пользователями.",
}


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("description", sa.String(length=200)),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_code", sa.String(length=50), primary_key=True),
    )
    op.add_column("users", sa.Column("role_id", sa.Uuid(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"], ondelete="RESTRICT")

    connection = op.get_bind()
    now = datetime.now(timezone.utc)

    role_ids = {
        ATHLETE: str(uuid.uuid4()),
        ORGANIZER: str(uuid.uuid4()),
        MASTER_ADMIN: str(uuid.uuid4()),
    }
    for name, description in DESCRIPTIONS.items():
        connection.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, is_system, created_at) "
                "VALUES (:id, :name, :description, :is_system, :created_at)"
            ),
            {"id": role_ids[name], "name": name, "description": description, "is_system": True, "created_at": now},
        )

    for name, permissions in ((ORGANIZER, ORGANIZER_PERMISSIONS), (MASTER_ADMIN, MASTER_ADMIN_PERMISSIONS)):
        for code in permissions:
            connection.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_code) VALUES (:role_id, :code)"),
                {"role_id": role_ids[name], "code": code},
            )

    connection.execute(
        sa.text("UPDATE users SET role_id = :role_id WHERE role = :old_role"),
        {"role_id": role_ids[ATHLETE], "old_role": ATHLETE},
    )
    connection.execute(
        sa.text("UPDATE users SET role_id = :role_id WHERE role = :old_role"),
        {"role_id": role_ids[ORGANIZER], "old_role": ORGANIZER},
    )

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
    op.alter_column("users", "role_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)


def downgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True))
    connection = op.get_bind()
    for old_role in (ATHLETE, ORGANIZER):
        connection.execute(
            sa.text("UPDATE users SET role = :old_role WHERE role_id = (SELECT id FROM roles WHERE name = :old_role)"),
            {"old_role": old_role},
        )
    op.alter_column("users", "role", existing_type=sa.String(length=20), nullable=False)
    op.create_check_constraint("ck_users_role", "users", "role IN ('athlete', 'organizer')")
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "role_id")
    op.drop_table("role_permissions")
    op.drop_table("roles")