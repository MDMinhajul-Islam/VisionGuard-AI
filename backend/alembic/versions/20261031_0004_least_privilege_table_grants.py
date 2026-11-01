"""Replace schema-wide DML with explicit least-privilege application grants.

Revision ID: 20261031_0004
Revises: 20261031_0003
"""
import os

from alembic import op

from app.database.postgres_security import install_postgres_security

revision = "20261031_0004"
down_revision = "20261031_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    install_postgres_security(op.get_bind(), os.environ.get("VISIONGUARD_APP_USER", "visionguard_app"))


def downgrade() -> None:
    raise RuntimeError("Least-privilege security downgrade is intentionally disabled")
