"""Harden actor bootstrap and transaction context policies.

Revision ID: 20261031_0002
Revises: 20261031_0001
"""
import os

from alembic import op

from app.database.postgres_security import install_postgres_security

revision = "20261031_0002"
down_revision = "20261031_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    install_postgres_security(op.get_bind(), os.environ.get("VISIONGUARD_APP_USER", "visionguard_app"))


def downgrade() -> None:
    raise RuntimeError("Security-policy downgrade is intentionally disabled")
