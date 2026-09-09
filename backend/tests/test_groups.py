def signup(client, email, name):
    password = 'Group-test-password-42'
    response = client.post('/api/auth/signup', json={'email': email, 'name': name, 'password': password, 'password_confirm': password})
    assert response.status_code == 201
    return {'id': response.json()['id'], 'cookie': client.cookies.get('jerp_session')}


def headers(user, group_id=None):
    result = {'Cookie': 'jerp_session=' + user['cookie']}
    if group_id: result['X-Group-ID'] = str(group_id)
    return result


def test_group_create_join_approval_roles_and_scoping(client):
    owner = signup(client, 'owner@example.com', '그룹장')
    client.cookies.clear()
    member = signup(client, 'member@example.com', '가입자')
    client.cookies.clear()
    outsider = signup(client, 'outsider@example.com', '외부인')
    client.cookies.clear()

    created = client.post('/api/groups', headers=headers(owner), json={'name': '개발팀'})
    assert created.status_code == 201
    group = created.json()
    assert group['my_role'] == 'OWNER' and len(group['code']) == 8
    assert client.get('/api/groups', headers=headers(member)).json() == []
    joined = client.post('/api/groups/join', headers=headers(member), json={'code': group['code'].lower()})
    assert joined.status_code == 201
    assert client.post('/api/groups/join', headers=headers(member), json={'code': group['code']}).status_code == 409
    pending = client.get(f"/api/groups/{group['id']}/pending", headers=headers(owner)).json()
    assert pending[0]['user']['display_name'] == '가입자'
    assert client.post(f"/api/groups/{group['id']}/members/{pending[0]['id']}/approve", headers=headers(member)).status_code == 403
    assert client.post(f"/api/groups/{group['id']}/members/{pending[0]['id']}/approve", headers=headers(owner)).status_code == 200
    assert client.get('/api/groups', headers=headers(member)).json()[0]['my_role'] == 'MEMBER'

    search = client.get('/api/users/search', headers=headers(member), params={'group_id': group['id'], 'q': ''})
    assert {u['display_name'] for u in search.json()} == {'그룹장', '가입자'}
    assert client.get('/api/users/search', headers=headers(outsider), params={'group_id': group['id'], 'q': ''}).status_code == 403
    document = client.post('/api/documents', headers=headers(owner, group['id']), json={'title': '그룹 문서', 'steps': [{'user_id': member['id']}]})
    assert document.status_code == 201
    assert client.get('/api/documents', headers=headers(outsider, group['id'])).status_code == 403
    assert client.post('/api/documents', headers=headers(owner), json={'title': '그룹 없는 문서'}).status_code == 400

    detail = client.get(f"/api/groups/{group['id']}", headers=headers(owner)).json()
    member_row = next(item for item in detail['members'] if item['user']['id'] == member['id'])
    assert client.delete(f"/api/groups/{group['id']}/members/{member_row['id']}", headers=headers(member)).status_code == 403
    assert client.delete(f"/api/groups/{group['id']}/members/{member_row['id']}", headers=headers(owner)).status_code == 204
    assert client.get('/api/groups', headers=headers(member)).json() == []


def test_member_can_invite_and_multiple_groups_are_isolated(client):
    owner = signup(client, 'multi@example.com', '여러 그룹장')
    first = client.post('/api/groups', headers=headers(owner), json={'name': '첫 그룹'}).json()
    second = client.post('/api/groups', headers=headers(owner), json={'name': '둘째 그룹'}).json()
    assert len(client.get('/api/groups', headers=headers(owner)).json()) == 2
    first_schedule = {'title': '첫 그룹 일정', 'description': '', 'start_at': '2026-09-07T00:00:00Z', 'end_at': '2026-09-07T01:00:00Z', 'all_day': False}
    assert client.post('/api/schedules', headers=headers(owner, first['id']), json=first_schedule).status_code == 201
    params = {'start': '2026-09-01T00:00:00Z', 'end': '2026-10-01T00:00:00Z'}
    assert len(client.get('/api/schedules', headers=headers(owner, first['id']), params=params).json()) == 1
    assert client.get('/api/schedules', headers=headers(owner, second['id']), params=params).json() == []
    # Every active member can share the group code; no privileged endpoint is needed.
    assert client.get(f"/api/groups/{first['id']}", headers=headers(owner)).json()['code'] == first['code']

def test_group_admin_permissions_are_scoped(client, users):
    from app.models import GroupMembership
    group_id = users[0]['group_id']
    with client.session_factory() as db:
        from sqlalchemy import select
        member = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group_id, GroupMembership.user_id == users[1]['id']))
        member_id = member.id
    path = f'/api/groups/{group_id}/members/{member_id}/admin'
    assert client.put(path, headers=users[1]['headers'], json={'is_admin': True}).status_code == 403
    assert client.put(path, headers=users[0]['headers'], json={'is_admin': True}).json()['is_admin'] is True
    assert client.get(f'/api/groups/{group_id}/pending', headers=users[1]['headers']).status_code == 200
    assert client.delete(f'/api/groups/{group_id}', headers=users[1]['headers']).status_code == 403
    other = client.post('/api/groups', headers=users[0]['headers'], json={'name': '다른 그룹'}).json()
    assert client.get(f"/api/groups/{other['id']}/pending", headers=users[1]['headers']).status_code == 403
    assert client.put(path, headers=users[0]['headers'], json={'is_admin': False}).json()['is_admin'] is False
    assert client.get(f'/api/groups/{group_id}/pending', headers=users[1]['headers']).status_code == 403
