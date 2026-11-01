# Row-Level Security

RLS is enabled and forced on 16 tables: `organizations`, `sites`, `organization_memberships`, `site_access`, `videos`, `audit_events`, `processing_jobs`, `video_frames`, `object_detections`, `pose_evidence`, `safety_zones`, `candidate_events`, `embedding_caches`, `exported_clips`, `validation_annotations`, and `dataset_assets`.

Video descendants resolve ownership through the visible parent video. Root policies require protected transaction organization/site context. Audit SELECT is organization-scoped; INSERT permits a matching organization or a null organization for authentication failures. No ordinary audit UPDATE/DELETE policy exists.

Policies use `USING` and `WITH CHECK` for SELECT/INSERT/UPDATE/DELETE. The schema-coverage test fails if any declared table lacks both `relrowsecurity` and `relforcerowsecurity`. Direct application-role tests prove missing context returns zero rows, cross-tenant SELECT/UPDATE/DELETE affect zero rows, cross-tenant INSERT fails, unauthorized site and forged organization contexts fail, and the application role is neither superuser nor BYPASSRLS.

RLS is defense in depth. Migration and cluster credentials remain privileged and require separate operational protection and audit controls.
