from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select

from app.core.security import CurrentUser, Db
from app.models import Group, GroupMembership, MembershipStatus


def current_membership(
    db: Db,
    user: CurrentUser,
    group_id: Annotated[int | None, Header(alias='X-Group-ID')] = None,
):
    if group_id is None:
        raise HTTPException(400, '사용할 그룹을 선택해 주세요.')
    membership = db.scalar(select(GroupMembership).join(Group).where(
        Group.is_active.is_(True),
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user.id,
        GroupMembership.status == MembershipStatus.ACTIVE,
    ))
    if membership is None:
        raise HTTPException(403, '이 그룹을 사용할 권한이 없습니다.')
    return membership


CurrentMembership = Annotated[GroupMembership, Depends(current_membership)]
