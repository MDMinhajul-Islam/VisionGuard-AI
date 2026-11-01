from __future__ import annotations

import re

from sqlalchemy import text


DIRECT_TENANT_TABLES = {
    "organizations", "sites", "organization_memberships", "site_access", "videos", "audit_events",
}
VIDEO_CHILD_TABLES = {
    "processing_jobs", "video_frames", "object_detections", "pose_evidence", "safety_zones",
    "candidate_events", "embedding_caches", "exported_clips", "validation_annotations", "dataset_assets",
}
RLS_TABLES = DIRECT_TENANT_TABLES | VIDEO_CHILD_TABLES
SECURITY_TABLES = {"users", "auth_sessions"}
APP_TABLE_GRANTS = {
    "users": "SELECT, INSERT, UPDATE",
    "auth_sessions": "SELECT, INSERT, UPDATE, DELETE",
    "organizations": "SELECT, INSERT, UPDATE",
    "sites": "SELECT, INSERT, UPDATE",
    "organization_memberships": "SELECT, INSERT, UPDATE, DELETE",
    "site_access": "SELECT, INSERT, UPDATE, DELETE",
    "videos": "SELECT, INSERT, UPDATE, DELETE",
    "audit_events": "SELECT, INSERT",
    **{table: "SELECT, INSERT, UPDATE, DELETE" for table in VIDEO_CHILD_TABLES},
}


def _role_identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
        raise ValueError("invalid PostgreSQL role identifier")
    return value


