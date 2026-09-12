from datetime import date, timedelta

import pytest
from sqlalchemy import inspect, select

from app.core.database import Base, make_engine
from app.models.projects import ProjectActivity
from app.schemas.projects import SCHEMAS


def project(client, users, code='TEST-PROJECT'):
    response = client.post('/api/projects', headers=users[0]['headers'], json={'project_code': code, 'project_name': '테스트 프로젝트', 'target_end_date': '2027-03-15'})
    assert response.status_code == 201, response.text
    return response.json()


def create(client, users, p, kind, data):
    response = client.post(f"/api/projects/{p['id']}/{kind}", headers=users[0]['headers'], json=data)
    assert response.status_code == 201, response.text
    return response.json()


def update(client, users, p, kind, row, changes, index=0):
    payload = {key: row[key] for key in SCHEMAS[kind].model_fields}
    payload.update(changes, revision=row['revision'])
    return client.put(f"/api/projects/{p['id']}/{kind}/{row['id']}", headers=users[index]['headers'], json=payload)


def test_project_crud_permissions_and_group_isolation(client, users):
    p = project(client, users)
    path = f"/api/projects/{p['id']}"
    assert client.get(path, headers=users[1]['headers']).json()['can_manage'] is False
    payload = {key: p[key] for key in SCHEMAS['projects'].model_fields}
    payload.update(project_name='수정 프로젝트', revision=p['revision'])
    assert client.put(path, headers=users[1]['headers'], json=payload).status_code == 403
    changed = client.put(path, headers=users[0]['headers'], json=payload)
    assert changed.status_code == 200, changed.text
    assert client.put(path, headers=users[0]['headers'], json=payload).status_code == 409
    other = client.post('/api/groups', headers=users[0]['headers'], json={'name': '다른 그룹'}).json()
    foreign_headers = {**users[0]['headers'], 'X-Group-ID': str(other['id'])}
    assert client.get(path, headers=foreign_headers).status_code == 404
    assert client.get('/api/projects', headers=foreign_headers).json() == []
    assert client.delete(path, headers=users[1]['headers'], params={'revision': changed.json()['revision']}).status_code == 403
    assert client.delete(path, headers=users[0]['headers'], params={'revision': changed.json()['revision']}).status_code == 204
    assert client.get(path, headers=users[0]['headers']).status_code == 404


def test_seed_new_project_and_wbs_tree(client, users):
    p = client.post('/api/projects/seed/karaoke', headers=users[0]['headers']).json()
    assert p['project_code'].startswith('PRJ-')
    second = client.post('/api/projects/seed/karaoke', headers=users[0]['headers']).json()
    assert second['id'] != p['id']
    assert second['project_code'] != p['project_code']
    assert second['project_name'] == p['project_name']
    assert client.get(f"/api/projects/{p['id']}", headers=users[0]['headers']).json()['project_code'] == p['project_code']
    base = f"/api/projects/{p['id']}"
    wbs = client.get(base + '/wbs', headers=users[0]['headers']).json()
    assert len(wbs) == 14
    child = create(client, users, p, 'wbs', {'title': '하위 작업', 'wbs_code': '1.1', 'parent_id': wbs[0]['id']})
    assert child['parent_id'] == wbs[0]['id']
    assert update(client, users, p, 'wbs', wbs[0], {'parent_id': child['id']}).status_code == 422
    assert client.delete(base + f"/wbs/{wbs[0]['id']}", headers=users[0]['headers'], params={'revision': wbs[0]['revision']}).status_code == 409
    readiness = client.get(base + '/readiness', headers=users[0]['headers']).json()
    assert len(readiness) == 14
    for r in readiness:
        assert update(client, users, p, 'readiness', r, {'status': 'READY'}).status_code == 200
    assert client.get(base + '/dashboard', headers=users[0]['headers']).json()['summary']['readiness'] == 100


