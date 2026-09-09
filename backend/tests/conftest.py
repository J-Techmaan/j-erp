import os
import secrets
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

_startup_dir = tempfile.TemporaryDirectory(prefix='jerp-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + _startup_dir.name.replace('\\', '/') + '/startup.db'
os.environ['UPLOAD_DIR'] = _startup_dir.name + '/uploads'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_COOKIE_SECURE'] = 'false'
os.environ['CORS_ORIGINS'] = 'http://testserver'

from app.core.config import get_settings
from app.core.database import Base, get_db, make_engine
from app.main import app
from app.models import Group, GroupMembership, GroupRole, MembershipStatus

TEST_PASSWORD = secrets.token_urlsafe(20)


@pytest.fixture
def client(tmp_path):
    engine = make_engine('sqlite:///' + (tmp_path / 'test.db').as_posix())
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    get_settings().upload_dir = tmp_path / 'uploads'
    with TestClient(app, headers={'X-CSRF-Protection': '1'}) as client:
        client.session_factory = factory
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def users(client):
    result = []
    for i, name in enumerate(['홍길동', '김철수', '박영희', '최민수'], 1):
        client.cookies.clear()
        response = client.post('/api/auth/signup', json={
            'name': name, 'email': f'user{i}@example.com',
            'password': TEST_PASSWORD, 'password_confirm': TEST_PASSWORD,
        })
        assert response.status_code == 201, response.text
        result.append({'id': response.json()['id'], 'headers': {
            'Cookie': 'jerp_session=' + client.cookies.get('jerp_session'),
        }})
    with client.session_factory() as db:
        group = Group(name='테스트 그룹', code='TESTCODE', owner_id=result[0]['id'])
        db.add(group); db.flush()
        for index, item in enumerate(result):
            db.add(GroupMembership(group_id=group.id, user_id=item['id'], role=GroupRole.OWNER if index == 0 else GroupRole.MEMBER, status=MembershipStatus.ACTIVE))
        db.commit()
        group_id = group.id
    for item in result:
        item['headers']['X-Group-ID'] = str(group_id)
        item['group_id'] = group_id
    client.cookies.clear()
    return result


def pytest_sessionfinish(session, exitstatus):
    from app.core.database import engine
    engine.dispose()
    _startup_dir.cleanup()
