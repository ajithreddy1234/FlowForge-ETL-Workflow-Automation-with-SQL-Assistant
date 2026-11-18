"""Add durable scheduler queue fields.

Revision ID: 20260602_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0002"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_schedule_run_logs_scheduled_for", ["scheduled_for"])
        batch.create_unique_constraint(
            "uq_schedule_run_logs_schedule_scheduled_for", ["schedule_id", "scheduled_for"]
        )


def downgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.drop_constraint("uq_schedule_run_logs_schedule_scheduled_for", type_="unique")
        batch.drop_index("ix_schedule_run_logs_scheduled_for")
        batch.drop_column("queued_at")
        batch.drop_column("scheduled_for")
