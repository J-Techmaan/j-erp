from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.security import (CurrentUser, Db, clear_session_cookie, issue_session,
                               revoke_session, set_session_cookie)
from app.models import AuthAccount, GroupMembership, MembershipStatus, User
from app.schemas import CurrentUserOut, LoginIn, SignupIn, UserOut
from app.services.identity import password_hasher, verify_password

router = APIRouter(tags=['auth / users'])


@router.post('/auth/signup', response_model=CurrentUserOut, status_code=201)
def signup(data: SignupIn, request: Request, response: Response, db: Db):
    # Hash before duplicate checks to avoid a quick account-existence timing probe.
    password_hash = password_hasher.hash(data.password)
    user = User(email=data.email, username=uuid4().hex, display_name=data.name)
    try:
        db.add(user)
        db.flush()
        db.add(AuthAccount(user_id=user.id, provider='local', provider_user_id=data.email,
                           password_hash=password_hash))
        token, max_age = issue_session(db, request, user, data.remember_me)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Duplicate emails are rejected without exposing account/provider details.
        raise HTTPException(409, '해당 이메일로 가입할 수 없습니다. 다른 이메일을 사용하거나 로그인해 주세요.')
    set_session_cookie(response, token, max_age)
    return user


@router.post('/auth/login', response_model=CurrentUserOut)
def login(data: LoginIn, request: Request, response: Response, db: Db):
    account = db.scalar(select(AuthAccount).where(AuthAccount.provider == 'local',
                                                 AuthAccount.provider_user_id == data.email))
    valid = verify_password(account.password_hash if account else None, data.password)
    if not valid or not account or not account.user.is_active:
        raise HTTPException(401, '이메일 또는 비밀번호가 올바르지 않습니다.')
    if password_hasher.check_needs_rehash(account.password_hash):
        account.password_hash = password_hasher.hash(data.password)
    token, max_age = issue_session(db, request, account.user, data.remember_me)
    db.commit()
    set_session_cookie(response, token, max_age)
    return account.user


@router.post('/auth/logout', status_code=204)
def logout(request: Request, response: Response, db: Db):
    revoke_session(db, request)
    db.commit()
    clear_session_cookie(response)


@router.get('/auth/me', response_model=CurrentUserOut)
@router.get('/users/me', response_model=CurrentUserOut)
def me(user: CurrentUser, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return user


@router.get('/users/search', response_model=list[UserOut])
def search_users(db: Db, user: CurrentUser, group_id: int = Query(gt=0), q: str = Query(default='', max_length=100)):
    member_ids = select(GroupMembership.user_id).where(GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.ACTIVE)
    own_membership = db.scalar(select(GroupMembership.id).where(GroupMembership.group_id == group_id, GroupMembership.user_id == user.id, GroupMembership.status == MembershipStatus.ACTIVE))
    if own_membership is None: raise HTTPException(403, '이 그룹을 사용할 권한이 없습니다.')
    return db.scalars(select(User).where(User.id.in_(member_ids), User.is_active.is_(True), or_(
        User.display_name.contains(q, autoescape=True), User.username.contains(q, autoescape=True),
    )).order_by(User.id).limit(50)).all()
