"""Create the PostgreSQL schema and tenant RLS foundation.

Revision ID: 20261031_0001
Revises: None
"""
from __future__ import annotations

import os

from alembic import op

from app.database.session import Base
from app.database import models  # noqa: F401
from app.database.postgres_security import install_postgres_security


revision = "20261031_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Sprint 5A migration requires PostgreSQL")
    Base.metadata.create_all(bind=bind)
    app_role = os.environ.get("VISIONGUARD_APP_USER", "visionguard_app")
    install_postgres_security(bind, app_role)


def downgrade() -> None:
    raise RuntimeError("Destructive automatic downgrade is disabled; use the documented restore procedure")
