"""Initial application schema.

Revision ID: 20260602_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("login_id", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_login_id", "users", ["login_id"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)

    op.create_table(
        "login_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("login_id", sa.String(80), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(160)),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_logs_user_id", "login_logs", ["user_id"])
    op.create_index("ix_login_logs_login_id", "login_logs", ["login_id"])

    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("pipeline_json", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_edited_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pipelines_slug", "pipelines", ["slug"], unique=True)
    op.create_index("ix_pipelines_created_by_user_id", "pipelines", ["created_by_user_id"])
    op.create_index("ix_pipelines_last_edited_by_user_id", "pipelines", ["last_edited_by_user_id"])

    op.create_table(
        "pipeline_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("old_name", sa.String(200)),
        sa.Column("new_name", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pipeline_logs_pipeline_id", "pipeline_logs", ["pipeline_id"])
    op.create_index("ix_pipeline_logs_user_id", "pipeline_logs", ["user_id"])

    op.create_table(
        "pipeline_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("day_of_week", sa.String(80), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("apscheduler_job_id", sa.String(160), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(20)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pipeline_schedules_pipeline_id", "pipeline_schedules", ["pipeline_id"])
    op.create_index("ix_pipeline_schedules_created_by_user_id", "pipeline_schedules", ["created_by_user_id"])
    op.create_index("ix_pipeline_schedules_status", "pipeline_schedules", ["status"])
    op.create_index("ix_pipeline_schedules_apscheduler_job_id", "pipeline_schedules", ["apscheduler_job_id"], unique=True)

    op.create_table(
        "schedule_run_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("pipeline_schedules.id"), nullable=False),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("rows_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schedule_run_logs_schedule_id", "schedule_run_logs", ["schedule_id"])
    op.create_index("ix_schedule_run_logs_pipeline_id", "schedule_run_logs", ["pipeline_id"])
    op.create_index("ix_schedule_run_logs_status", "schedule_run_logs", ["status"])


def downgrade():
    for table in [
        "schedule_run_logs",
        "pipeline_schedules",
        "pipeline_logs",
        "pipelines",
        "login_logs",
        "user_sessions",
        "users",
    ]:
        op.drop_table(table)
