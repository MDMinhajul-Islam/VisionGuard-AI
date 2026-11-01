from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.database.postgres_security import RLS_TABLES


pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def databases():
    migration_url = os.environ.get("VISIONGUARD_TEST_MIGRATION_DATABASE_URL")
    app_url = os.environ.get("VISIONGUARD_TEST_APP_DATABASE_URL")
    if not migration_url or not app_url:
        pytest.skip("PostgreSQL test URLs are not configured")
    migration = create_engine(migration_url, pool_pre_ping=True)
    application = create_engine(app_url, pool_size=1, max_overflow=0, pool_pre_ping=True)
    prefix = uuid4().hex[:10]
    ids = {name: f"{prefix}-{name}" for name in (
        "user_a", "user_b", "reviewer", "org_a", "org_b", "site_a", "site_a2", "site_b",
        "membership_a", "membership_b", "membership_r", "grant_r", "video_a", "video_a2", "video_b",
        "job_a", "job_b", "event_a", "event_b", "frame_a", "frame_b",
    )}
    with migration.begin() as connection:
        connection.execute(text("INSERT INTO users(id,email,display_name,password_hash,role,disabled,session_version,created_at) VALUES (:user_a,:email_a,'A','hash','reviewer',false,0,'2026-10-31T00:00:00+00:00'),(:user_b,:email_b,'B','hash','reviewer',false,0,'2026-10-31T00:00:00+00:00'),(:reviewer,:email_r,'R','hash','reviewer',false,0,'2026-10-31T00:00:00+00:00')"), {**ids, "email_a": f"a-{prefix}@test.invalid", "email_b": f"b-{prefix}@test.invalid", "email_r": f"r-{prefix}@test.invalid"})
        connection.execute(text("INSERT INTO organizations(id,name,status,workspace_type,created_at) VALUES (:org_a,:name_a,'active','commercial_candidate','2026-10-31'),(:org_b,:name_b,'active','commercial_candidate','2026-10-31')"), {**ids, "name_a": f"RLS A {prefix}", "name_b": f"RLS B {prefix}"})
        connection.execute(text("INSERT INTO sites(id,organization_id,name,status,created_at) VALUES (:site_a,:org_a,'A1','active','2026-10-31'),(:site_a2,:org_a,'A2','active','2026-10-31'),(:site_b,:org_b,'B1','active','2026-10-31')"), ids)
        connection.execute(text("INSERT INTO organization_memberships(id,user_id,organization_id,role,status,created_at) VALUES (:membership_a,:user_a,:org_a,'organization_admin','active','2026-10-31'),(:membership_b,:user_b,:org_b,'organization_admin','active','2026-10-31'),(:membership_r,:reviewer,:org_a,'safety_reviewer','active','2026-10-31')"), ids)
        connection.execute(text("INSERT INTO site_access(id,membership_id,site_id,created_at) VALUES (:grant_r,:membership_r,:site_a,'2026-10-31')"), ids)
        connection.execute(text("INSERT INTO videos(id,organization_id,site_id,original_filename,stored_filename,path,mime_type,size_bytes,status,is_demo,created_at) VALUES (:video_a,:org_a,:site_a,'a.mp4',:stored_a,'/a','video/mp4',1,'uploaded',false,'2026-10-31'),(:video_a2,:org_a,:site_a2,'a2.mp4',:stored_a2,'/a2','video/mp4',1,'uploaded',false,'2026-10-31'),(:video_b,:org_b,:site_b,'b.mp4',:stored_b,'/b','video/mp4',1,'uploaded',false,'2026-10-31')"), {**ids, "stored_a": f"{prefix}-a.mp4", "stored_a2": f"{prefix}-a2.mp4", "stored_b": f"{prefix}-b.mp4"})
        connection.execute(text("INSERT INTO processing_jobs(id,video_id,status,progress,stage,config_json,metrics_json,cancel_requested,created_at) VALUES (:job_a,:video_a,'queued',0,'queued','{}','{}',false,'2026-10-31'),(:job_b,:video_b,'queued',0,'queued','{}','{}',false,'2026-10-31')"), ids)
        connection.execute(text("INSERT INTO video_frames(id,video_id,timestamp_seconds,frame_number,path,width,height,clip_indexed) VALUES (:frame_a,:video_a,0,0,'/fa',1,1,false),(:frame_b,:video_b,0,0,'/fb',1,1,false)"), ids)
        connection.execute(text("INSERT INTO candidate_events(id,video_id,event_type,label,start_seconds,end_seconds,processing_method,model_version,raw_scores_json,thresholds_json,supporting_frames_json,review_status,reviewer_note,synthetic_fixture,created_at) VALUES (:event_a,:video_a,'potential_fall','A',0,1,'test','test','{}','{}','[]','pending','',false,'2026-10-31'),(:event_b,:video_b,'potential_fall','B',0,1,'test','test','{}','{}','[]','pending','',false,'2026-10-31')"), ids)
    yield migration, application, ids
    with migration.begin() as connection:
        for table in ("candidate_events", "video_frames", "processing_jobs", "videos", "site_access", "organization_memberships", "sites", "organizations", "users"):
            connection.execute(text(f"DELETE FROM {table} WHERE id LIKE :prefix"), {"prefix": f"{prefix}-%"})
    application.dispose()
    migration.dispose()


