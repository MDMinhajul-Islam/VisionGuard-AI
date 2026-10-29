from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.database.models import User
from app.database.session import SessionLocal


ALGORITHM = "HS256"
ISSUER = "visionguard-local"
AUDIENCE = "visionguard-api"
SESSION_COOKIE = "visionguard_session"
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_token_minutes),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.effective_auth_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            get_settings().effective_auth_secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "role", "iat", "exp", "jti"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired session") from error


def authenticate_token(token: str) -> User:
    payload = decode_access_token(token)
    with SessionLocal() as db:
        user = db.get(User, payload["sub"])
        if not user or user.disabled or user.role != payload["role"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session user is unavailable")
        db.expunge(user)
        return user


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(request: Request) -> User:
        user = current_user(request)
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return dependency
