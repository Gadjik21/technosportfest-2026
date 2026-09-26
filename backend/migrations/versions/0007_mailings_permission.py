"""Grant the mailing UI permission to existing master admins.

Revision ID: 0007_mailings_permission
Revises: 0006_roles
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_mailings_permission"
down_revision = "0006_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_code) "
            "SELECT id, 'mailings.manage' FROM roles WHERE name = 'master-admin' "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions "
            "WHERE role_id = roles.id AND permission_code = 'mailings.manage')"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code = 'mailings.manage'")
    )
