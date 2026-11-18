"""Allow queue records to exist before a run starts.

Revision ID: 20260602_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0003"
down_revision = "20260602_0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )


def downgrade():
    op.execute("UPDATE schedule_run_logs SET started_at = created_at WHERE started_at IS NULL")
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
