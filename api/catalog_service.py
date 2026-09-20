import logging
from collections.abc import Iterable

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from api.connection_profiles import allowed_schemas, profile_uri
from api.database import (
    CatalogColumn,
    CatalogRelationship,
    CatalogSnapshot,
    CatalogTable,
    ConnectionProfile,
    app_now,
)
from src.config import (
    CATALOG_MAX_COLUMNS_PER_TABLE,
    CATALOG_MAX_TABLES,
    get_engine_kwargs,
)

logger = logging.getLogger(__name__)

SYSTEM_SCHEMAS = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
    "pg_catalog",
    "pg_internal",
}


def sync_catalog(db: Session, profile: ConnectionProfile) -> CatalogSnapshot:
    snapshot = CatalogSnapshot(
        connection_id=profile.id,
        status="syncing",
        dialect=profile.db_type,
        created_at=app_now(),
    )
    db.add(snapshot)
    db.flush()

    engine = create_engine(
        profile_uri(profile), pool_pre_ping=True, **get_engine_kwargs(profile_uri(profile))
    )
    try:
        inspector = inspect(engine)
        schemas = _schemas_to_scan(inspector, profile)
        table_count = 0
        column_count = 0

        for schema in schemas:
            definitions = [
                (name, "table") for name in _safe_names(inspector.get_table_names, schema)
            ]
            definitions.extend(
                (name, "view") for name in _safe_names(inspector.get_view_names, schema)
            )

            for table_name, table_type in definitions:
                if table_count >= CATALOG_MAX_TABLES:
                    break
                table = CatalogTable(
                    snapshot_id=snapshot.id,
                    schema_name=schema,
                    table_name=table_name,
                    table_type=table_type,
                    table_comment=_table_comment(inspector, table_name, schema),
                )
                db.add(table)
                db.flush()

                pk_columns = set(
                    (_safe_call(inspector.get_pk_constraint, table_name, schema=schema) or {}).get(
                        "constrained_columns", []
                    )
                )
                columns = _safe_call(inspector.get_columns, table_name, schema=schema) or []
                for ordinal, column in enumerate(
                    columns[:CATALOG_MAX_COLUMNS_PER_TABLE], start=1
                ):
                    db.add(
                        CatalogColumn(
                            table_id=table.id,
                            column_name=str(column.get("name") or ""),
                            data_type=str(column.get("type") or "unknown"),
                            is_nullable=bool(column.get("nullable", True)),
                            ordinal_position=ordinal,
                            is_primary_key=column.get("name") in pk_columns,
                            column_comment=column.get("comment"),
                        )
                    )
                    column_count += 1

                for fk in _safe_call(
                    inspector.get_foreign_keys, table_name, schema=schema
                ) or []:
                    target_schema = fk.get("referred_schema") or schema
                    constrained = fk.get("constrained_columns") or []
                    referred = fk.get("referred_columns") or []
                    for source_column, target_column in zip(constrained, referred):
                        db.add(
                            CatalogRelationship(
                                snapshot_id=snapshot.id,
                                source_schema=schema,
                                source_table=table_name,
                                source_column=source_column,
                                target_schema=target_schema,
                                target_table=fk.get("referred_table") or "",
                                target_column=target_column,
                                constraint_name=fk.get("name"),
                            )
                        )
                table_count += 1
            if table_count >= CATALOG_MAX_TABLES:
                break

        snapshot.status = "ready"
        snapshot.table_count = table_count
        snapshot.column_count = column_count
        db.commit()
        db.refresh(snapshot)
        logger.info(
            "Catalog synchronized connection_id=%s tables=%s columns=%s",
            profile.id,
            table_count,
            column_count,
        )
        return snapshot
    except Exception as exc:
        db.rollback()
        failed = db.query(CatalogSnapshot).filter(CatalogSnapshot.id == snapshot.id).first()
        if failed:
            failed.status = "failed"
            failed.error_message = str(exc)
            db.commit()
        raise RuntimeError(f"Metadata sync failed: {exc}") from exc
    finally:
        engine.dispose()


def latest_catalog(db: Session, connection_id: int) -> CatalogSnapshot | None:
    return (
        db.query(CatalogSnapshot)
        .filter(CatalogSnapshot.connection_id == connection_id)
        .filter(CatalogSnapshot.status == "ready")
        .order_by(CatalogSnapshot.created_at.desc(), CatalogSnapshot.id.desc())
        .first()
    )


def catalog_to_dict(snapshot: CatalogSnapshot, include_columns: bool = True) -> dict:
    tables = []
    for table in sorted(snapshot.tables, key=lambda item: (item.schema_name, item.table_name)):
        item = {
            "schema": table.schema_name,
            "name": table.table_name,
            "type": table.table_type,
            "comment": table.table_comment,
        }
        if include_columns:
            item["columns"] = [
                {
                    "name": column.column_name,
                    "type": column.data_type,
                    "nullable": column.is_nullable,
                    "primary_key": column.is_primary_key,
                    "comment": column.column_comment,
                }
                for column in sorted(table.columns, key=lambda col: col.ordinal_position)
            ]
        tables.append(item)
    return {
        "id": snapshot.id,
        "connection_id": snapshot.connection_id,
        "status": snapshot.status,
        "dialect": snapshot.dialect,
        "table_count": snapshot.table_count,
        "column_count": snapshot.column_count,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "tables": tables,
        "relationships": [
            {
                "source_schema": rel.source_schema,
                "source_table": rel.source_table,
                "source_column": rel.source_column,
                "target_schema": rel.target_schema,
                "target_table": rel.target_table,
                "target_column": rel.target_column,
                "constraint_name": rel.constraint_name,
            }
            for rel in snapshot.relationships
        ],
    }


def _schemas_to_scan(inspector, profile: ConnectionProfile) -> list[str]:
    configured = allowed_schemas(profile)
    if configured:
        return list(dict.fromkeys(configured))

    if profile.db_type == "mysql":
        return [profile.database_name]

    schemas = _safe_call(inspector.get_schema_names) or []
    usable = [
        schema
        for schema in schemas
        if schema and schema.lower() not in SYSTEM_SCHEMAS and not schema.startswith("pg_")
    ]
    default_schema = getattr(inspector, "default_schema_name", None)
    if default_schema and default_schema in usable:
        usable.remove(default_schema)
        usable.insert(0, default_schema)
    return usable or [default_schema or "public"]


def _safe_names(method, schema: str) -> list[str]:
    value = _safe_call(method, schema=schema) or []
    return [str(item) for item in value if str(item).strip()]


def _safe_call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except Exception:
        logger.warning("Metadata inspector operation failed", exc_info=True)
        return None


def _table_comment(inspector, table_name: str, schema: str) -> str | None:
    value = _safe_call(inspector.get_table_comment, table_name, schema=schema) or {}
    return value.get("text")
