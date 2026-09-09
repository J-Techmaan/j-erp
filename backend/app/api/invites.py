import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.groups import require_manager
from app.core.security import CurrentUser, Db
from app.models import Group, GroupInvite, GroupMembership, GroupRole, MembershipStatus, User, now

router = APIRouter(tags=['invites'])


def resolve(db, token):
    invite = db.scalar(select(GroupInvite).where(GroupInvite.token == token))
    if invite is None:
        raise HTTPException(404, '초대 링크를 찾을 수 없습니다.')
    group = db.get(Group, invite.group_id)
    if not invite.is_active or invite.expires_at.replace(tzinfo=timezone.utc) <= now() or not group or not group.is_active:
        raise HTTPException(410, '만료되거나 사용할 수 없는 초대 링크입니다.')
    return invite, group


@router.post('/groups/{group_id}/invites', status_code=201)
def create(group_id: int, db: Db, user: CurrentUser):
    require_manager(db, group_id, user.id)
    invite = GroupInvite(group_id=group_id, created_by=user.id, token=secrets.token_urlsafe(32), expires_at=now() + timedelta(days=7))
    db.add(invite)
    db.commit()
    return {'token': invite.token, 'expires_at': invite.expires_at}


@router.get('/invites/{token}')
def detail(token: str, db: Db):
    invite, group = resolve(db, token)
    inviter = db.get(User, invite.created_by)
    count = db.scalar(select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.status == MembershipStatus.ACTIVE))
    return {'group_name': group.name, 'inviter': inviter.display_name if inviter else None, 'member_count': count, 'expires_at': invite.expires_at, 'status': 'ACTIVE'}


@router.post('/invites/{token}/accept')
def accept(token: str, db: Db, user: CurrentUser):
    invite, group = resolve(db, token)
    membership = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user.id))
    if membership and membership.status == MembershipStatus.ACTIVE:
        return {'group_id': group.id, 'detail': '이미 가입된 그룹입니다.'}
    if membership:
        membership.status = MembershipStatus.ACTIVE
        membership.role = GroupRole.MEMBER
        membership.is_admin = False
    else:
        db.add(GroupMembership(group_id=group.id, user_id=user.id, role=GroupRole.MEMBER, status=MembershipStatus.ACTIVE))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        membership = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user.id, GroupMembership.status == MembershipStatus.ACTIVE))
        if membership is None:
            raise HTTPException(409, '가입 상태가 변경되었습니다. 다시 시도해 주세요.')
        return {'group_id': group.id, 'detail': '이미 가입된 그룹입니다.'}
    return {'group_id': group.id, 'detail': '그룹에 가입했습니다.'}
