from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import GroupMembership, GroupRole, MembershipStatus, User, now
from app.models.projects import MODELS, Project, ProjectActivity, Task, TaskDependency, Wbs
from app.repositories.documents import get_document
from app.services.approvals import commit


def snapshot(row):
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    if row.__tablename__ == 'project_risks':
        result['risk_score'] = row.probability * row.impact
    return jsonable_encoder(result, custom_encoder={Decimal: str})


def save(db):
    try:
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '코드 또는 연결이 중복되거나 참조 중인 항목입니다.')


def project_for(db, project_id, membership):
    row = db.scalar(select(Project).where(Project.id == project_id, Project.group_id == membership.group_id, Project.is_deleted.is_(False)))
    if row is None:
        raise HTTPException(404, '프로젝트를 찾을 수 없습니다.')
    return row


def manages(project, membership):
    return membership.role == GroupRole.OWNER or membership.is_admin or membership.user_id in (project.owner, project.project_manager)


def require_manager(project, membership):
    if not manages(project, membership):
        raise HTTPException(403, '프로젝트 책임자·관리자 또는 그룹 관리자만 처리할 수 있습니다.')


def item_for(db, project, kind, item_id):
    model = MODELS.get(kind)
    if model is None or kind == 'projects':
        raise HTTPException(404, '지원하지 않는 항목입니다.')
    row = db.scalar(select(model).where(model.id == item_id, model.project_id == project.id, model.is_deleted.is_(False)))
    if row is None:
        raise HTTPException(404, '항목을 찾을 수 없습니다.')
    return row


def audit(db, project_id, actor_id, kind, row, action, before=None):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '코드 또는 연결이 중복됩니다.')
    db.add(ProjectActivity(project_id=project_id or row.id, actor_id=actor_id, entity_type=kind,
                           entity_id=row.id, action=action, before=before or {}, after=snapshot(row)))


def check_revision(row, revision):
    if revision is None or revision != row.revision:
        raise HTTPException(409, '다른 사용자가 수정했습니다. 새로고침 후 다시 시도해 주세요.')


def validate_members(db, group_id, data):
    ids = {data[k] for k in ('owner', 'project_manager', 'reviewer') if data.get(k) is not None}
    if not ids:
        return
    found = set(db.scalars(select(GroupMembership.user_id).join(User).where(
        GroupMembership.group_id == group_id, GroupMembership.user_id.in_(ids),
        GroupMembership.status == MembershipStatus.ACTIVE, User.is_active.is_(True))))
    if found != ids:
        raise HTTPException(422, '담당자는 현재 그룹의 활성 구성원이어야 합니다.')


REFS = {'wbs_id': 'wbs', 'parent_id': 'wbs', 'parent_task_id': 'tasks', 'next_task_id': 'tasks',
        'predecessor_task_id': 'tasks', 'successor_task_id': 'tasks', 'task_id': 'tasks',
        'linked_task': 'tasks', 'linked_ecr': 'ecr', 'related_ecr': 'ecr', 'vendor_id': 'vendors'}


def validate_references(db, project, kind, data, user_id, row=None):
    for field, target in REFS.items():
        if data.get(field) is not None:
            item_for(db, project, target, data[field])
    for field in ('related_tasks', 'affected_tasks'):
        for task_id in set(data.get(field, [])):
            item_for(db, project, 'tasks', task_id)
    documents = set(data.get('related_documents', []) + data.get('affected_documents', []))
    if data.get('document_id'):
        documents.add(data['document_id'])
    for doc_id in documents:
        get_document(db, doc_id, user_id, project.group_id)
    parent_field = {'wbs': 'parent_id', 'tasks': 'parent_task_id'}.get(kind)
    if parent_field and data.get(parent_field) is not None:
        visited = {row.id} if row else set()
        parent_id = data[parent_field]
        while parent_id is not None:
            if parent_id in visited:
                raise HTTPException(422, '상위 항목에 순환 관계를 만들 수 없습니다.')
            visited.add(parent_id)
            parent_id = getattr(item_for(db, project, kind, parent_id), parent_field)
    if kind == 'tasks' and row and data.get('next_task_id') == row.id:
        raise HTTPException(422, '다음 업무는 다른 업무를 선택해 주세요.')
    if kind == 'dependencies':
        predecessor, successor = data['predecessor_task_id'], data['successor_task_id']
        edges = list(db.scalars(select(TaskDependency).where(TaskDependency.project_id == project.id, TaskDependency.is_deleted.is_(False))))
        graph = {}
        for edge in edges:
            if row and edge.id == row.id:
                continue
            graph.setdefault(edge.predecessor_task_id, []).append(edge.successor_task_id)
        queue, visited = [successor], set()
        while queue:
            node = queue.pop()
            if node == predecessor:
                raise HTTPException(422, '업무 의존성에 순환 관계를 만들 수 없습니다.')
            if node not in visited:
                visited.add(node)
                queue.extend(graph.get(node, []))