def set_tenant(connection, ids, user="user_a", org="org_a", sites=("site_a",)):
    connection.execute(text("SELECT visionguard_context.set_tenant_context(:user_id,:org_id,CAST(:sites AS text[]))"), {"user_id": ids[user], "org_id": ids[org], "sites": [ids[site] for site in sites]})


def test_role_is_least_privileged(databases):
    migration, _, _ = databases
    with migration.connect() as connection:
        role = connection.execute(text("SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname='visionguard_app'")) .one()
    assert tuple(role) == (False, False, False, False)


def test_table_grants_are_explicit_and_minimal(databases):
    migration, _, _ = databases
    with migration.connect() as connection:
        can_delete_user = connection.scalar(text("SELECT has_table_privilege('visionguard_app','users','DELETE')"))
        can_update_audit = connection.scalar(text("SELECT has_table_privilege('visionguard_app','audit_events','UPDATE')"))
        can_delete_video = connection.scalar(text("SELECT has_table_privilege('visionguard_app','videos','DELETE')"))
        can_insert_audit = connection.scalar(text("SELECT has_table_privilege('visionguard_app','audit_events','INSERT')"))
        can_read_context = connection.scalar(text("SELECT has_table_privilege('visionguard_app','visionguard_context.transaction_context','SELECT')"))
    assert can_delete_user is False
    assert can_update_audit is False
    assert can_delete_video is True
    assert can_insert_audit is True
    assert can_read_context is False


def test_missing_context_fails_closed(databases):
    _, application, _ = databases
    with application.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM videos")) == 0
        assert connection.scalar(text("SELECT count(*) FROM candidate_events")) == 0


def test_cross_tenant_select_insert_update_delete_are_denied(databases):
    _, application, ids = databases
    with application.begin() as connection:
        set_tenant(connection, ids)
        assert connection.scalars(text("SELECT original_filename FROM videos ORDER BY original_filename")).all() == ["a.mp4"]
        assert connection.execute(text("UPDATE videos SET status='failed' WHERE id=:id"), {"id": ids["video_b"]}).rowcount == 0
        assert connection.execute(text("DELETE FROM candidate_events WHERE id=:id"), {"id": ids["event_b"]}).rowcount == 0
    with pytest.raises(DBAPIError):
        with application.begin() as connection:
            set_tenant(connection, ids)
            connection.execute(text("INSERT INTO videos(id,organization_id,site_id,original_filename,stored_filename,path,mime_type,size_bytes,status,is_demo,created_at) VALUES (:id,:org,:site,'x.mp4',:stored,'/x','video/mp4',1,'uploaded',false,'2026-10-31')"), {"id": f"{ids['video_b']}-x", "org": ids["org_b"], "site": ids["site_b"], "stored": f"{ids['video_b']}-x.mp4"})


def test_forged_tenant_and_unauthorized_site_context_are_rejected(databases):
    _, application, ids = databases
    with application.connect() as connection:
        with pytest.raises(DBAPIError):
            with connection.begin():
                set_tenant(connection, ids, user="user_a", org="org_b", sites=("site_b",))
        with pytest.raises(DBAPIError):
            with connection.begin():
                set_tenant(connection, ids, user="reviewer", org="org_a", sites=("site_a2",))
        with connection.begin():
            set_tenant(connection, ids, user="reviewer", org="org_a", sites=("site_a",))
            assert connection.scalars(text("SELECT id FROM videos")).all() == [ids["video_a"]]


def test_pool_context_does_not_survive_commit_or_rollback(databases):
    _, application, ids = databases
    with application.begin() as connection:
        set_tenant(connection, ids)
        assert connection.scalar(text("SELECT count(*) FROM videos")) == 1
    with application.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM videos")) == 0
        connection.rollback()
        with pytest.raises(RuntimeError):
            with connection.begin():
                set_tenant(connection, ids, user="user_b", org="org_b", sites=("site_b",))
                assert connection.scalar(text("SELECT count(*) FROM videos")) == 1
                raise RuntimeError("force rollback")
    with application.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM videos")) == 0


def test_worker_context_is_derived_from_job_relationship(databases):
    _, application, ids = databases
    with application.begin() as connection:
        connection.execute(text("SELECT visionguard_context.set_job_context(:job_id)"), {"job_id": ids["job_b"]})
        assert connection.scalars(text("SELECT id FROM videos")).all() == [ids["video_b"]]


def test_all_declared_tenant_tables_have_forced_rls(databases):
    migration, _, _ = databases
    with migration.connect() as connection:
        rows = connection.execute(text("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY(CAST(:tables AS text[]))"), {"tables": sorted(RLS_TABLES)}).all()
        coverage = {name: (enabled, forced) for name, enabled, forced in rows}
    assert set(coverage) == RLS_TABLES
    assert all(enabled and forced for enabled, forced in coverage.values())
