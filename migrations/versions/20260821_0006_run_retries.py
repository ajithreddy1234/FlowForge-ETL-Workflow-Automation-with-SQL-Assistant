"""Add bounded exponential retry state.

Revision ID: 20260821_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20260821_0006"
down_revision = "20260821_0005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_schedule_run_logs_next_attempt_at", ["next_attempt_at"])


def downgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.drop_index("ix_schedule_run_logs_next_attempt_at")
        batch.drop_column("next_attempt_at")
        batch.drop_column("max_attempts")
        batch.drop_column("attempt_count")
