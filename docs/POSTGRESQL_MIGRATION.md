# PostgreSQL Migration

Keep `runtime/visionguard.db` unchanged. Copy `.env.postgres.example` to ignored `.env.postgres`, replace every password, start Compose, wait for health, and run Alembic with `VISIONGUARD_MIGRATION_DATABASE_URL`.

`scripts/migrate_sqlite_to_postgres.py` checks SQLite integrity and foreign keys, hashes the source, follows SQLAlchemy FK order, preserves IDs, rejects conflicting rows, skips exact duplicates, and verifies counts and representative relationships.

```powershell
python scripts/migrate_sqlite_to_postgres.py --source runtime/visionguard.db --dry-run
python scripts/migrate_sqlite_to_postgres.py --source runtime/visionguard.db --report runtime/backups/sprint5a-migration.json
```

The verified migration copied 31 videos, 34 jobs, 368 frames, 653 detections, 1,734 pose rows, 8 events, 18 annotations, 30 dataset assets, 31 embedding caches, one export, 29 audit events, and one user. A rerun inserted zero rows. There were zero orphan jobs, frames, events, annotations, or dataset assets. One reviewed event and all legacy ownership links survived.

This source contained zero session rows, so no cutover invalidation was necessary. Password hashes are copied byte-for-byte; PostgreSQL API login verifies Argon2 authentication without resetting a password.

Rollback: stop the PostgreSQL-backed API, restore `VISIONGUARD_DATABASE_URL` to the unchanged SQLite file, and restart. Do not reverse-copy partially changed PostgreSQL data. For PostgreSQL rollback, restore a verified archive into a new database and switch only after verification.
