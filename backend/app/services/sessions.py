"""Session lifecycle: create, validate, rotate, revoke.

A session is backed by a DB row holding a *hash* of the refresh token.
Access tokens are short-lived JWTs (stateless). Refresh tokens are opaque
random strings checked against the DB row, so revocation actually works.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Session as SessionModel, User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_session(
    db: DbSession,
    user: User,
    device_id: int | None,
    ip: str | None,
    user_agent: str | None,
) -> tuple[SessionModel, str, str]:
    """Returns (session_row, access_token, refresh_token_plain).

    `user_agent` is accepted for call-site stability but no longer stored.
    """
    refresh_plain = _new_refresh_token()
    row = SessionModel(
        user_id=user.id,
        device_id=device_id,
        refresh_token_hash=_hash_token(refresh_plain),
        ip_address=ip,
        expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    db.add(row)
    db.flush()
    access = create_access_token(str(user.uuid), sid=row.id)
    return row, access, refresh_plain


def find_session_by_refresh(db: DbSession, refresh_token: str) -> SessionModel | None:
    h = _hash_token(refresh_token)
    stmt = select(SessionModel).where(SessionModel.refresh_token_hash == h)
    return db.execute(stmt).scalar_one_or_none()


def is_session_valid(s: SessionModel | None) -> bool:
    if s is None or s.revoked_at is not None:
        return False
    return s.expires_at > datetime.now(timezone.utc)


def rotate_session(db: DbSession, s: SessionModel) -> str:
    """Rotate the refresh token, return new plain refresh token."""
    refresh_plain = _new_refresh_token()
    s.refresh_token_hash = _hash_token(refresh_plain)
    s.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    db.flush()
    return refresh_plain


def revoke_session(db: DbSession, s: SessionModel) -> None:
    s.revoked_at = datetime.now(timezone.utc)
    db.flush()


def revoke_all_user_sessions(db: DbSession, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    stmt = (
        update(SessionModel)
        .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    result = db.execute(stmt)
    return result.rowcount or 0


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    # With the Next.js rewrite proxy the frontend and API share the same origin,
    # so first-party SameSite=Lax cookies work in dev without HTTPS.
    secure = not settings.DEBUG
    samesite = "lax" if settings.DEBUG else "none"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        path="/api/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
