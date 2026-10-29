# Model and Product Release Gates

No experiment is promoted automatically.

## Product pilot gate

- Independent threat model and penetration test completed.
- SSO/MFA, tenant/site authorization and immutable audit logs implemented.
- Rate limiting, session revocation and account recovery implemented.
- Encryption at rest/in transit, retention, deletion, backup and restore tested.
- PostgreSQL migrations and durable workers pass crash/retry/idempotency tests.
- Privacy impact assessment and customer data-processing terms approved.

## Detector commercial-candidate gate

- Code, weights and training/evaluation data cleared for the intended commercial distribution.
- Checkpoint hash, complete configuration and reproducible build recorded.
- Industrial classes have written labeling rules and a versioned commercial dataset.
- Camera/site/organization-disjoint evaluation completed with per-class metrics and failures.
- Latency, memory, false-alert rate and stability meet documented target-hardware limits.

## Released-model gate

- Locked held-out evaluation report approved by ML, product safety, security and legal owners.
- Regression comparison against the currently released detector completed.
- Rollback artifact and compatibility tests verified.
- Human approver recorded in the release registry.
- Safety language remains candidate/review-required; no automated disciplinary outcome is introduced.
