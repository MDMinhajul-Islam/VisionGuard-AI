# Production Security Gates

Sprint 4 does not make VisionGuard production-ready. Before a controlled pilot:

- Complete an independent threat model, penetration test, privacy assessment, and legal review.
- Add enterprise SSO, MFA, recovery, distributed rate limiting, and session administration.
- Move to PostgreSQL with tested tenant constraints and row-level defense in depth.
- Add durable idempotent workers, object storage, encryption/key rotation, backups, restore exercises, metrics, and alerting.
- Forward audit events to append-only storage with retention and tamper-evidence controls.
- Add malware scanning and sandboxed media parsing.
- Implement per-tenant quotas, retention, deletion, export approval, and incident response.
- Clear model code, weights, training/evaluation data, and FFmpeg distribution commercially.
- Require locked industrial evaluations and human approval for every released model.

CLIP and non-commercial UR data remain research-only. Experimental fall candidates require human review and cannot trigger unattended disciplinary or safety-critical action.