def test_task_dependencies_cycles_warning_and_approval(client, users):
    p = project(client, users)
    first = create(client, users, p, 'tasks', {'task_code': 'T1', 'title': '선행'})
    second = create(client, users, p, 'tasks', {'task_code': 'T2', 'title': '후속', 'approval_required': True})
    create(client, users, p, 'dependencies', {'predecessor_task_id': first['id'], 'successor_task_id': second['id'], 'dependency_type': 'FS'})
    path = f"/api/projects/{p['id']}/dependencies"
    assert client.post(path, headers=users[0]['headers'], json={'predecessor_task_id': second['id'], 'successor_task_id': first['id']}).status_code == 422
    assert update(client, users, p, 'tasks', first, {'status': 'DONE'}).status_code == 409
    warning = update(client, users, p, 'tasks', second, {'status': 'IN_PROGRESS'})
    assert warning.status_code == 409
    assert warning.json()['detail']['code'] == 'DEPENDENCY_WARNING'
    started = update(client, users, p, 'tasks', second, {'status': 'IN_PROGRESS', 'acknowledge_dependencies': True}).json()
    assert started['started_at']
    assert update(client, users, p, 'tasks', started, {'approval_required': False}, index=1).status_code == 403
    assert update(client, users, p, 'tasks', started, {'status': 'DONE'}, index=1).status_code == 403
    assert update(client, users, p, 'tasks', started, {'status': 'DONE'}).status_code == 409
    first = update(client, users, p, 'tasks', first, {'status': 'IN_PROGRESS'}).json()
    first = update(client, users, p, 'tasks', first, {'status': 'DONE'}).json()
    done = update(client, users, p, 'tasks', started, {'status': 'DONE'}).json()
    assert done['progress'] == 100 and done['completed_at']
    assert update(client, users, p, 'tasks', started, {'status': 'DONE'}).status_code == 409


@pytest.mark.parametrize('dependency_type', ['SS', 'FF', 'SF'])
def test_dependency_types_and_lag(client, users, dependency_type):
    p = project(client, users)
    first = create(client, users, p, 'tasks', {'task_code': 'A', 'title': 'A'})
    second = create(client, users, p, 'tasks', {'task_code': 'B', 'title': 'B'})
    create(client, users, p, 'dependencies', {'predecessor_task_id': first['id'], 'successor_task_id': second['id'], 'dependency_type': dependency_type, 'lag_days': 2})
    first = update(client, users, p, 'tasks', first, {'status': 'IN_PROGRESS'}).json()
    first = update(client, users, p, 'tasks', first, {'status': 'DONE'}).json()
    second = update(client, users, p, 'tasks', second, {'status': 'IN_PROGRESS', 'acknowledge_dependencies': True}).json()
    assert update(client, users, p, 'tasks', second, {'status': 'DONE'}).json()['detail']['code'] == 'DEPENDENCY_WARNING'


def test_ecr_eco_approval_and_immutable_audit(client, users):
    p = project(client, users)
    ecr = create(client, users, p, 'ecr', {'title': '일정 변경', 'reason': '허가 일정 변경'})
    eco_payload = {'linked_ecr': ecr['id'], 'title': '일정 반영', 'implementation_plan': '변경 일정 공지'}
    assert client.post(f"/api/projects/{p['id']}/eco", headers=users[0]['headers'], json=eco_payload).status_code == 409
    ecr = update(client, users, p, 'ecr', ecr, {'status': 'SUBMITTED'}).json()
    ecr = update(client, users, p, 'ecr', ecr, {'status': 'UNDER_REVIEW'}).json()
    assert update(client, users, p, 'ecr', ecr, {'status': 'APPROVED', 'decision': '동의'}, index=1).status_code == 403
    assert update(client, users, p, 'ecr', ecr, {'status': 'APPROVED'}).status_code == 422
    ecr = update(client, users, p, 'ecr', ecr, {'status': 'APPROVED', 'decision': '영향 검토 완료'}).json()
    assert ecr['reviewer'] == users[0]['id']
    assert update(client, users, p, 'ecr', ecr, {'reason': '변조'}).status_code == 409
    eco = create(client, users, p, 'eco', eco_payload)
    assert client.post(f"/api/projects/{p['id']}/eco", headers=users[0]['headers'], json=eco_payload).status_code == 409
    eco = update(client, users, p, 'eco', eco, {'implementation_status': 'IMPLEMENTING'}).json()
    eco = update(client, users, p, 'eco', eco, {'implementation_status': 'VERIFYING'}).json()
    assert update(client, users, p, 'eco', eco, {'implementation_status': 'CLOSED'}).status_code == 422
    eco = update(client, users, p, 'eco', eco, {'implementation_status': 'CLOSED', 'after_state': '일정 반영', 'verification_result': '검토 통과'}).json()
    assert eco['closed_at']
    with client.session_factory() as db:
        entries = db.scalars(select(ProjectActivity).where(ProjectActivity.project_id == p['id'])).all()
        approved = next(e for e in entries if e.action == 'ECR_APPROVED')
        assert approved.before['status'] == 'UNDER_REVIEW' and approved.after['status'] == 'APPROVED'
        assert any(e.action == 'ECO_CLOSED' for e in entries)
    assert client.delete(f"/api/projects/{p['id']}/activity/1", headers=users[0]['headers'], params={'revision': 1}).status_code == 404


