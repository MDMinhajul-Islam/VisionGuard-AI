# Sprint 5A Database Audit

Sprint 4 used SQLAlchemy 2.x with one synchronous SQLite engine, `Base.metadata.create_all`, and an idempotent SQLite-only migration. HTTP handlers, authentication, startup recovery, scripts, and the local worker opened `SessionLocal` directly. Python enforced tenant access, but the database did not.

Confirmed gaps were SQLite-specific connection handling, no versioned schema history, no least-privileged database role, no database-enforced tenant boundary, no pool-context test, and no tested PostgreSQL restore. The file-backed model registry under `evaluations/registry` is not relational data and remains unchanged.

## Ownership classification

| Class | Tables | Boundary |
|---|---|---|
| Tenant root | `organizations`, `organization_memberships`, `audit_events` | Organization |
| Site root | `sites`, `site_access`, `videos` | Organization plus authorized site |
| Video descendants | `processing_jobs`, `video_frames`, `object_detections`, `pose_evidence`, `safety_zones`, `candidate_events`, `embedding_caches`, `exported_clips`, `validation_annotations`, `dataset_assets` | Owning video's organization/site |
| User/security | `users`, `auth_sessions` | Backend security subsystem; login precedes tenant selection |
| Migration metadata | `alembic_version` | Migration role only |
| Protected context | `visionguard_context.transaction_context` | No direct application-role access |

Research status is represented by `organizations.workspace_type`. The deterministic Legacy Research Workspace remains restricted and owns all migrated research media. No research record was assigned to a commercial organization.

The first transactional migration found a missing database-level `CREATE` grant and rolled back. The first RLS test found omitted `EXECUTE` grants for three read-only policy helpers; queries failed closed. Chromium then exposed a tenant-selection initialization race that produced a valid empty RLS result. All three were corrected and regression-tested.

Request sessions now receive verified actor/organization/site context per transaction. Workers receive a job ID and re-derive ownership through a protected database function. Startup recovery obtains recoverable IDs through a narrow function and binds each job independently. The queue remains single-process and is not a durable distributed worker system.
