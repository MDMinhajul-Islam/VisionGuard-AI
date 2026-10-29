from __future__ import annotations

from sqlalchemy import Engine, inspect, text


LEGACY_RESEARCH_ORG_ID = "00000000-0000-4000-8000-000000000001"
LEGACY_RESEARCH_SITE_ID = "00000000-0000-4000-8000-000000000002"


def _add_column(connection, table: str, column: str, definition: str) -> None:
    columns = {item["name"] for item in inspect(connection).get_columns(table)}
    if column not in columns:
        connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'))


def run_non_destructive_migrations(engine: Engine) -> dict[str, int]:
    """Idempotent SQLite migration for Sprint 4.

    Existing objects are assigned only to a deterministic, disabled-by-default legacy
    research scope. No user receives membership automatically.
    """
    with engine.begin() as connection:
        _add_column(connection, "users", "session_version", "INTEGER NOT NULL DEFAULT 0")
        _add_column(connection, "users", "password_changed_at", "VARCHAR(40)")
        _add_column(connection, "videos", "organization_id", "VARCHAR(36)")
        _add_column(connection, "videos", "site_id", "VARCHAR(36)")
        _add_column(connection, "candidate_events", "reviewer_id", "VARCHAR(36)")
        _add_column(connection, "candidate_events", "reviewed_at", "VARCHAR(40)")
        _add_column(connection, "exported_clips", "created_by_user_id", "VARCHAR(36)")

        connection.execute(text(
            "INSERT OR IGNORE INTO organizations "
            "(id, name, status, workspace_type, created_at) "
            "VALUES (:id, 'Legacy Research Workspace', 'restricted', 'research', CURRENT_TIMESTAMP)"
        ), {"id": LEGACY_RESEARCH_ORG_ID})
        connection.execute(text(
            "INSERT OR IGNORE INTO sites (id, organization_id, name, status, created_at) "
            "VALUES (:id, :organization_id, 'Legacy Imported Data', 'restricted', CURRENT_TIMESTAMP)"
        ), {"id": LEGACY_RESEARCH_SITE_ID, "organization_id": LEGACY_RESEARCH_ORG_ID})
        migrated = connection.execute(text(
            "UPDATE videos SET organization_id=:organization_id, site_id=:site_id "
            "WHERE organization_id IS NULL OR site_id IS NULL"
        ), {"organization_id": LEGACY_RESEARCH_ORG_ID, "site_id": LEGACY_RESEARCH_SITE_ID}).rowcount
        remaining = connection.execute(text(
            "SELECT COUNT(*) FROM videos WHERE organization_id IS NULL OR site_id IS NULL"
        )).scalar_one()
    if remaining:
        raise RuntimeError(f"tenant migration left {remaining} videos without ownership")
    return {"legacy_videos_scoped": max(migrated, 0), "unscoped_videos": remaining}
