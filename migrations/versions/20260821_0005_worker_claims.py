"""Add durable worker claim ownership.

Revision ID: 20260821_0005
"""

from alembic import op
import sqlalchemy as sa

revision = "20260821_0005"
down_revision = "20260821_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("worker_id", sa.String(160), nullable=True))
        batch.create_index("ix_schedule_run_logs_claimed_at", ["claimed_at"])
        batch.create_index("ix_schedule_run_logs_worker_id", ["worker_id"])


def downgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.drop_index("ix_schedule_run_logs_worker_id")
        batch.drop_index("ix_schedule_run_logs_claimed_at")
        batch.drop_column("worker_id")
        batch.drop_column("claimed_at")
