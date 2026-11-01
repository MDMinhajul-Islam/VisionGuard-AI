# Sprint 5A Verification

## Results

- Existing deterministic backend: 67 passed, 3 skipped, 9 deselected.
- Direct PostgreSQL RLS and authenticated API: 9 passed, including explicit least-privilege grant assertions.
- Real CLIP, SSDlite, and MediaPipe integration tests: 3 passed.
- Chromium on the PostgreSQL-backed API: 4 passed.
- Frontend production build passed; lint had no errors and six existing image-optimization warnings.
- Dependency audit found no high-severity issue. Sixteen moderate transitive development-tool findings remain because the proposed forced fix is a breaking ESLint downgrade.

All 31 research videos remain in the restricted Legacy Research Workspace. Chromium opened imported video, loaded evidence diagnostics, displayed preserved metrics, and exercised logout revocation. Commercial-candidate policy gates remain active.

## Local measurements

| Operation | Median | p95 | Max |
|---|---:|---:|---:|
| New PostgreSQL connection | 61.94 ms | 78.46 ms | 79.60 ms |
| Tenant video-count query | 1.09 ms | 1.24 ms | 3.65 ms |
| Recent job metadata query | 1.17 ms | 1.86 ms | 3.50 ms |
| Authenticated overview API | 46.64 ms | 51.56 ms | 58.48 ms |

Migration took 1.72 seconds; safe rerun 0.59 seconds; backup 1.64 seconds; restore 4.54 seconds. These small localhost measurements are not production scalability evidence.

Remaining limitations: the queue is in-process, rate limiting is process-local, audit storage is not externally immutable, backups lack PITR, and filesystem media is not replicated or encrypted by this sprint. Production still needs secret management, TLS, monitored backups, media recovery, a durable queue, and an externally anchored audit sink.
