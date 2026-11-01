from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.security import hash_password
from app.main import app


pytestmark = pytest.mark.postgres


def test_postgresql_login_tenant_api_and_revocation():
    migration_url = os.environ.get("VISIONGUARD_TEST_MIGRATION_DATABASE_URL")
    if not migration_url:
        pytest.skip("PostgreSQL migration URL is not configured")
    migration = create_engine(migration_url)
    suffix = uuid4().hex[:10]
    user_id, org_a, org_b, site_a, site_b = [f"{suffix}-{name}" for name in ("user", "org-a", "org-b", "site-a", "site-b")]
    membership = f"{suffix}-membership"
    video_a, video_b = f"{suffix}-video-a", f"{suffix}-video-b"
    email = f"api-{suffix}@test.invalid"
    password = "postgres-api-test-password-123!"
    with migration.begin() as connection:
        connection.execute(text("INSERT INTO users(id,email,display_name,password_hash,role,disabled,session_version,created_at) VALUES (:id,:email,'Postgres API',:password_hash,'reviewer',false,0,'2026-10-31')"), {"id": user_id, "email": email, "password_hash": hash_password(password)})
        connection.execute(text("INSERT INTO organizations(id,name,status,workspace_type,created_at) VALUES (:a,:na,'active','commercial_candidate','2026-10-31'),(:b,:nb,'active','commercial_candidate','2026-10-31')"), {"a": org_a, "b": org_b, "na": f"API A {suffix}", "nb": f"API B {suffix}"})
        connection.execute(text("INSERT INTO sites(id,organization_id,name,status,created_at) VALUES (:a,:oa,'A','active','2026-10-31'),(:b,:ob,'B','active','2026-10-31')"), {"a": site_a, "oa": org_a, "b": site_b, "ob": org_b})
        connection.execute(text("INSERT INTO organization_memberships(id,user_id,organization_id,role,status,created_at) VALUES (:id,:user,:org,'organization_admin','active','2026-10-31')"), {"id": membership, "user": user_id, "org": org_a})
        connection.execute(text("INSERT INTO videos(id,organization_id,site_id,original_filename,stored_filename,path,mime_type,size_bytes,status,is_demo,created_at) VALUES (:va,:oa,:sa,'a.mp4',:sta,'/a','video/mp4',1,'uploaded',false,'2026-10-31'),(:vb,:ob,:sb,'b.mp4',:stb,'/b','video/mp4',1,'uploaded',false,'2026-10-31')"), {"va": video_a, "oa": org_a, "sa": site_a, "sta": f"{suffix}-a.mp4", "vb": video_b, "ob": org_b, "sb": site_b, "stb": f"{suffix}-b.mp4"})
    try:
        with TestClient(app) as client:
            login = client.post("/api/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200
            organizations = client.get("/api/organizations")
            assert organizations.status_code == 200
            assert [item["id"] for item in organizations.json()] == [org_a]
            headers = {"X-Organization-ID": org_a, "X-Site-ID": site_a}
            videos = client.get("/api/videos", headers=headers)
            assert videos.status_code == 200
            assert [item["id"] for item in videos.json()] == [video_a]
            assert client.get(f"/api/videos/{video_a}").status_code == 200
            assert client.get(f"/api/videos/{video_b}").status_code == 404
            logout = client.post("/api/auth/logout", headers={"Origin": "http://127.0.0.1:3000"})
            assert logout.status_code == 204
            assert client.get("/api/organizations").status_code == 401
    finally:
        with migration.begin() as connection:
            connection.execute(text("DELETE FROM auth_sessions WHERE user_id=:user"), {"user": user_id})
            for table, identifiers in (("videos", [video_a, video_b]), ("organization_memberships", [membership]), ("sites", [site_a, site_b]), ("organizations", [org_a, org_b]), ("users", [user_id])):
                connection.execute(text(f"DELETE FROM {table} WHERE id = ANY(CAST(:ids AS text[]))"), {"ids": identifiers})
        migration.dispose()
