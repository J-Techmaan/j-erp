from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.models import Document, User, now
from app.repositories.documents import get_document
from app.schemas import ActionIn
from app.services.approvals import act


def create(client, users, steps=None):
    response = client.post('/api/documents', headers=users[0]['headers'], json={'title': '장비 구매 요청', 'content': '모니터 2대 구매', 'steps': steps if steps is not None else [{'user_id': users[1]['id'], 'approval_type': 'APPROVAL'}, {'user_id': users[3]['id'], 'approval_type': 'NOTIFICATION'}, {'user_id': users[2]['id'], 'approval_type': 'AGREEMENT'}]})
    assert response.status_code == 201, response.text
    return response.json()


def action(client, doc, user, name, comment=''):
    return client.post(f"/api/documents/{doc['id']}/{name}", headers=user['headers'], json={'revision': doc['revision'], 'comment': comment})


def test_sequential_approval_and_notification(client, users):
    doc = create(client, users)
    assert doc['status'] == 'DRAFT'
    assert client.get(f"/api/documents/{doc['id']}", headers=users[1]['headers']).status_code == 404
    saved = client.put(f"/api/documents/{doc['id']}", headers=users[0]['headers'], json={'title': '수정된 요청', 'content': '내용 저장', 'steps': [{'user_id': s['user_id'], 'approval_type': s['approval_type']} for s in doc['steps']], 'revision': doc['revision']})
    assert saved.status_code == 200, saved.text
    doc = saved.json()
    assert doc['content'] == '내용 저장'
    doc = action(client, doc, users[0], 'submit').json()
    assert doc['status'] == 'IN_PROGRESS'
    assert [s['status'] for s in doc['steps']] == ['CURRENT', 'WAITING', 'WAITING']
    assert len(client.get('/api/approvals/pending', headers=users[1]['headers']).json()) == 1
    assert client.get('/api/approvals/pending', headers=users[2]['headers']).json() == []
    for index in [0, 2, 3]:
        assert action(client, doc, users[index], 'approve').status_code == 403
    old = doc
    doc = action(client, doc, users[1], 'approve', '확인했습니다.').json()
    assert [s['status'] for s in doc['steps']] == ['APPROVED', 'WAITING', 'CURRENT']
    assert action(client, old, users[1], 'approve').status_code == 409
    assert action(client, doc, users[1], 'approve').status_code == 403
    assert len(client.get('/api/approvals/pending', headers=users[2]['headers']).json()) == 1
    doc = action(client, doc, users[2], 'approve').json()
    assert doc['status'] == 'COMPLETED' and doc['completed_at']
    assert [s['status'] for s in doc['steps']] == ['APPROVED', 'NOTIFIED', 'APPROVED']
    assert client.get('/api/approvals/pending', headers=users[2]['headers']).json() == []
    assert len(client.get('/api/approvals/history', headers=users[1]['headers']).json()) == 1
    notified = client.get('/api/documents?scope=notified', headers=users[3]['headers']).json()
    assert notified[0]['status'] == 'COMPLETED'
    assert action(client, doc, users[2], 'approve').status_code == 409
    assert action(client, doc, users[0], 'submit').status_code == 409


def test_rejection_closes_original_and_recreate_preserves_history(client, users):
    original = create(client, users)
    submitted = client.post(f"/api/documents/{original['id']}/submit", headers=users[0]['headers'], json={'revision': original['revision'], 'message': '검토 부탁드립니다.'})
    doc = submitted.json()
    assert doc['history'][-1]['comment'] == '검토 부탁드립니다.'
    assert action(client, doc, users[1], 'reject', ' ').status_code == 422
    doc = action(client, doc, users[1], 'reject', '견적서를 보완하세요.').json()
    assert doc['status'] == 'REJECTED'
    assert doc['rejected_at'] and doc['rejector_id'] == users[1]['id']
    assert doc['steps'][0]['status'] == 'REJECTED'
    assert doc['steps'][2]['status'] == 'WAITING'
    assert doc['steps'][1]['status'] == 'NOTIFIED'
    assert client.get('/api/approvals/pending', headers=users[1]['headers']).json() == []
    assert action(client, doc, users[2], 'approve').status_code == 409
    assert client.put(f"/api/documents/{doc['id']}", headers=users[0]['headers'], json={'title': doc['title'], 'content': '수정 시도', 'steps': [], 'revision': doc['revision']}).status_code == 409
    notified = client.get('/api/documents?scope=notified', headers=users[3]['headers']).json()
    assert notified[0]['status'] == 'REJECTED'
    copy = client.post(f"/api/documents/{doc['id']}/recreate", headers=users[0]['headers']).json()
    assert copy['id'] != doc['id'] and copy['source_document_id'] == doc['id']
    assert copy['status'] == 'DRAFT' and copy['title'] == doc['title'] and copy['content'] == doc['content']
    assert [(s['user_id'], s['approval_type']) for s in copy['steps']] == [(s['user_id'], s['approval_type']) for s in doc['steps']]
    original_again = client.get(f"/api/documents/{doc['id']}", headers=users[0]['headers']).json()
    assert original_again['status'] == 'REJECTED'
    assert any(h['comment'] == '견적서를 보완하세요.' for h in original_again['history'])