def test_logs_budget_dashboard_and_references(client, users):
    p = project(client, users)
    task = create(client, users, p, 'tasks', {'task_code': 'URGENT', 'title': '계약 검토', 'priority': 'P0', 'critical_path': True, 'due_date': str(date.today() - timedelta(days=1))})
    issue = create(client, users, p, 'issues', {'title': '공사 지연', 'linked_task': task['id']})
    assert update(client, users, p, 'issues', issue, {'status': 'RESOLVED'}).status_code == 422
    assert update(client, users, p, 'issues', issue, {'status': 'RESOLVED', 'resolution': '추가 인력 투입'}).status_code == 200
    risk = create(client, users, p, 'risks', {'title': '지연 위험', 'probability': 4, 'impact': 5})
    assert risk['risk_score'] == 20
    create(client, users, p, 'decisions', {'title': '위치 결정', 'decision': 'A점포', 'rationale': '유동인구'})
    create(client, users, p, 'milestones', {'milestone_code': 'OPEN', 'name': '오픈', 'planned_date': '2027-03-15'})
    vendor = create(client, users, p, 'vendors', {'name': '인테리어 업체'})
    budget = create(client, users, p, 'budget', {'title': '공사', 'vendor_id': vendor['id'], 'planned_amount': '100.00', 'actual_amount': '40.25'})
    assert update(client, users, p, 'budget', budget, {'actual_amount': 20}, index=1).status_code == 403
    feed = client.get(f"/api/projects/{p['id']}/dashboard", headers=users[1]['headers']).json()
    assert feed['summary']['budget_variance'] == '59.75'
    assert feed['summary']['high_risks'] == 1 and feed['risk_matrix'][3][4] == 1
    assert feed['summary']['overdue_tasks'] == 1 and feed['summary']['health'] == 'RED'
    assert feed['next_actions'][0]['id'] == task['id'] and len(feed['next_actions']) <= 3
    other = project(client, users, 'OTHER')
    assert client.post(f"/api/projects/{other['id']}/issues", headers=users[0]['headers'], json={'title': '교차 프로젝트', 'linked_task': task['id']}).status_code == 404
    comment = create(client, users, p, 'comments', {'task_id': task['id'], 'content': '진행 보고'})
    assert update(client, users, p, 'comments', comment, {'content': '위조'}, index=1).status_code == 403


def test_additive_migration_preserves_legacy_data(tmp_path):
    from app.models import User
    engine = make_engine('sqlite:///' + (tmp_path / 'legacy.db').as_posix())
    legacy = [t for t in Base.metadata.sorted_tables if not t.name.startswith('project')]
    Base.metadata.create_all(engine, tables=legacy)
    with engine.begin() as connection:
        connection.execute(User.__table__.insert(), {'id': 1, 'username': 'legacy', 'display_name': '기존 사용자', 'is_active': True})
    Base.metadata.create_all(engine)
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        assert connection.execute(select(User.display_name)).scalar() == '기존 사용자'
    assert 'project_tasks' in inspect(engine).get_table_names()
    engine.dispose()


