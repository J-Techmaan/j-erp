import secrets

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.security import CurrentUser, Db
from app.models import Group, GroupMembership, GroupRole, MembershipStatus
from app.schemas import GroupCreate, GroupJoin, GroupOut, MembershipOut

router = APIRouter(prefix='/groups', tags=['groups'])


def code():
    return secrets.token_hex(4).upper()


def active_membership(db, group_id, user_id):
    membership = db.scalar(select(GroupMembership).where(
        GroupMembership.group_id == group_id, GroupMembership.user_id == user_id,
        GroupMembership.status == MembershipStatus.ACTIVE,
    ))
    if membership is None or not db.get(Group, group_id).is_active:
        raise HTTPException(403, '이 그룹을 사용할 권한이 없습니다.')
    return membership


def require_owner(db, group_id, user_id):
    membership = active_membership(db, group_id, user_id)
    if membership.role != GroupRole.OWNER:
        raise HTTPException(403, '그룹장만 처리할 수 있습니다.')
    return membership


def require_manager(db, group_id, user_id):
    membership = active_membership(db, group_id, user_id)
    if membership.role != GroupRole.OWNER and not membership.is_admin:
        raise HTTPException(403, '그룹장 또는 관리자만 처리할 수 있습니다.')
    return membership


class AdminIn(BaseModel):
    is_admin: StrictBool


@router.put('/{group_id}/members/{membership_id}/admin', response_model=MembershipOut)
def set_admin(group_id: int, membership_id: int, data: AdminIn, db: Db, user: CurrentUser):
    require_owner(db, group_id, user.id)
    member = db.scalar(select(GroupMembership).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.ACTIVE))
    if member is None:
        raise HTTPException(404, '그룹원을 찾을 수 없습니다.')
    if member.role == GroupRole.OWNER:
        raise HTTPException(409, '그룹장 권한은 변경할 수 없습니다.')
    member.is_admin = data.is_admin
    db.commit()
    return member


def serialize(group, role=None, members=None):
    return GroupOut.model_validate(group).model_copy(update={'my_role': role, 'members': members or []})


@router.get('', response_model=list[GroupOut])
def groups(db: Db, user: CurrentUser):
    memberships = db.scalars(select(GroupMembership).options(selectinload(GroupMembership.group)).where(
        GroupMembership.user_id == user.id, GroupMembership.status == MembershipStatus.ACTIVE,
    ).order_by(GroupMembership.id)).all()
    return [serialize(item.group, item.role) for item in memberships if item.group.is_active]


@router.post('', response_model=GroupOut, status_code=201)
def create_group(data: GroupCreate, db: Db, user: CurrentUser):
    for _ in range(5):
        group = Group(name=data.name, code=code(), owner_id=user.id)
        try:
            db.add(group); db.flush()
            db.add(GroupMembership(group_id=group.id, user_id=user.id, role=GroupRole.OWNER, status=MembershipStatus.ACTIVE))
            db.commit()
            return serialize(group, GroupRole.OWNER)
        except IntegrityError:
            db.rollback()
    raise HTTPException(503, '그룹 코드를 만들지 못했습니다. 다시 시도해 주세요.')


@router.post('/join', status_code=201)
def join_group(data: GroupJoin, db: Db, user: CurrentUser):
    group = db.scalar(select(Group).where(Group.code == data.code, Group.is_active.is_(True)))
    if group is None:
        raise HTTPException(404, '그룹 코드를 확인해 주세요.')
    membership = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user.id))
    if membership and membership.status in {MembershipStatus.ACTIVE, MembershipStatus.PENDING}:
        raise HTTPException(409, '이미 가입했거나 승인을 기다리는 그룹입니다.')
    if membership:
        membership.status = MembershipStatus.PENDING
        membership.is_admin = False
    else:
        db.add(GroupMembership(group_id=group.id, user_id=user.id, status=MembershipStatus.PENDING))
    db.commit()
    return {'detail': '가입 요청을 보냈습니다. 그룹장의 승인을 기다려 주세요.', 'group_name': group.name}


@router.get('/{group_id}/pending', response_model=list[MembershipOut])
def pending_requests(group_id: int, db: Db, user: CurrentUser):
    manager = require_manager(db, group_id, user.id)
    return db.scalars(select(GroupMembership).options(selectinload(GroupMembership.user)).where(GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.PENDING).order_by(GroupMembership.created_at)).all()


@router.get('/{group_id}', response_model=GroupOut)
def group_detail(group_id: int, db: Db, user: CurrentUser):
    membership = active_membership(db, group_id, user.id)
    group = db.get(Group, group_id)
    if not group.is_active: raise HTTPException(404, '그룹을 찾을 수 없습니다.')
    members = db.scalars(select(GroupMembership).options(selectinload(GroupMembership.user)).where(GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.ACTIVE).order_by(GroupMembership.role, GroupMembership.id)).all()
    return serialize(group, membership.role, members)


@router.post('/{group_id}/members/{membership_id}/approve', response_model=MembershipOut)
def approve_member(group_id: int, membership_id: int, db: Db, user: CurrentUser):
    manager = require_manager(db, group_id, user.id)
    membership = db.scalar(select(GroupMembership).options(selectinload(GroupMembership.user)).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.PENDING))
    if membership is None: raise HTTPException(404, '가입 요청을 찾을 수 없습니다.')
    membership.status = MembershipStatus.ACTIVE; membership.role = GroupRole.MEMBER
    db.commit(); return membership


@router.post('/{group_id}/members/{membership_id}/reject', status_code=204)
def reject_member(group_id: int, membership_id: int, db: Db, user: CurrentUser):
    manager = require_manager(db, group_id, user.id)
    membership = db.scalar(select(GroupMembership).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.PENDING))
    if membership is None: raise HTTPException(404, '가입 요청을 찾을 수 없습니다.')
    membership.status = MembershipStatus.REJECTED; db.commit(); return Response(status_code=204)


@router.delete('/{group_id}/members/{membership_id}', status_code=204)
def remove_member(group_id: int, membership_id: int, db: Db, user: CurrentUser):
    manager = require_manager(db, group_id, user.id)
    membership = db.scalar(select(GroupMembership).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id, GroupMembership.status == MembershipStatus.ACTIVE))
    if membership is None: raise HTTPException(404, '그룹원을 찾을 수 없습니다.')
    if membership.role == GroupRole.OWNER: raise HTTPException(409, '그룹장은 내보낼 수 없습니다.')
    if membership.is_admin and manager.role != GroupRole.OWNER:
        raise HTTPException(403, '?그룹장 또는 관리자만 처리할 수 있습니다.')
    db.delete(membership); db.commit(); return Response(status_code=204)


@router.delete('/{group_id}', status_code=204)
def delete_group(group_id: int, db: Db, user: CurrentUser):
    require_owner(db, group_id, user.id)
    group = db.get(Group, group_id)
    group.is_active = False
    db.commit(); return Response(status_code=204)