def test_submission_cancellation_permissions_closure_and_recreation(client, users):
    draft = create(client, users)
    cancel_path = f"/api/documents/{draft['id']}/cancel"
    assert client.post(cancel_path, headers=users[0]['headers'], json={'revision': draft['revision']}).status_code == 409
    doc = action(client, draft, users[0], 'submit').json()
    assert client.post(cancel_path, headers=users[1]['headers'], json={'revision': doc['revision']}).status_code == 403
    cancelled = client.post(cancel_path, headers=users[0]['headers'], json={'revision': doc['revision']}).json()
    assert cancelled['status'] == 'CANCELLED' and cancelled['cancelled_at']
    assert cancelled['history'][-1]['action'] == 'CANCELLED'
    assert client.post(cancel_path, headers=users[0]['headers'], json={'revision': cancelled['revision']}).status_code == 409
    assert action(client, cancelled, users[1], 'approve').status_code == 409
    assert action(client, cancelled, users[1], 'reject', '취소 문서').status_code == 409
    authored = client.get('/api/documents?scope=authored', headers=users[0]['headers']).json()
    assert any(item['id'] == cancelled['id'] and item['status'] == 'CANCELLED' for item in authored)
    copy = client.post(f"/api/documents/{cancelled['id']}/recreate", headers=users[0]['headers']).json()
    assert copy['id'] != cancelled['id'] and copy['status'] == 'DRAFT'
    assert copy['source_document_id'] == cancelled['id'] and copy['title'] == cancelled['title']
    assert [(s['user_id'], s['approval_type']) for s in copy['steps']] == [(s['user_id'], s['approval_type']) for s in cancelled['steps']]
    assert client.get(f"/api/documents/{cancelled['id']}", headers=users[0]['headers']).json()['status'] == 'CANCELLED'

    completed = action(client, create(client, users, [{'user_id': users[1]['id']}]), users[0], 'submit').json()
    completed = action(client, completed, users[1], 'approve').json()
    assert client.post(f"/api/documents/{completed['id']}/cancel", headers=users[0]['headers'], json={'revision': completed['revision']}).status_code == 409

    rejected = action(client, create(client, users), users[0], 'submit').json()
    rejected = action(client, rejected, users[1], 'reject', '반려').json()
    assert client.post(f"/api/documents/{rejected['id']}/cancel", headers=users[0]['headers'], json={'revision': rejected['revision']}).status_code == 409


def test_attachments_and_access_control(client, users):
    doc = create(client, users, [{'user_id': users[1]['id'], 'approval_type': 'APPROVAL'}])
    path = f"/api/documents/{doc['id']}/attachments"
    uploaded = client.post(path, headers=users[0]['headers'], data={'revision': doc['revision']}, files={'file': ('견적.txt', b'quotation', 'text/plain')})
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()
    assert 'file_path' not in attachment
    download = f"/api/attachments/{attachment['id']}/download"
    assert client.get(download, headers=users[0]['headers']).content == b'quotation'
    assert client.get(download, headers=users[3]['headers']).status_code == 404
    doc = client.get(f"/api/documents/{doc['id']}", headers=users[0]['headers']).json()
    assert len(doc['attachments']) == 1
    assert client.post(path, headers=users[0]['headers'], data={'revision': doc['revision']}, files={'file': ('bad.exe', b'bad')}).status_code == 422
    settings = get_settings()
    previous = settings.max_upload_bytes
    settings.max_upload_bytes = 4
    try:
        assert client.post(path, headers=users[0]['headers'], data={'revision': doc['revision']}, files={'file': ('large.txt', b'12345')}).status_code == 413
    finally:
        settings.max_upload_bytes = previous
    assert len(list(settings.upload_dir.iterdir())) == 1
    doc = action(client, doc, users[0], 'submit').json()
    assert client.get(download, headers=users[1]['headers']).content == b'quotation'
    assert client.post(path, headers=users[0]['headers'], data={'revision': doc['revision']}, files={'file': ('late.txt', b'late')}).status_code == 409


