from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.core.security import CurrentUser, Db
from app.core.groups import CurrentMembership
from app.models import Schedule
from app.schemas import ScheduleIn, ScheduleOut

router = APIRouter(prefix='/schedules', tags=['schedules'])


def owned_schedule(db, schedule_id, user_id, group_id):
    schedule = db.scalar(select(Schedule).where(Schedule.id == schedule_id, Schedule.user_id == user_id, Schedule.group_id == group_id))
    if schedule is None:
        raise HTTPException(404, '일정을 찾을 수 없습니다.')
    return schedule


def utc(value):
    if value.tzinfo is None:
        raise HTTPException(422, '날짜에 시간대를 포함하세요.')
    return value.astimezone(timezone.utc)


@router.get('', response_model=list[ScheduleOut])
def schedules(db: Db, user: CurrentUser, membership: CurrentMembership, start: datetime, end: datetime, offset: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=1000)):
    start, end = utc(start), utc(end)
    if start >= end:
        raise HTTPException(422, '조회 기간을 확인하세요.')
    return db.scalars(select(Schedule).where(Schedule.group_id == membership.group_id, Schedule.start_at < end, Schedule.end_at >= start).order_by(Schedule.start_at, Schedule.id).offset(offset).limit(limit)).all()


@router.post('', response_model=ScheduleOut, status_code=201)
def create_schedule(data: ScheduleIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    schedule = Schedule(user_id=user.id, group_id=membership.group_id, **data.model_dump())
    db.add(schedule)
    db.commit()
    return schedule


@router.put('/{schedule_id}', response_model=ScheduleOut)
def update_schedule(schedule_id: int, data: ScheduleIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    schedule = owned_schedule(db, schedule_id, user.id, membership.group_id)
    for key, value in data.model_dump().items():
        setattr(schedule, key, value)
    db.commit()
    return schedule


@router.delete('/{schedule_id}', status_code=204)
def delete_schedule(schedule_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    db.delete(owned_schedule(db, schedule_id, user.id, membership.group_id))
    db.commit()
    return Response(status_code=204)
