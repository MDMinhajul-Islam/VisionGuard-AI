# Tenant Context

The backend does not trust `X-Organization-ID` or `X-Site-ID` as authorization proof. Python first verifies active membership, role, organization/site status, and site grant.

PostgreSQL context is stored in `visionguard_context.transaction_context`, keyed by `pg_backend_pid()` and `txid_current()`. The application role cannot access it directly. Security-definer setters validate canonical records; policy helpers expose only current actor, organization, and the site predicate.

Transaction identity prevents context from surviving commit, rollback, exception, or pooled connection reuse. Tests exercise all of those paths with a one-connection pool alternating tenants.

Media requests without custom headers use `set_object_context(user, kind, id)`, which derives the parent video and validates access. Workers use `set_job_context(job_id)`, deriving scope from `processing_jobs → videos`; queue-supplied tenant IDs are never accepted.

`users` and `auth_sessions` are outside tenant RLS because authentication precedes tenant selection. They are available only through the backend database role and remain protected by API security controls.
