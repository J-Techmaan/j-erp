from datetime import date

from fastapi import APIRouter, Body, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import or_, select

from app.core.groups import CurrentMembership
from app.core.security import CurrentUser, Db
from app.models import Document, DocumentStatus, GroupMembership, MembershipStatus, User
from app.models.projects import MODELS, Project, ProjectActivity
from app.schemas.projects import SCHEMAS, ProjectIn
from app.services import project_control as control

router = APIRouter(prefix='/projects', tags=['project control'])


def parse(kind, payload):
    if kind not in SCHEMAS:
        raise HTTPException(404, '지원하지 않는 항목입니다.')
    try:
        return SCHEMAS[kind].model_validate(payload).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False))


@router.get('/meta')
def metadata(db: Db, user: CurrentUser, membership: CurrentMembership):
    members = db.scalars(select(User).join(GroupMembership).where(GroupMembership.group_id == membership.group_id,
        GroupMembership.status == MembershipStatus.ACTIVE, User.is_active.is_(True))).all()
    return {'schemas': {k: s.model_json_schema() for k, s in SCHEMAS.items()},
            'members': [{'id': u.id, 'name': u.display_name} for u in members]}


@router.get('')
def projects(db: Db, user: CurrentUser, membership: CurrentMembership, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    rows = db.scalars(select(Project).where(Project.group_id == membership.group_id, Project.is_deleted.is_(False))
                      .order_by(Project.updated_at.desc(), Project.id.desc()).offset(offset).limit(limit))
    return [control.snapshot(row) for row in rows]


@router.post('', status_code=201)
def create_project(data: ProjectIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    values = data.model_dump()
    control.assign_code('projects', values)
    values['owner'] = values['owner'] or user.id
    values['project_manager'] = values['project_manager'] or user.id
    control.validate_members(db, membership.group_id, values)
    project = Project(group_id=membership.group_id, **values)
    db.add(project)
    control.audit(db, None, user.id, 'projects', project, 'PROJECT_CREATED')
    control.save(db)
    return control.snapshot(project)


@router.post('/seed/karaoke', status_code=201)
def seed(db: Db, user: CurrentUser, membership: CurrentMembership):
    values = {}
    control.assign_code('projects', values)
    project = Project(group_id=membership.group_id, **values,
        project_name='코인노래방 1호점 오픈 프로젝트', description='', project_type='OPENING', owner=user.id,
        project_manager=user.id, status='PLANNING', priority='P1', start_date=date(2026, 9, 9),
        target_end_date=date(2027, 3, 15), progress_percent=0, health_status='GREEN', budget=0, actual_cost=0)
    db.add(project)
    control.audit(db, None, user.id, 'projects', project, 'PROJECT_CREATED')
    titles = ['프로젝트 관리', '사업 계획', '법인·행정', '재무·세무', '입지 조사', '점포 실사·계약', '설계·인테리어',
              '전기·소방·방음', '노래방 장비', '인허가', 'IT·결제·CCTV', 'J-ERP', '운영·표준절차', '마케팅·오픈']
    for number, title in enumerate(titles, 1):
        control.write_item(db, project, membership, 'wbs', parse('wbs', {'wbs_code': f'{number}.0', 'title': title, 'sort_order': number}))
    for category in ('LEGAL', 'LOCATION', 'CONSTRUCTION', 'FIRE', 'ELECTRICAL', 'SOUNDPROOF', 'EQUIPMENT', 'PAYMENT', 'IT', 'SECURITY', 'ACCOUNTING', 'STAFF', 'SOP', 'MARKETING'):
        control.write_item(db, project, membership, 'readiness', parse('readiness', {'category': category}))
    control.save(db)
    return control.snapshot(project)


@router.get('/{project_id}')
def detail(project_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    project = control.project_for(db, project_id, membership)
    return {**control.snapshot(project), 'can_manage': control.manages(project, membership)}


@router.put('/{project_id}')
def update(project_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, payload: dict = Body()):
    project = control.project_for(db, project_id, membership)
    control.require_manager(project, membership)
    control.check_revision(project, payload.pop('revision', None))
    data = parse('projects', payload)
    control.assign_code('projects', data, project)
    control.validate_members(db, membership.group_id, data)
    before = control.snapshot(project)
    for key, value in data.items():
        setattr(project, key, value)
    control.audit(db, project.id, user.id, 'projects', project,
                  'BUDGET_CHANGED' if before['budget'] != str(project.budget) or before['actual_cost'] != str(project.actual_cost) else 'PROJECT_UPDATED', before)
    control.save(db)
    return control.snapshot(project)


@router.delete('/{project_id}', status_code=204)
def delete_project(project_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, revision: int = Query(gt=0)):
    project = control.project_for(db, project_id, membership)
    control.require_manager(project, membership)
    control.check_revision(project, revision)
    before = control.snapshot(project)
    project.is_deleted = True
    control.audit(db, project.id, user.id, 'projects', project, 'PROJECT_ARCHIVED', before)
    control.save(db)
    return Response(status_code=204)


@router.get('/{project_id}/dashboard')
def dashboard(project_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    return control.project_dashboard(db, control.project_for(db, project_id, membership))


@router.get('/{project_id}/activity')
def activity(project_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    control.project_for(db, project_id, membership)
    rows = db.execute(select(ProjectActivity, User.display_name).join(User, ProjectActivity.actor_id == User.id)
        .where(ProjectActivity.project_id == project_id).order_by(ProjectActivity.id.desc()).offset(offset).limit(limit)).all()
    return [{**control.snapshot(row), 'actor_name': name} for row, name in rows]


@router.get('/{project_id}/{kind}')
def items(project_id: int, kind: str, db: Db, user: CurrentUser, membership: CurrentMembership,
          offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), task_id: int | None = None):
    project = control.project_for(db, project_id, membership)
    if kind not in MODELS or kind == 'projects':
        raise HTTPException(404, '지원하지 않는 항목입니다.')
    model = MODELS[kind]
    query = select(model).where(model.project_id == project.id, model.is_deleted.is_(False))
    if kind == 'comments' and task_id is not None:
        query = query.where(model.task_id == task_id)
    if kind == 'wbs':
        query = query.order_by(model.sort_order, model.id)
    else:
        query = query.order_by(model.id.desc())
    result = [control.snapshot(row) for row in db.scalars(query.offset(offset).limit(limit))]
    if kind == 'documents':
        titles = dict(db.execute(select(Document.id, Document.title).where(
            Document.id.in_([row['document_id'] for row in result]), Document.group_id == project.group_id,
            or_(Document.author_id == user.id, Document.status != DocumentStatus.DRAFT))).all())
        for row in result:
            row['document_title'] = titles.get(row['document_id'], '열람 권한이 없는 문서')
    return result


@router.post('/{project_id}/{kind}', status_code=201)
def create_item(project_id: int, kind: str, db: Db, user: CurrentUser, membership: CurrentMembership, payload: dict = Body()):
    project = control.project_for(db, project_id, membership)
    if kind == 'projects':
        raise HTTPException(404, '지원하지 않는 항목입니다.')
    row = control.write_item(db, project, membership, kind, parse(kind, payload))
    control.save(db)
    return control.snapshot(row)


@router.get('/{project_id}/{kind}/{item_id}')
def item_detail(project_id: int, kind: str, item_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    return control.snapshot(control.item_for(db, control.project_for(db, project_id, membership), kind, item_id))


@router.put('/{project_id}/{kind}/{item_id}')
def update_item(project_id: int, kind: str, item_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, payload: dict = Body()):
    project = control.project_for(db, project_id, membership)
    row = control.item_for(db, project, kind, item_id)
    revision = payload.pop('revision', None)
    acknowledge = payload.pop('acknowledge_dependencies', False)
    if not isinstance(acknowledge, bool):
        raise HTTPException(422, '선행조건 확인 값이 올바르지 않습니다.')
    control.write_item(db, project, membership, kind, parse(kind, payload), row, revision, acknowledge)
    control.save(db)
    return control.snapshot(row)


@router.delete('/{project_id}/{kind}/{item_id}', status_code=204)
def delete_item(project_id: int, kind: str, item_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, revision: int = Query(gt=0)):
    project = control.project_for(db, project_id, membership)
    row = control.item_for(db, project, kind, item_id)
    if kind == 'comments' and row.author_id == user.id:
        pass
    else:
        control.require_manager(project, membership)
    control.check_revision(row, revision)
    if kind in ('ecr', 'eco') and getattr(row, 'status', getattr(row, 'implementation_status', '')) in ('APPROVED', 'CLOSED'):
        raise HTTPException(409, '확정된 변경 기록은 보관 해제할 수 없습니다.')
    # Keep references valid: linked records must be disconnected before archiving.
    for source_kind, model in MODELS.items():
        if source_kind == 'projects':
            continue
        for field, target_kind in control.REFS.items():
            if target_kind == kind and hasattr(model, field):
                if db.scalar(select(model.id).where(model.project_id == project.id, model.is_deleted.is_(False), getattr(model, field) == row.id).limit(1)):
                    raise HTTPException(409, '다른 항목에서 참조 중입니다. 연결을 먼저 해제해 주세요.')
    before = control.snapshot(row)
    row.is_deleted = True
    control.audit(db, project.id, user.id, kind, row, f'{kind.upper()}_ARCHIVED', before)
    control.save(db)
    return Response(status_code=204)
