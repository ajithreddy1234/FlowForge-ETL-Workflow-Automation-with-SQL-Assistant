"""Store per-schedule incremental extract checkpoints.

Revision ID: 20260920_0008
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_0008"
down_revision = "20260821_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extract_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("pipeline_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extract_node_id", sa.String(120), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_id", "extract_node_id", name="uq_extract_checkpoint_scope"),
    )
    op.create_index("ix_extract_checkpoints_schedule_id", "extract_checkpoints", ["schedule_id"])


def downgrade():
    op.drop_index("ix_extract_checkpoints_schedule_id", table_name="extract_checkpoints")
    op.drop_table("extract_checkpoints")
