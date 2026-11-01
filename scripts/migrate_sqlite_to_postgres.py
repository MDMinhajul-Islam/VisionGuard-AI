from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from sqlalchemy import MetaData, create_engine, func, inspect, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.session import Base  # noqa: E402
from app.database import models  # noqa: F401,E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_preflight(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or violations:
        raise RuntimeError(f"SQLite preflight failed: integrity={integrity}, foreign_key_violations={len(violations)}")
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256(path), "integrity": integrity, "foreign_key_violations": 0}


def row_key(row: dict, primary_keys: list[str]) -> tuple:
    return tuple(row[column] for column in primary_keys)


def migrate(source_path: Path, destination_url: str, dry_run: bool) -> dict:
    started = time.perf_counter()
    preflight = sqlite_preflight(source_path)
    source = create_engine(f"sqlite:///{source_path.as_posix()}")
    destination = create_engine(destination_url, pool_pre_ping=True)
    if destination.dialect.name != "postgresql":
        raise ValueError("destination must be PostgreSQL")
    source_meta = MetaData()
    source_meta.reflect(bind=source)
    destination_tables = set(inspect(destination).get_table_names())
    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    missing = expected_tables - destination_tables
    if missing:
        raise RuntimeError(f"destination schema is missing tables: {sorted(missing)}")

    table_reports = {}
    with source.connect() as source_connection, destination.begin() as destination_connection:
        for table in Base.metadata.sorted_tables:
            source_table = source_meta.tables.get(table.name)
            if source_table is None:
                raise RuntimeError(f"source schema is missing {table.name}")
            rows = [dict(row._mapping) for row in source_connection.execute(select(source_table))]
            primary_keys = [column.name for column in table.primary_key.columns]
            existing_rows = [dict(row._mapping) for row in destination_connection.execute(select(table))]
            existing = {row_key(row, primary_keys): row for row in existing_rows}
            pending = []
            exact_duplicates = 0
            for row in rows:
                key = row_key(row, primary_keys)
                current = existing.get(key)
                if current is None:
                    pending.append(row)
                elif all(current.get(column.name) == row.get(column.name) for column in table.columns):
                    exact_duplicates += 1
                else:
                    raise RuntimeError(f"conflicting destination row in {table.name}: primary_key={key}")
            if pending and not dry_run:
                destination_connection.execute(table.insert(), pending)
            table_reports[table.name] = {
                "source": len(rows), "destination_before": len(existing_rows),
                "inserted": 0 if dry_run else len(pending), "would_insert": len(pending),
                "exact_duplicates": exact_duplicates,
            }
        if dry_run:
            destination_connection.rollback()

    verification = {"counts_match": True, "relationships": {}}
    if not dry_run:
        with destination.connect() as connection:
            for table in Base.metadata.sorted_tables:
                actual = connection.scalar(select(func.count()).select_from(table)) or 0
                minimum = table_reports[table.name]["source"]
                table_reports[table.name]["destination_after"] = actual
                if actual < minimum:
                    verification["counts_match"] = False
            relationship_checks = {
                "jobs_without_video": "SELECT count(*) FROM processing_jobs j LEFT JOIN videos v ON v.id=j.video_id WHERE v.id IS NULL",
                "frames_without_video": "SELECT count(*) FROM video_frames f LEFT JOIN videos v ON v.id=f.video_id WHERE v.id IS NULL",
                "events_without_video": "SELECT count(*) FROM candidate_events e LEFT JOIN videos v ON v.id=e.video_id WHERE v.id IS NULL",
                "annotations_without_video": "SELECT count(*) FROM validation_annotations a LEFT JOIN videos v ON v.id=a.video_id WHERE v.id IS NULL",
                "dataset_assets_without_video": "SELECT count(*) FROM dataset_assets a LEFT JOIN videos v ON v.id=a.video_id WHERE v.id IS NULL",
                "reviewed_events": "SELECT count(*) FROM candidate_events WHERE review_status <> 'pending' OR reviewer_note <> ''",
                "legacy_research_videos": "SELECT count(*) FROM videos WHERE organization_id='00000000-0000-4000-8000-000000000001'",
            }
            from sqlalchemy import text
            for name, statement in relationship_checks.items():
                verification["relationships"][name] = connection.scalar(text(statement))
            verification["relationship_integrity"] = all(
                verification["relationships"][name] == 0 for name in relationship_checks if name.endswith("without_video")
            )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
        "source": preflight, "tables": table_reports, "verification": verification,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate VisionGuard SQLite records into an already-migrated PostgreSQL database.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination-url", default=os.environ.get("VISIONGUARD_MIGRATION_DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.destination_url:
        parser.error("--destination-url or VISIONGUARD_MIGRATION_DATABASE_URL is required")
    report = migrate(args.source.resolve(), args.destination_url, args.dry_run)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