def test_group_document_archive_for_uninvolved_member(client, users):
    doc = client.post('/api/documents', headers=users[0]['headers'], json={'title': '공유 문서', 'steps': [{'user_id': users[1]['id']}]}).json()
    path = f"/api/documents/{doc['id']}"
    uploaded = client.post(path + '/attachments', headers=users[0]['headers'], data={'revision': doc['revision']}, files={'file': ('note.txt', b'group attachment', 'text/plain')}).json()
    doc = client.get(path, headers=users[0]['headers']).json()
    assert client.get('/api/documents?scope=group', headers=users[2]['headers']).json() == []
    assert client.get(path, headers=users[2]['headers']).status_code == 404
    doc = client.post(path + '/submit', headers=users[0]['headers'], json={'revision': doc['revision']}).json()
    assert client.get('/api/documents?scope=group', headers=users[2]['headers']).json()[0]['id'] == doc['id']
    assert client.get(path, headers=users[2]['headers']).status_code == 200
    assert client.get(f"/api/attachments/{uploaded['id']}/download", headers=users[2]['headers']).content == b'group attachment'
    assert client.post(path + '/approve', headers=users[2]['headers'], json={'revision': doc['revision']}).status_code == 403
    doc = client.post(path + '/approve', headers=users[1]['headers'], json={'revision': doc['revision']}).json()
    assert doc['status'] == 'COMPLETED'
    assert client.get('/api/documents?scope=group&status=COMPLETED', headers=users[2]['headers']).json()[0]['id'] == doc['id']


def test_supporting_record_crud_and_milestone_completion(client, users):
    p = project(client, users)
    samples = {
        'vendors': {'name': '협력사'},
        'budget': {'title': '예산', 'planned_amount': '10.25'},
        'risks': {'title': '위험'},
        'issues': {'title': '이슈'},
        'decisions': {'title': '결정', 'decision': '시행', 'rationale': '검토 완료'},
        'milestones': {'name': '완료 시점', 'milestone_code': 'M1'},
        'readiness': {'category': 'LEGAL'},
    }
    for kind, data in samples.items():
        row = create(client, users, p, kind, data)
        path = f"/api/projects/{p['id']}/{kind}/{row['id']}"
        assert client.get(path, headers=users[1]['headers']).status_code == 200
        changes = {'status': 'COMPLETED'} if kind == 'milestones' else {}
        response = update(client, users, p, kind, row, changes)
        assert response.status_code == 200, response.text
        if kind == 'milestones':
            assert response.json()['actual_date']
        assert client.delete(path, headers=users[0]['headers'], params={'revision': response.json()['revision']}).status_code == 204
        assert client.get(path, headers=users[1]['headers']).status_code == 404


def test_codes_are_generated_and_preserved(client, users):
    p = project(client, users, 'MANUAL')
    assert p['project_code'].startswith('PRJ-')
    other = project(client, users, 'MANUAL')
    assert other['project_code'] != p['project_code']
    payload = {key: p[key] for key in SCHEMAS['projects'].model_fields}
    payload.update(project_code='REPLACE', revision=p['revision'])
    response = client.put(f"/api/projects/{p['id']}", headers=users[0]['headers'], json=payload)
    assert response.status_code == 200
    assert response.json()['project_code'] == p['project_code']
    for kind, field, prefix, values in [
        ('wbs', 'wbs_code', 'WBS-', {'title': '자동 WBS'}),
        ('tasks', 'task_code', 'TASK-', {'title': '자동 액션'}),
        ('milestones', 'milestone_code', 'MS-', {'name': '자동 마일스톤'}),
    ]:
        row = create(client, users, p, kind, values)
        assert row[field].startswith(prefix)
        second = create(client, users, p, kind, {**values, field: row[field]})
        assert second[field] != row[field]
        changed = update(client, users, p, kind, row, {field: 'REPLACE'})
        assert changed.status_code == 200
        assert changed.json()[field] == row[field]
