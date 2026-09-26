"""Add code tasks, private test cases and judging results.

Revision ID: 0007_code_judge
Revises: 0006_roles
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_code_judge"
down_revision = "0006_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("judging_mode", sa.String(10), nullable=False, server_default="manual"))
    op.add_column("tasks", sa.Column("time_limit_seconds", sa.Integer(), nullable=False, server_default="15"))
    op.add_column("tasks", sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="128"))
    op.add_column("tasks", sa.Column("visible_test_count", sa.Integer(), nullable=False, server_default="2"))
    op.create_check_constraint("ck_tasks_judging_mode", "tasks", "judging_mode IN ('manual', 'code')")
    op.create_check_constraint("ck_tasks_time_limit", "tasks", "time_limit_seconds BETWEEN 1 AND 60")
    op.create_check_constraint("ck_tasks_memory_limit", "tasks", "memory_limit_mb BETWEEN 32 AND 512")
    op.create_check_constraint("ck_tasks_visible_tests", "tasks", "visible_test_count BETWEEN 0 AND 50")
    op.create_table(
        "task_test_cases",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("task_id", sa.Uuid(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.UniqueConstraint("task_id", "order_index", name="uq_task_test_case_order"),
    )
    op.add_column("submissions", sa.Column("language", sa.String(20)))
    op.add_column("submissions", sa.Column("verdict", sa.String(30)))
    op.add_column("submissions", sa.Column("failed_test_index", sa.Integer()))
    op.add_column("submissions", sa.Column("time_ms", sa.Integer()))
    op.add_column("submissions", sa.Column("memory_kb", sa.Integer()))
    op.add_column("submissions", sa.Column("judge_details", sa.JSON()))
    op.add_column("submissions", sa.Column("judge_message", sa.String(4000)))
    op.add_column("submissions", sa.Column("judge_token", sa.Uuid(as_uuid=True)))
    op.add_column("submissions", sa.Column("judge_started_at", sa.DateTime(timezone=True)))
    op.drop_constraint("ck_submissions_kind", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_kind", "submissions", "kind IN ('text', 'link', 'code')")


def downgrade() -> None:
    op.drop_constraint("ck_submissions_kind", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_kind", "submissions", "kind IN ('text', 'link')")
    for name in ("judge_started_at", "judge_token", "judge_message", "judge_details", "memory_kb", "time_ms", "failed_test_index", "verdict", "language"):
        op.drop_column("submissions", name)
    op.drop_table("task_test_cases")
    for name in ("ck_tasks_visible_tests", "ck_tasks_memory_limit", "ck_tasks_time_limit", "ck_tasks_judging_mode"):
        op.drop_constraint(name, "tasks", type_="check")
    for name in ("visible_test_count", "memory_limit_mb", "time_limit_seconds", "judging_mode"):
        op.drop_column("tasks", name)
