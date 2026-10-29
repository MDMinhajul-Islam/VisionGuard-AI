from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.database.models import AuthSession, User, now_iso
from app.database.session import SessionLocal


ALGORITHM = "HS256"
ISSUER = "visionguard-local"
AUDIENCE = "visionguard-api"
SESSION_COOKIE = "visionguard_session"
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password-value")


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


def create_access_token(user: User, db=None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    expires_at = now + timedelta(minutes=settings.auth_token_minutes)
    payload = {
        "sub": user.id,
        "role": user.role,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": expires_at,
        "jti": jti,
        "sv": user.session_version,
    }
    token = jwt.encode(payload, settings.effective_auth_secret(), algorithm=ALGORITHM)
    owns_session = db is None
    session = db or SessionLocal()
    try:
        session.add(AuthSession(
            jti=jti, user_id=user.id, session_version=user.session_version,
            expires_at=expires_at.isoformat(),
        ))
        session.commit()
    finally:
        if owns_session:
            session.close()
    return token


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            get_settings().effective_auth_secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "role", "iat", "exp", "jti", "sv"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired session") from error


def authenticate_session(token: str) -> tuple[User, dict]:
    payload = decode_access_token(token)
    with SessionLocal() as db:
        user = db.get(User, payload["sub"])
        session = db.get(AuthSession, payload["jti"])
        if (
            not user or user.disabled or user.role != payload["role"]
            or user.session_version != payload["sv"]
            or not session or session.revoked_at is not None
            or session.session_version != user.session_version
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session user is unavailable")
        db.expunge(user)
        return user, payload


def authenticate_token(token: str) -> User:
    return authenticate_session(token)[0]


def revoke_session(jti: str) -> None:
    with SessionLocal() as db:
        session = db.get(AuthSession, jti)
        if session and session.revoked_at is None:
            session.revoked_at = now_iso()
            db.commit()


def revoke_all_user_sessions(user: User, db) -> None:
    user.session_version += 1
    user.password_changed_at = now_iso()
    for session in db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)):
        session.revoked_at = now_iso()


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