@pytest.mark.parametrize('steps', [[], [{'user_id': 4, 'approval_type': 'NOTIFICATION'}]])
def test_requires_actual_approver(client, users, steps):
    doc = create(client, users, steps)
    assert action(client, doc, users[0], 'submit').status_code == 422


def test_validation_and_auth(client, users):
    assert client.get('/api/users/me').status_code == 401
    assert client.get('/api/users/me', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong-password'}).status_code == 401
    for title, steps in [(' ', []), ('ok', [{'user_id': 999}]), ('ok', [{'user_id': 2}, {'user_id': 2}])]:
        assert client.post('/api/documents', headers=users[0]['headers'], json={'title': title, 'steps': steps}).status_code == 422
    doc = action(client, create(client, users), users[0], 'submit').json()
    assert action(client, doc, users[1], 'submit').status_code == 403
    assert client.put(f"/api/documents/{doc['id']}", headers=users[0]['headers'], json={'title': 'no', 'revision': doc['revision']}).status_code == 409
    assert client.get('/api/users/search', params={'q': '김', 'group_id': users[0]['group_id']}, headers=users[0]['headers']).json()[0]['display_name'] == '김철수'
    assert client.get('/api/users/search', params={'q': '%', 'group_id': users[0]['group_id']}, headers=users[0]['headers']).json() == []
    with client.session_factory() as db:
        db.get(User, users[1]['id']).is_active = False
        db.commit()
    assert client.get('/api/users/me', headers=users[1]['headers']).status_code == 401


def test_personal_schedule_crud(client, users):
    data = {'title': '회의', 'description': '주간 회의', 'start_at': '2026-09-07T10:00:00+09:00', 'end_at': '2026-09-07T11:00:00+09:00', 'all_day': False}
    response = client.post('/api/schedules', headers=users[0]['headers'], json=data)
    assert response.status_code == 201
    schedule = response.json()
    assert schedule['start_at'] == '2026-09-07T01:00:00Z'
    params = {'start': '2026-09-01T00:00:00+09:00', 'end': '2026-10-01T00:00:00+09:00'}
    assert len(client.get('/api/schedules', params=params, headers=users[0]['headers']).json()) == 1
    assert len(client.get('/api/schedules', params=params, headers=users[1]['headers']).json()) == 1
    path = f"/api/schedules/{schedule['id']}"
    assert client.put(path, headers=users[1]['headers'], json=data).status_code == 404
    assert client.delete(path, headers=users[1]['headers']).status_code == 404
    assert client.put(path, headers=users[0]['headers'], json={**data, 'title': '수정된 회의'}).json()['title'] == '수정된 회의'
    assert client.post('/api/schedules', headers=users[0]['headers'], json={**data, 'end_at': '2026-09-06T00:00:00Z'}).status_code == 422
    assert client.delete(path, headers=users[0]['headers']).status_code == 204


def test_legacy_mock_endpoints_removed(client):
    assert client.get('/api/auth/mock-users').status_code == 404
    assert client.post('/api/auth/mock-login', json={'username': 'user1'}).status_code == 404


def test_stale_transaction_rolls_back_steps_and_history(client, users):
    doc = action(client, create(client, users), users[0], 'submit').json()
    with client.session_factory() as first, client.session_factory() as second:
        a = get_document(first, doc['id'], users[1]['id'])
        b = get_document(second, doc['id'], users[1]['id'])
        act(first, a, users[1]['id'], ActionIn(revision=doc['revision']))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as conflict:
            act(second, b, users[1]['id'], ActionIn(revision=doc['revision']))
        assert conflict.value.status_code == 409
    final = client.get(f"/api/documents/{doc['id']}", headers=users[0]['headers']).json()
    assert [s['status'] for s in final['steps']] == ['APPROVED', 'WAITING', 'CURRENT']
    assert len([h for h in final['history'] if h['action'] == 'APPROVED']) == 1


def test_simultaneous_duplicate_requests(client, users):
    doc = action(client, create(client, users), users[0], 'submit').json()
    barrier = Barrier(2)

    def approve():
        barrier.wait()
        return action(client, doc, users[1], 'approve').status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))
    assert sorted(results) == [200, 409]
