# PostgreSQL Architecture

VisionGuard uses PostgreSQL 17.11 from the pinned `postgres:17.11-bookworm` image. Docker Compose stores the cluster under ignored `runtime/postgres-data` on the project drive and exposes the configured localhost port (`54329` by default).

## Roles

- `visionguard_cluster_admin`: local container administration and recovery drills only.
- `visionguard_migrator`: `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `BYPASSRLS`; schema and bulk migration.
- `visionguard_app`: `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOBYPASSRLS`; FastAPI and ordinary workers.

Credentials exist only in ignored `.env.postgres` and backend process environments. The frontend never receives them. The migration URL must never launch ordinary FastAPI requests.

Alembic is the PostgreSQL migration mechanism. `init_db()` retains SQLite compatibility for deterministic tests, but PostgreSQL startup refuses an unmigrated database. Automatic destructive downgrades are disabled; rollback means using the preserved SQLite URL or restoring a verified PostgreSQL archive.

PostgreSQL stores metadata, relationships, sessions, reviews, audits, and provenance. Videos, frames, embeddings, exports, and weights remain on the filesystem. `create_media_manifest.py` records database-to-file dependencies without duplicating participant media.
