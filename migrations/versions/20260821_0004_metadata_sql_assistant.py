"""Add server-side connections, metadata catalog, and SQL assistant audit.

Revision ID: 20260821_0004
"""

from alembic import op
import sqlalchemy as sa

revision = "20260821_0004"
down_revision = "20260602_0003"
branch_labels = None
depends_on = None


def upgrade():
    # Re-apply this correction because early SQLite copies were stamped at
    # 0003 without rebuilding the NOT NULL column.
    with op.batch_alter_table("schedule_run_logs") as batch:
        batch.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )

    op.create_table(
        "connection_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("db_type", sa.String(20), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.String(12)),
        sa.Column("database_name", sa.String(120), nullable=False),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("allowed_schemas_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("created_by_user_id", "name", name="uq_connection_profiles_owner_name"),
    )
    op.create_index("ix_connection_profiles_created_by_user_id", "connection_profiles", ["created_by_user_id"])
    op.create_index("ix_connection_profiles_status", "connection_profiles", ["status"])

    op.create_table(
        "catalog_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("connection_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("dialect", sa.String(20), nullable=False),
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_catalog_snapshots_connection_id", "catalog_snapshots", ["connection_id"])
    op.create_index("ix_catalog_snapshots_status", "catalog_snapshots", ["status"])

    op.create_table(
        "catalog_tables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_name", sa.String(160), nullable=False),
        sa.Column("table_name", sa.String(200), nullable=False),
        sa.Column("table_type", sa.String(40), nullable=False),
        sa.Column("table_comment", sa.Text()),
        sa.UniqueConstraint("snapshot_id", "schema_name", "table_name", name="uq_catalog_table_identity"),
    )
    op.create_index("ix_catalog_tables_snapshot_id", "catalog_tables", ["snapshot_id"])

    op.create_table(
        "catalog_columns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("catalog_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_name", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(160), nullable=False),
        sa.Column("is_nullable", sa.Boolean(), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=False),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("column_comment", sa.Text()),
        sa.UniqueConstraint("table_id", "column_name", name="uq_catalog_column_identity"),
    )
    op.create_index("ix_catalog_columns_table_id", "catalog_columns", ["table_id"])

    op.create_table(
        "catalog_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_schema", sa.String(160), nullable=False),
        sa.Column("source_table", sa.String(200), nullable=False),
        sa.Column("source_column", sa.String(200), nullable=False),
        sa.Column("target_schema", sa.String(160), nullable=False),
        sa.Column("target_table", sa.String(200), nullable=False),
        sa.Column("target_column", sa.String(200), nullable=False),
        sa.Column("constraint_name", sa.String(200)),
    )
    op.create_index("ix_catalog_relationships_snapshot_id", "catalog_relationships", ["snapshot_id"])

    op.create_table(
        "sql_assistant_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("connection_profiles.id"), nullable=False),
        sa.Column("catalog_snapshot_id", sa.Integer(), sa.ForeignKey("catalog_snapshots.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("referenced_tables_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("validation_error", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sql_assistant_candidates_connection_id", "sql_assistant_candidates", ["connection_id"])
    op.create_index("ix_sql_assistant_candidates_catalog_snapshot_id", "sql_assistant_candidates", ["catalog_snapshot_id"])
    op.create_index("ix_sql_assistant_candidates_user_id", "sql_assistant_candidates", ["user_id"])
    op.create_index("ix_sql_assistant_candidates_status", "sql_assistant_candidates", ["status"])


def downgrade():
    op.drop_table("sql_assistant_candidates")
    op.drop_table("catalog_relationships")
    op.drop_table("catalog_columns")
    op.drop_table("catalog_tables")
    op.drop_table("catalog_snapshots")
    op.drop_table("connection_profiles")
