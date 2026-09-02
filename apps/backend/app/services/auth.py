from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.models.auth_session import AuthSession
from app.models.user import User

password_hash = PasswordHash.recommended()


def hash_password(value: str) -> str:
    return password_hash.hash(value)


def verify_password(value: str, hashed_value: str) -> bool:
    return password_hash.verify(value, hashed_value)


def create_session(db: Session, user: User, settings: Settings) -> str:
    raw_token = token_urlsafe(32)
    session = AuthSession(
        id=str(uuid4()),
        token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(session)
    return raw_token


def get_current_user(request: Request, db: Session, settings: Settings) -> User:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user).joinedload(User.merchant))
        .where(AuthSession.token_hash == token_hash)
    )
    expires_at = session.expires_at if session is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if session is None or expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return session.user
