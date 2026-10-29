# Audit Logging

`AuditEvent` stores actor, organization, object type/ID, action, outcome, UTC timestamp, correlation request ID, and bounded JSON metadata. Current events include authentication success/failure/rate limiting/logout/password change, user/organization/site/membership administration, upload, media access, processing creation/cancellation, review changes, and evidence export.

Passwords, cookies, bearer tokens, source frames, and video content are never audit metadata. No audit update/delete API exists. Organization administrators can read only their organization’s records.

SQLite owner/process access can still alter rows, so this is not immutable. A pilot needs append-only remote ingestion, restricted operator access, retention controls, backup verification, and tamper-evident or WORM storage.
