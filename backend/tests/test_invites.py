from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import GroupInvite, GroupMembership, now


def test_invite_permissions_acceptance_and_memberships(client, users):
    group = client.post('/api/groups', headers=users[0]['headers'], json={'name': '초대 그룹'}).json()
    path = f"/api/groups/{group['id']}/invites"
    assert client.post(path, headers=users[1]['headers']).status_code == 403
    response = client.post(path, headers=users[0]['headers'])
    assert response.status_code == 201
    token = response.json()['token']
    assert len(token) >= 32
    assert client.get(f'/api/invites/{token}').json()['group_name'] == '초대 그룹'
    assert client.post(f'/api/invites/{token}/accept').status_code == 401
    for _ in range(2):
        assert client.post(f'/api/invites/{token}/accept', headers=users[1]['headers']).status_code == 200
    assert len(client.get('/api/groups', headers=users[1]['headers']).json()) == 2
    with client.session_factory() as db:
        memberships = db.scalars(select(GroupMembership).where(GroupMembership.group_id == group['id'], GroupMembership.user_id == users[1]['id'])).all()
        assert len(memberships) == 1
        member_id = memberships[0].id
    assert client.post(path, headers=users[1]['headers']).status_code == 403
    client.put(f"/api/groups/{group['id']}/members/{member_id}/admin", headers=users[0]['headers'], json={'is_admin': True})
    assert client.post(path, headers=users[1]['headers']).status_code == 201


@pytest.mark.parametrize('state', ['invalid', 'expired', 'inactive', 'deleted_group'])
def test_unavailable_invites(client, users, state):
    group_id = users[0]['group_id']
    token = client.post(f'/api/groups/{group_id}/invites', headers=users[0]['headers']).json()['token']
    if state == 'invalid':
        token = 'missing'
    elif state == 'deleted_group':
        client.delete(f'/api/groups/{group_id}', headers=users[0]['headers'])
    else:
        with client.session_factory() as db:
            invite = db.scalar(select(GroupInvite).where(GroupInvite.token == token))
            if state == 'expired':
                invite.expires_at = now() - timedelta(seconds=1)
            else:
                invite.is_active = False
            db.commit()
    expected = 404 if state == 'invalid' else 410
    assert client.get(f'/api/invites/{token}').status_code == expected
    assert client.post(f'/api/invites/{token}/accept', headers=users[1]['headers']).status_code == expected