TRANSITIONS = {
    'ecr': {'DRAFT': ['SUBMITTED', 'CANCELLED'], 'SUBMITTED': ['UNDER_REVIEW', 'CANCELLED'],
            'UNDER_REVIEW': ['APPROVED', 'REJECTED', 'CANCELLED'], 'REJECTED': ['DRAFT'], 'APPROVED': [], 'CANCELLED': []},
    'eco': {'OPEN': ['IMPLEMENTING', 'FAILED'], 'IMPLEMENTING': ['VERIFYING', 'FAILED'],
            'VERIFYING': ['CLOSED', 'IMPLEMENTING', 'FAILED'], 'FAILED': ['IMPLEMENTING'], 'CLOSED': []},
    'tasks': {'BACKLOG': ['READY', 'IN_PROGRESS', 'CANCELLED'], 'READY': ['IN_PROGRESS', 'WAITING', 'BLOCKED', 'CANCELLED'],
              'IN_PROGRESS': ['WAITING', 'BLOCKED', 'REVIEW', 'DONE', 'CANCELLED'], 'WAITING': ['READY', 'IN_PROGRESS', 'BLOCKED', 'CANCELLED'],
              'BLOCKED': ['READY', 'IN_PROGRESS', 'WAITING', 'CANCELLED'], 'REVIEW': ['IN_PROGRESS', 'DONE', 'CANCELLED'],
              'DONE': ['IN_PROGRESS'], 'CANCELLED': ['BACKLOG']},
}


def dependency_warnings(db, project, task, target_status):
    edges = db.scalars(select(TaskDependency).where(TaskDependency.project_id == project.id,
        TaskDependency.successor_task_id == task.id, TaskDependency.is_deleted.is_(False))).all()
    predecessors = {t.id: t for t in db.scalars(select(Task).where(Task.id.in_([e.predecessor_task_id for e in edges])))}
    today = datetime.now(timezone(timedelta(hours=9))).date()
    warnings = []
    for edge in edges:
        predecessor = predecessors[edge.predecessor_task_id]
        if target_status == 'IN_PROGRESS' and edge.dependency_type not in ('FS', 'SS'):
            continue
        finished = edge.dependency_type in ('FS', 'FF')
        stamp = predecessor.completed_at if finished else predecessor.started_at
        met = predecessor.status == 'DONE' if finished else stamp is not None
        if not met or stamp is None or stamp.date() + timedelta(days=edge.lag_days) > today:
            warnings.append(f'{predecessor.task_code}: {edge.dependency_type} 선행조건·시차 미충족')
    return warnings


