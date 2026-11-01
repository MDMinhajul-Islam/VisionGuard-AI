"""Grant the application role only the policy helper functions it must execute.

Revision ID: 20261031_0003
Revises: 20261031_0002
"""
import os

from alembic import op

from app.database.postgres_security import install_postgres_security

revision = "20261031_0003"
down_revision = "20261031_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    install_postgres_security(op.get_bind(), os.environ.get("VISIONGUARD_APP_USER", "visionguard_app"))


def downgrade() -> None:
    raise RuntimeError("Security-policy downgrade is intentionally disabled")