CONTEXT_SQL = r"""
CREATE SCHEMA IF NOT EXISTS visionguard_context;
REVOKE ALL ON SCHEMA visionguard_context FROM PUBLIC;

CREATE TABLE IF NOT EXISTS visionguard_context.transaction_context (
    backend_pid integer NOT NULL,
    transaction_id bigint NOT NULL,
    actor_id varchar(36),
    organization_id varchar(36),
    site_ids text[] NOT NULL DEFAULT ARRAY[]::text[],
    established_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (backend_pid, transaction_id)
);
REVOKE ALL ON visionguard_context.transaction_context FROM PUBLIC;

CREATE OR REPLACE FUNCTION visionguard_context.actor_id() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, visionguard_context
AS $$ SELECT actor_id FROM transaction_context WHERE backend_pid = pg_backend_pid() AND transaction_id = txid_current() $$;

CREATE OR REPLACE FUNCTION visionguard_context.organization_id() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, visionguard_context
AS $$ SELECT organization_id FROM transaction_context WHERE backend_pid = pg_backend_pid() AND transaction_id = txid_current() $$;

CREATE OR REPLACE FUNCTION visionguard_context.site_allowed(site_id text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, visionguard_context
AS $$ SELECT site_id = ANY(COALESCE((SELECT tc.site_ids FROM transaction_context tc WHERE tc.backend_pid = pg_backend_pid() AND tc.transaction_id = txid_current()), ARRAY[]::text[])) $$;

CREATE OR REPLACE FUNCTION visionguard_context.set_actor_context(p_user_id text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, visionguard_context
AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id = p_user_id AND disabled = false) THEN
        RAISE EXCEPTION 'invalid actor context' USING ERRCODE = '42501';
    END IF;
    DELETE FROM transaction_context WHERE backend_pid = pg_backend_pid();
    INSERT INTO transaction_context(backend_pid, transaction_id, actor_id)
    VALUES (pg_backend_pid(), txid_current(), p_user_id);
END $$;

CREATE OR REPLACE FUNCTION visionguard_context.set_tenant_context(
    p_user_id text, p_organization_id text, p_site_ids text[]
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, visionguard_context
AS $$
DECLARE membership_role text;
BEGIN
    SELECT role INTO membership_role FROM public.organization_memberships
      WHERE user_id = p_user_id AND organization_id = p_organization_id AND status = 'active';
    IF membership_role IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.organizations WHERE id = p_organization_id AND status NOT IN ('disabled', 'suspended')
    ) THEN RAISE EXCEPTION 'unauthorized tenant context' USING ERRCODE = '42501'; END IF;
    IF coalesce(array_length(p_site_ids, 1), 0) = 0 THEN
        RAISE EXCEPTION 'at least one site is required' USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM unnest(p_site_ids) requested(site_id)
        LEFT JOIN public.sites s ON s.id = requested.site_id AND s.organization_id = p_organization_id
        WHERE s.id IS NULL OR s.status IN ('disabled', 'suspended') OR (
            membership_role <> 'organization_admin' AND NOT EXISTS (
                SELECT 1 FROM public.site_access sa
                JOIN public.organization_memberships om ON om.id = sa.membership_id
                WHERE om.user_id = p_user_id AND om.organization_id = p_organization_id
                  AND om.status = 'active' AND sa.site_id = requested.site_id
            )
        )
    ) THEN RAISE EXCEPTION 'unauthorized site context' USING ERRCODE = '42501'; END IF;
    DELETE FROM transaction_context WHERE backend_pid = pg_backend_pid();
    INSERT INTO transaction_context(backend_pid, transaction_id, actor_id, organization_id, site_ids)
    VALUES (pg_backend_pid(), txid_current(), p_user_id, p_organization_id, p_site_ids);
END $$;

CREATE OR REPLACE FUNCTION visionguard_context.set_object_context(
    p_user_id text, p_object_kind text, p_object_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, visionguard_context
AS $$
DECLARE v_org text; v_site text;
BEGIN
    IF p_object_kind = 'video' THEN
        SELECT organization_id, site_id INTO v_org, v_site FROM public.videos WHERE id = p_object_id;
    ELSIF p_object_kind = 'frame' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.video_frames x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSIF p_object_kind = 'event' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.candidate_events x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSIF p_object_kind = 'job' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.processing_jobs x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSIF p_object_kind = 'export' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.exported_clips x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSIF p_object_kind = 'dataset_asset' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.dataset_assets x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSIF p_object_kind = 'annotation' THEN
        SELECT v.organization_id, v.site_id INTO v_org, v_site FROM public.validation_annotations x JOIN public.videos v ON v.id=x.video_id WHERE x.id=p_object_id;
    ELSE RAISE EXCEPTION 'unsupported object context'; END IF;
    IF v_org IS NULL THEN RAISE EXCEPTION 'object unavailable' USING ERRCODE = '42501'; END IF;
    PERFORM visionguard_context.set_tenant_context(p_user_id, v_org, ARRAY[v_site]);
END $$;

CREATE OR REPLACE FUNCTION visionguard_context.set_job_context(p_job_id text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, visionguard_context
AS $$
DECLARE v_org text; v_site text;
BEGIN
    SELECT v.organization_id, v.site_id INTO v_org, v_site
      FROM public.processing_jobs j JOIN public.videos v ON v.id=j.video_id
      WHERE j.id=p_job_id;
    IF v_org IS NULL THEN RAISE EXCEPTION 'job unavailable' USING ERRCODE = '42501'; END IF;
    DELETE FROM transaction_context WHERE backend_pid = pg_backend_pid();
    INSERT INTO transaction_context(backend_pid, transaction_id, organization_id, site_ids)
    VALUES (pg_backend_pid(), txid_current(), v_org, ARRAY[v_site]);
END $$;

CREATE OR REPLACE FUNCTION visionguard_context.recoverable_job_ids() RETURNS TABLE(job_id text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$ SELECT id::text FROM public.processing_jobs WHERE status IN ('queued','running') $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA visionguard_context FROM PUBLIC;
"""


