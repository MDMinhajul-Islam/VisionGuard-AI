# Production Architecture Direction

## Current bounded architecture

One FastAPI process owns a SQLite database and a one-worker thread pool. Local files hold videos, frames, embeddings and exports. Sprint 3 resubmits queued jobs after restart, quarantines interrupted running jobs, removes their partial generated artifacts and preserves reviewed events.

This remains unsuitable for multi-user production. A host crash can interrupt work; SQLite cannot coordinate a worker fleet; local media lacks independent durability; and observability is process-local.

## Controlled migration

1. Introduce Alembic migrations and PostgreSQL while retaining the modular monolith.
2. Move uploads/frames/exports to encrypted S3-compatible object storage with tenant-prefixed keys and signed short-lived access.
3. Replace the thread pool with a durable queue supporting leases, heartbeats, retries, idempotency keys and dead-letter inspection.
4. Run GPU inference in separately scalable workers using the same detector adapter contract.
5. Add OpenTelemetry traces, structured security/audit events, metrics and alerting.
6. Add organization/site ownership to every sensitive entity before any multi-customer pilot.

Do not split into additional services until scaling, isolation or deployment ownership requires it. The FastAPI application can remain the control-plane modular monolith through an initial pilot.
