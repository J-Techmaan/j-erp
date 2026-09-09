from datetime import timedelta
from hashlib import sha256
import re
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import AuthSession, User, now

Db = Annotated[Session, Depends(get_db)]
SESSION_COOKIE = 'jerp_session'
COOKIE_PATH = '/api'


def request_token_hash(request: Request):
    token = request.cookies.get(SESSION_COOKIE, '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        return None
    return sha256(token.encode('ascii')).hexdigest()


def revoke_session(db: Session, request: Request):
    token_hash = request_token_hash(request)
    if token_hash:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))


def issue_session(db: Session, request: Request, user: User, remember: bool):
    settings = get_settings()
    lifetime = timedelta(days=settings.persistent_session_days) if remember else timedelta(hours=settings.session_hours)
    token = secrets.token_urlsafe(32)
    revoke_session(db, request)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
    db.add(AuthSession(user_id=user.id, token_hash=sha256(token.encode('ascii')).hexdigest(), expires_at=now() + lifetime))
    return token, int(lifetime.total_seconds()) if remember else None


def set_session_cookie(response: Response, token: str, max_age: int | None):
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True,
                        secure=get_settings().session_cookie_secure, samesite='lax', path=COOKIE_PATH)
    response.headers['Cache-Control'] = 'no-store'


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH, httponly=True,
                           secure=get_settings().session_cookie_secure, samesite='lax')
    response.headers['Cache-Control'] = 'no-store'


def current_user(request: Request, db: Db):
    token_hash = request_token_hash(request)
    user = db.scalar(select(User).join(AuthSession).where(
        AuthSession.token_hash == token_hash,
        AuthSession.expires_at > now(), User.is_active.is_(True),
    )) if token_hash else None
    if user is None:
        raise HTTPException(401, '로그인이 필요합니다. 다시 로그인해 주세요.')
    return user


CurrentUser = Annotated[User, Depends(current_user)]
