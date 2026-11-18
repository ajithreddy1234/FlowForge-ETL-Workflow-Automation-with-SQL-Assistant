"""Add immutable pipeline versions and pin schedules.

Revision ID: 20260821_0007
"""

from alembic import op
import sqlalchemy as sa

revision = "20260821_0007"
down_revision = "20260821_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pipeline_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("pipeline_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pipeline_id", "version_number", name="uq_pipeline_version_number"),
    )
    op.create_index("ix_pipeline_versions_pipeline_id", "pipeline_versions", ["pipeline_id"])
    op.create_index("ix_pipeline_versions_created_by_user_id", "pipeline_versions", ["created_by_user_id"])
    op.create_index("ix_pipeline_versions_status", "pipeline_versions", ["status"])

    op.execute(
        "INSERT INTO pipeline_versions "
        "(pipeline_id, version_number, pipeline_json, content_hash, status, created_by_user_id, created_at) "
        "SELECT id, 1, pipeline_json, '', 'published', last_edited_by_user_id, updated_at FROM pipelines"
    )

    with op.batch_alter_table("pipeline_schedules") as batch:
        batch.add_column(sa.Column("pipeline_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_pipeline_schedules_pipeline_version_id",
            "pipeline_versions",
            ["pipeline_version_id"],
            ["id"],
        )
        batch.create_index("ix_pipeline_schedules_pipeline_version_id", ["pipeline_version_id"])

    op.execute(
        "UPDATE pipeline_schedules SET pipeline_version_id = "
        "(SELECT id FROM pipeline_versions WHERE pipeline_versions.pipeline_id = pipeline_schedules.pipeline_id "
        "ORDER BY version_number DESC LIMIT 1)"
    )


def downgrade():
    with op.batch_alter_table("pipeline_schedules") as batch:
        batch.drop_index("ix_pipeline_schedules_pipeline_version_id")
        batch.drop_constraint("fk_pipeline_schedules_pipeline_version_id", type_="foreignkey")
        batch.drop_column("pipeline_version_id")
    op.drop_table("pipeline_versions")
