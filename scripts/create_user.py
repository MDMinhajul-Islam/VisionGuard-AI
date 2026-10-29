from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.security import hash_password, normalize_email
from app.database import init_db
from app.database.models import User
from app.database.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local VisionGuard application user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["admin", "reviewer"], required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    init_db()
    email = normalize_email(args.email)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            parser.error("email already exists")
        user = User(email=email, display_name=args.name.strip(), role=args.role, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        print(f"Created {user.role} user {user.email} ({user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
