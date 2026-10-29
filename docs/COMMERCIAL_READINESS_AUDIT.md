# Commercial Readiness Audit — Sprint 3

VisionGuard is **not production-ready or safety-certified**. Sprint 3 establishes a controlled-pilot engineering foundation and closes the most direct local data-exposure paths.

## Scorecard

| Area | Score | Evidence | Principal blocker |
|---|---:|---|---|
| Authentication / RBAC | 65/100 | Argon2, signed HttpOnly session, admin/reviewer roles, API tests | no SSO, MFA, revocation store, or rate limiting |
| Video/evidence security | 60/100 | all `/api/*` data routes deny unauthenticated requests; media and exports included | no tenant/site ownership model or encryption-at-rest key management |
| Model governance | 55/100 | normalized adapter contract, checkpoint hashes, research/commercial flags | training-data and checkpoint legal review incomplete |
| Evaluation rigor | 50/100 | fixed protocol, p50/p95, hardware and source hashes | five frames and no bounding-box ground truth |
| Processing reliability | 45/100 | interrupted-job quarantine, queued resubmission, reviewed-event preservation | single-process executor and SQLite remain |
| Operations | 25/100 | structured local logs and reproducible setup | no centralized audit log, metrics, alerting, backups, or disaster recovery |
| Overall controlled-pilot readiness | **48/100** | substantial local foundation | P1 items below remain mandatory |

## Findings and disposition

### P0 — addressed in Sprint 3

- **Unauthenticated API and direct media access.** Previously every video, frame, evidence and export route was callable directly. A deny-by-default middleware now protects all `/api/*` routes except health and login; automated tests cover direct media, frame, export and dataset denial.
- **No application identities or roles.** Added persisted users, Argon2id password hashes, signed expiring sessions, and admin/reviewer permissions.
- **Reviewed evidence deletion during reprocessing.** Processing previously deleted all non-synthetic events. It now deletes only pending model events and preserves human-reviewed records.

### P1 — partially addressed / still blocking a customer pilot

- No organization, site, or video-level ownership boundary. Every authenticated user can read all records.
- No enterprise SSO, MFA, session revocation, credential recovery, login rate limiting, or account lockout.
- No immutable audit trail for login, review, export, administration, and model execution.
- SQLite and the in-process executor cannot provide multi-host durability or high availability.
- Uploaded videos and exports are not application-encrypted at rest.
- Detector checkpoint and training-data commercial clearance is incomplete; YOLO26 is benchmark-only without an appropriate Ultralytics license.
- No malware scanning/content disarm or full media parser sandbox.

### P2 — required before scale

- PostgreSQL migrations, durable queue, object storage, isolated GPU workers, idempotency keys, quotas, backups, telemetry and alerting.
- Signed short-lived object URLs, retention policies, legal hold, deletion workflows and customer-managed encryption keys.
- Dependency/SBOM scanning, container hardening and repeatable deployment artifacts.

### P3 — future

- Hardware fleet scheduling, active learning, model drift monitoring, site-specific calibration, and multi-region operation.

## Security implementation

Sessions use HS256 with issuer/audience validation, expiration, unique token IDs and a secret supplied through `VISIONGUARD_AUTH_SECRET`. Production/pilot mode refuses to start token operations without that secret. The browser receives the token only through an HttpOnly, SameSite=Strict cookie. CLI workflows may use a bearer token or environment-supplied credentials. CORS is restricted to configured local origins and credentials are explicitly enabled.

This is a secure foundation, not a completed security program. Obtain an independent threat model, penetration test, privacy review and legal review before a controlled customer pilot.