def install_postgres_security(connection, app_role: str) -> None:
    role = _role_identifier(app_role)
    connection.execute(text(CONTEXT_SQL))
    connection.execute(text(f"GRANT USAGE ON SCHEMA visionguard_context TO {role}"))
    for function in (
        "actor_id()", "organization_id()", "site_allowed(text)",
        "set_actor_context(text)", "set_tenant_context(text,text,text[])",
        "set_object_context(text,text,text)", "set_job_context(text)", "recoverable_job_ids()",
    ):
        connection.execute(text(f"GRANT EXECUTE ON FUNCTION visionguard_context.{function} TO {role}"))
    # Never let a newly added table silently become application-accessible. Each
    # table must be reviewed here and remains subject to its RLS policy below.
    connection.execute(text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}"))
    connection.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {role}"))
    for table, privileges in sorted(APP_TABLE_GRANTS.items()):
        connection.execute(text(f"GRANT {privileges} ON TABLE public.{table} TO {role}"))

    direct = {
        "videos": "organization_id = visionguard_context.organization_id() AND visionguard_context.site_allowed(site_id)",
    }
    for table, predicate in direct.items():
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        connection.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        connection.execute(text(f"CREATE POLICY tenant_isolation ON {table} FOR ALL TO {role} USING ({predicate}) WITH CHECK ({predicate})"))

    for table in ("organizations", "sites", "organization_memberships", "site_access"):
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        for policy in ("tenant_isolation", "actor_read", "tenant_write", "platform_insert"):
            connection.execute(text(f"DROP POLICY IF EXISTS {policy} ON {table}"))
    connection.execute(text(f"CREATE POLICY actor_read ON organizations FOR SELECT TO {role} USING (id=visionguard_context.organization_id() OR EXISTS (SELECT 1 FROM organization_memberships m WHERE m.organization_id=organizations.id AND m.user_id=visionguard_context.actor_id() AND m.status='active'))"))
    connection.execute(text(f"CREATE POLICY platform_insert ON organizations FOR INSERT TO {role} WITH CHECK (EXISTS (SELECT 1 FROM users u WHERE u.id=visionguard_context.actor_id() AND u.role='admin' AND u.disabled=false))"))
    connection.execute(text(f"CREATE POLICY tenant_write ON organizations FOR UPDATE TO {role} USING (id=visionguard_context.organization_id()) WITH CHECK (id=visionguard_context.organization_id())"))
    connection.execute(text(f"CREATE POLICY actor_read ON organization_memberships FOR SELECT TO {role} USING (user_id=visionguard_context.actor_id() OR organization_id=visionguard_context.organization_id())"))
    connection.execute(text(f"CREATE POLICY tenant_write ON organization_memberships FOR ALL TO {role} USING (organization_id=visionguard_context.organization_id()) WITH CHECK (organization_id=visionguard_context.organization_id())"))
    connection.execute(text(f"CREATE POLICY actor_read ON sites FOR SELECT TO {role} USING ((organization_id=visionguard_context.organization_id() AND visionguard_context.site_allowed(id)) OR EXISTS (SELECT 1 FROM organization_memberships m WHERE m.organization_id=sites.organization_id AND m.user_id=visionguard_context.actor_id() AND m.status='active' AND (m.role='organization_admin' OR EXISTS (SELECT 1 FROM site_access a WHERE a.membership_id=m.id AND a.site_id=sites.id))))"))
    connection.execute(text(f"CREATE POLICY tenant_write ON sites FOR ALL TO {role} USING (organization_id=visionguard_context.organization_id()) WITH CHECK (organization_id=visionguard_context.organization_id())"))
    connection.execute(text(f"CREATE POLICY actor_read ON site_access FOR SELECT TO {role} USING (EXISTS (SELECT 1 FROM organization_memberships m WHERE m.id=membership_id AND (m.user_id=visionguard_context.actor_id() OR m.organization_id=visionguard_context.organization_id())))"))
    connection.execute(text(f"CREATE POLICY tenant_write ON site_access FOR ALL TO {role} USING (EXISTS (SELECT 1 FROM organization_memberships m WHERE m.id=membership_id AND m.organization_id=visionguard_context.organization_id())) WITH CHECK (EXISTS (SELECT 1 FROM organization_memberships m WHERE m.id=membership_id AND m.organization_id=visionguard_context.organization_id()) AND visionguard_context.site_allowed(site_id))"))

    for table in sorted(VIDEO_CHILD_TABLES):
        predicate = f"EXISTS (SELECT 1 FROM videos tenant_video WHERE tenant_video.id = {table}.video_id)"
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        connection.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        connection.execute(text(f"CREATE POLICY tenant_isolation ON {table} FOR ALL TO {role} USING ({predicate}) WITH CHECK ({predicate})"))

    connection.execute(text("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY"))
    connection.execute(text("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY"))
    connection.execute(text("DROP POLICY IF EXISTS tenant_audit_select ON audit_events"))
    connection.execute(text("DROP POLICY IF EXISTS tenant_audit_insert ON audit_events"))
    connection.execute(text(f"CREATE POLICY tenant_audit_select ON audit_events FOR SELECT TO {role} USING (organization_id = visionguard_context.organization_id())"))
    connection.execute(text(f"CREATE POLICY tenant_audit_insert ON audit_events FOR INSERT TO {role} WITH CHECK (organization_id IS NULL OR organization_id = visionguard_context.organization_id())"))
