from __future__ import annotations

import argparse
import json
import os
import statistics
import time

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


def summary(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "iterations": len(values), "median_ms": statistics.median(values),
        "p95_ms": ordered[max(0, int(len(ordered) * 0.95) - 1)], "max_ms": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Small local PostgreSQL/API benchmark; not a scalability claim.")
    parser.add_argument("--database-url", default=os.environ.get("VISIONGUARD_DATABASE_URL"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--api-base")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or VISIONGUARD_DATABASE_URL is required")

    pooled = create_engine(args.database_url, pool_pre_ping=True)
    with pooled.connect() as connection:
        user_id = connection.scalar(text("SELECT id FROM users WHERE email=:email"), {"email": args.email})
    if not user_id:
        raise SystemExit("benchmark user was not found")

    cold = create_engine(args.database_url, poolclass=NullPool)
    connections = []
    for _ in range(args.iterations):
        started = time.perf_counter()
        with cold.connect() as connection:
            connection.scalar(text("SELECT 1"))
        connections.append((time.perf_counter() - started) * 1000)

    tenant_queries, job_queries = [], []
    for _ in range(args.iterations):
        with pooled.begin() as connection:
            connection.execute(text("SELECT visionguard_context.set_tenant_context(:user,:org,CAST(:sites AS text[]))"), {"user": user_id, "org": args.organization_id, "sites": [args.site_id]})
            started = time.perf_counter()
            connection.scalar(text("SELECT count(*) FROM videos"))
            tenant_queries.append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            connection.execute(text("SELECT id,status,progress,stage FROM processing_jobs ORDER BY created_at DESC LIMIT 25")).all()
            job_queries.append((time.perf_counter() - started) * 1000)

    result = {
        "warning": "Small localhost benchmark; not evidence of production scalability.",
        "database_connection": summary(connections),
        "tenant_video_count_query": summary(tenant_queries),
        "job_metadata_query": summary(job_queries),
    }
    password = os.environ.get("VISIONGUARD_API_PASSWORD")
    if args.api_base and password:
        with httpx.Client(base_url=args.api_base, timeout=10) as client:
            login = client.post("/api/auth/login", json={"email": args.email, "password": password})
            login.raise_for_status()
            headers = {"X-Organization-ID": args.organization_id, "X-Site-ID": args.site_id}
            api_times = []
            for _ in range(args.iterations):
                started = time.perf_counter()
                response = client.get("/api/overview", headers=headers)
                response.raise_for_status()
                api_times.append((time.perf_counter() - started) * 1000)
            result["overview_api"] = summary(api_times)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