def validate_workflow(db, project, membership, kind, data, row=None, acknowledge=False):
    if kind == 'tasks' and row and row.approval_required != data['approval_required']:
        require_manager(project, membership)
    if kind in ('budget', 'eco', 'decisions'):
        require_manager(project, membership)
    if kind == 'comments' and row and row.author_id != membership.user_id:
        require_manager(project, membership)
    if kind == 'ecr' and row and row.requester != membership.user_id and not manages(project, membership):
        raise HTTPException(403, '요청자 또는 프로젝트 관리자만 변경 요청을 수정할 수 있습니다.')
    key = 'implementation_status' if kind == 'eco' else 'status'
    if kind in TRANSITIONS:
        new = data[key]
        if row:
            old = getattr(row, key)
            if new != old and new not in TRANSITIONS[kind][old]:
                raise HTTPException(409, '허용되지 않는 상태 전환입니다.')
            if kind in ('ecr', 'eco') and old in ('APPROVED', 'CLOSED'):
                raise HTTPException(409, '확정된 변경 기록은 수정할 수 없습니다. 새 변경 요청을 작성해 주세요.')
        elif new != {'ecr': 'DRAFT', 'eco': 'OPEN', 'tasks': 'BACKLOG'}[kind]:
            raise HTTPException(422, '초기 상태로 생성한 뒤 순서대로 진행해 주세요.')
    if kind == 'ecr' and data['status'] in ('APPROVED', 'REJECTED'):
        require_manager(project, membership)
        if not data['decision']:
            raise HTTPException(422, '승인 또는 반려 근거를 입력해 주세요.')
        data['reviewer'] = membership.user_id
    if kind == 'eco':
        source = item_for(db, project, 'ecr', data['linked_ecr'])
        if source.status != 'APPROVED':
            raise HTTPException(409, '승인된 ECR에서만 ECO를 발행할 수 있습니다.')
        if row and row.linked_ecr != data['linked_ecr']:
            raise HTTPException(409, '발행된 ECO의 원본 ECR은 변경할 수 없습니다.')
        if data['implementation_status'] == 'CLOSED' and (not data['verification_result'] or not data['after_state']):
            raise HTTPException(422, '종료 전에 변경 후 상태와 검증 결과를 입력해 주세요.')
    if kind == 'issues' and data['status'] in ('RESOLVED', 'CLOSED') and not data['resolution']:
        raise HTTPException(422, '해결 내용을 입력해 주세요.')
    if kind == 'tasks' and row and data['status'] in ('IN_PROGRESS', 'DONE') and data['status'] != row.status:
        if data['status'] == 'DONE' and (row.approval_required or data['approval_required']):
            require_manager(project, membership)
        warnings = dependency_warnings(db, project, row, data['status'])
        if warnings and not acknowledge:
            raise HTTPException(409, {'code': 'DEPENDENCY_WARNING', 'message': '선행조건이 충족되지 않았습니다. 확인 후 진행해 주세요.', 'warnings': warnings})


def write_item(db, project, membership, kind, data, row=None, revision=None, acknowledge=False):
    if row:
        check_revision(row, revision)
    validate_members(db, project.group_id, data)
    validate_references(db, project, kind, data, membership.user_id, row)
    validate_workflow(db, project, membership, kind, data, row, acknowledge)
    before = snapshot(row) if row else None
    if row is None:
        row = MODELS[kind](project_id=project.id)
        number_field = {'ecr': 'ecr_no', 'eco': 'eco_no', 'issues': 'issue_no', 'risks': 'risk_no', 'decisions': 'decision_no'}.get(kind)
        if number_field:
            setattr(row, number_field, f'{kind.upper()}-{uuid4().hex[:12].upper()}')
        if kind in ('ecr', 'decisions', 'comments'):
            setattr(row, {'ecr': 'requester', 'decisions': 'decided_by', 'comments': 'author_id'}[kind], membership.user_id)
        db.add(row)
    for key, value in data.items():
        setattr(row, key, value)
    status = data.get('status', data.get('implementation_status'))
    if kind == 'tasks':
        if status == 'DONE':
            row.completed_at = row.completed_at or now()
            row.progress = 100
        elif before and before['status'] == 'DONE':
            row.completed_at = None
            row.progress = min(row.progress, 99)
        if status == 'IN_PROGRESS':
            row.started_at = row.started_at or now()
    if kind in ('eco', 'issues'):
        row.closed_at = now() if status == 'CLOSED' else None
    if kind == 'milestones' and status == 'COMPLETED':
        row.actual_date = row.actual_date or datetime.now(timezone(timedelta(hours=9))).date()
    action = f'{kind.upper()}_CREATED' if before is None else f'{kind.upper()}_UPDATED'
    if before and status and status != before.get('status', before.get('implementation_status')):
        action = f'{kind.upper()}_{status}'
    audit(db, project.id, membership.user_id, kind, row, action, before)
    return row


