# Tenant Isolation

The implemented ownership chain is `Organization → Site → Video → jobs/frames/detections/pose/events/zones/annotations/embeddings/exports/dataset assets`.

Videos store organization and site identifiers. Descendant ownership is resolved through the video foreign key; clients cannot override it. Collection queries use an authorized-video subquery. Direct object routes return the same `404` response for missing and unauthorized identifiers to reduce enumeration.

Membership roles are `organization_admin`, `site_admin`, `safety_reviewer`, and `read_only_auditor`. Organization administrators see all sites in their organization. Other roles require an explicit `SiteAccess` row. Browser organization/site headers are selection hints only and are validated before upload.

## Legacy migration and rollback

Existing videos are migrated non-destructively into deterministic `Legacy Research Workspace` and `Legacy Imported Data` records. Video IDs and descendants remain unchanged. No user membership is created. Grant access explicitly with `scripts/manage_tenant.py`.

Before migration, stop workers and copy `runtime/visionguard.db`. Startup migrations are idempotent and fail if any video remains unscoped. Rollback means stopping the new application and restoring that copy; do not attempt ad-hoc SQLite column removal.
