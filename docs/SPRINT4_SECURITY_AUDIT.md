# Sprint 4 Security Audit

VisionGuard remains a local engineering prototype, not a production-certified safety system.

| Priority | Confirmed finding | Sprint 4 disposition |
|---|---|---|
| P0 | Any authenticated user could enumerate and access every video and descendant object | Fixed with memberships, site grants, scoped queries, and object authorization |
| P0 | Direct frame, event, job, export, and dataset identifiers bypassed tenant boundaries | Fixed by resolving nested objects through their owning video |
| P1 | Logout only removed the browser cookie | Fixed with persisted server-side session revocation |
| P1 | Role or disabled-account changes did not reliably invalidate active authorization | Role and session-version checks run on every request |
| P1 | Cookie mutations had no explicit CSRF control | Cookie mutations require an allowed Origin; bearer CLI calls are exempt |
| P1 | Unlimited login attempts and user-timing differences | Added bounded rate limiting, dummy-hash verification, and uniform failures |
| P1 | No structured security/business audit trail | Added scoped audit records for authentication, administration, media, reviews, processing, and exports |
| P1 | Research-only models/data could activate in commercial workspaces | CLIP/search and dataset registration are rejected outside research workspaces |

Remaining blockers include SSO/MFA, distributed rate limiting, centralized policy enforcement, malware scanning, encryption-at-rest key management, PostgreSQL defense in depth, durable workers, secrets management, independent penetration testing, and tamper-evident audit storage.