def project_dashboard(db, project):
    data = {kind: list(db.scalars(select(model).where(model.project_id == project.id, model.is_deleted.is_(False))))
            for kind, model in MODELS.items() if kind not in ('projects', 'comments', 'documents')}
    today = datetime.now(timezone(timedelta(hours=9))).date()
    tasks = data['tasks']
    active = [t for t in tasks if t.status not in ('DONE', 'CANCELLED')]
    overdue = [t for t in active if t.due_date and t.due_date < today]
    task_map = {t.id: t for t in tasks}
    blocked_ids = set()
    for edge in data['dependencies']:
        successor = task_map.get(edge.successor_task_id)
        if edge.dependency_type in ('FF', 'SF') and successor and successor.status != 'REVIEW':
            continue
        predecessor = task_map.get(edge.predecessor_task_id)
        if not predecessor:
            blocked_ids.add(edge.successor_task_id)
            continue
        stamp = predecessor.completed_at if edge.dependency_type in ('FS', 'FF') else predecessor.started_at
        if stamp is None or stamp.date() + timedelta(days=edge.lag_days) > today:
            blocked_ids.add(edge.successor_task_id)
    waiting = [t for t in active if t.status in ('WAITING', 'BLOCKED', 'REVIEW') or t.blocker or t.id in blocked_ids]
    waiting_ids = {t.id for t in waiting}
    executable = [t for t in active if t.id not in waiting_ids and (t.start_date is None or t.start_date <= today)]
    unblockers = {e.predecessor_task_id for e in data['dependencies'] if e.successor_task_id in waiting_ids}
    rank = lambda t: (t.priority != 'P0', not t.critical_path, not (t.due_date and t.due_date < today),
                      t.id not in unblockers, t.due_date or date.max, t.priority, t.id)
    executable.sort(key=rank)
    now_tasks = [t for t in executable if t.priority in ('P0', 'P1') or t.status == 'IN_PROGRESS' or (t.due_date and t.due_date <= today)]
    next_tasks = [t for t in executable if t not in now_tasks and t.status == 'READY']
    later = [t for t in active if t not in now_tasks and t not in next_tasks and t not in waiting]
    relevant = [t for t in tasks if t.status != 'CANCELLED']
    progress = round(sum(t.progress for t in relevant) / len(relevant), 1) if relevant else project.progress_percent
    ready = sum(r.status == 'READY' for r in data['readiness'])
    readiness = round(ready / 14 * 100, 1)
    budget = sum((b.planned_amount for b in data['budget']), Decimal(0)) if data['budget'] else project.budget
    actual = sum((b.actual_amount for b in data['budget']), Decimal(0)) if data['budget'] else project.actual_cost
    risks = [r for r in data['risks'] if r.status != 'CLOSED']
    high = [r for r in risks if r.probability * r.impact >= 15]
    health = 'RED' if high or overdue or any(t.critical_path for t in waiting) or actual > budget else 'YELLOW' if waiting else project.health_status
    return {'project': snapshot(project), 'summary': {'progress': progress, 'd_day': (project.target_end_date - today).days if project.target_end_date else None,
        'health': health, 'open_tasks': len(active), 'overdue_tasks': len(overdue), 'blocked_tasks': len(waiting),
        'critical_tasks': sum(t.critical_path for t in active), 'open_issues': sum(i.status not in ('RESOLVED', 'CLOSED') for i in data['issues']),
        'high_risks': len(high), 'open_ecr': sum(e.status in ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW') for e in data['ecr']),
        'active_eco': sum(e.implementation_status not in ('CLOSED', 'FAILED') for e in data['eco']),
        'budget': str(budget), 'actual_cost': str(actual), 'budget_variance': str(budget - actual), 'readiness': readiness},
        'next_actions': [snapshot(t) for t in executable[:3]],
        'buckets': {k: [snapshot(t) for t in v] for k, v in {'NOW': now_tasks, 'NEXT': next_tasks, 'WAITING': waiting, 'LATER': later}.items()},
        'overdue': [snapshot(t) for t in overdue], 'critical': [snapshot(t) for t in active if t.critical_path],
        'risk_matrix': [[sum(r.probability == p and r.impact == i for r in risks) for i in range(1, 6)] for p in range(1, 6)],
        'milestones': [snapshot(m) for m in sorted(data['milestones'], key=lambda m: m.forecast_date or m.planned_date or date.max)],
        'changes': [snapshot(e) for e in data['ecr'] if e.status in ('SUBMITTED', 'UNDER_REVIEW')],
        'ecos': [snapshot(e) for e in data['eco'] if e.implementation_status not in ('CLOSED', 'FAILED')],
        'decisions': [snapshot(d) for d in sorted(data['decisions'], key=lambda d: d.id, reverse=True)[:5]]}
