from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.migrations import LEGACY_RESEARCH_ORG_ID, LEGACY_RESEARCH_SITE_ID
from app.database.models import Organization, OrganizationMembership, Site, SiteAccess, User
from app.database.session import SessionLocal, init_db


def grant(email: str, organization_id: str, role: str, site_ids: list[str]) -> None:
    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().casefold()))
        organization = db.get(Organization, organization_id)
        if not user or not organization:
            raise SystemExit("user or organization was not found")
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )) or OrganizationMembership(user_id=user.id, organization_id=organization_id, role=role)
        membership.role = role; membership.status = "active"
        db.add(membership); db.flush()
        db.query(SiteAccess).filter(SiteAccess.membership_id == membership.id).delete()
        sites = db.scalars(select(Site).where(Site.organization_id == organization_id, Site.id.in_(site_ids))).all()
        if {site.id for site in sites} != set(site_ids):
            raise SystemExit("one or more sites do not belong to the organization")
        for site in sites:
            db.add(SiteAccess(membership_id=membership.id, site_id=site.id))
        db.commit()
        print(f"Granted {role} membership in {organization.name} to {user.email}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly grant a user tenant access; no access is assigned during migration.")
    parser.add_argument("email")
    parser.add_argument("--organization-id", default=LEGACY_RESEARCH_ORG_ID)
    parser.add_argument("--site-id", action="append", dest="site_ids", default=[])
    parser.add_argument("--role", choices=["organization_admin", "site_admin", "safety_reviewer", "read_only_auditor"], default="organization_admin")
    args = parser.parse_args()
    site_ids = args.site_ids or ([LEGACY_RESEARCH_SITE_ID] if args.organization_id == LEGACY_RESEARCH_ORG_ID else [])
    grant(args.email, args.organization_id, args.role, site_ids)


if __name__ == "__main__":
    main()
