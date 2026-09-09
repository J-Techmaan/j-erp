from datetime import timedelta
from hashlib import sha256
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.main import app
from app.models import AuthAccount, AuthSession, User, now
from app.services.identity import password_hasher


def signup(client, **overrides):
    password = 'Valid-test-password-42'
    return client.post('/api/auth/signup', json={
        'email': 'member@example.com', 'name': '테스트 회원',
        'password': password, 'password_confirm': password, **overrides,
    })


def login(client, **overrides):
    return client.post('/api/auth/login', json={
        'email': 'member@example.com', 'password': 'Valid-test-password-42', **overrides,
    })


def test_signup_hashes_credentials_and_uses_httponly_cookie(client):
    response = signup(client)
    assert response.status_code == 201, response.text
    assert response.json()['email'] == 'member@example.com'
    assert response.json()['display_name'] == '테스트 회원'
    assert 'password' not in response.text and 'access_token' not in response.text
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/api' in cookie
    assert 'max-age' not in cookie
    token = client.cookies.get('jerp_session')
    with client.session_factory() as db:
        account = db.scalar(select(AuthAccount))
        assert account.provider == 'local'
        assert account.password_hash.startswith('$argon2id$')
        assert password_hasher.verify(account.password_hash, 'Valid-test-password-42')
        session = db.scalar(select(AuthSession))
        assert session.token_hash != token
        assert session.token_hash == sha256(token.encode()).hexdigest()
    assert client.get('/api/auth/me').json()['id'] == response.json()['id']
    assert client.get('/api/users/me').json()['id'] == response.json()['id']


def test_signup_eight_character_password_boundary(client):
    assert signup(client, password='Abcd123', password_confirm='Abcd123').status_code == 422
    assert signup(client, password='Abcd1234', password_confirm='Abcd1234').status_code == 201
    assert login(client, password='Abcd1234').status_code == 200


def test_remember_session_rotation_and_logout_revocation(client):
    signup(client)
    old_token = client.cookies.get('jerp_session')
    response = login(client, remember_me=True)
    assert response.status_code == 200
    assert f'max-age={30 * 86400}' in response.headers['set-cookie'].lower()
    token = client.cookies.get('jerp_session')
    assert token != old_token
    assert client.get('/api/auth/me', headers={'Cookie': f'jerp_session={old_token}'}).status_code == 401
    # A new application client can restore the session using only the cookie.
    with TestClient(app) as other:
        assert other.get('/api/auth/me', headers={'Cookie': f'jerp_session={token}'}).status_code == 200
    response = client.post('/api/auth/logout')
    assert response.status_code == 204
    assert 'max-age=0' in response.headers['set-cookie'].lower()
    assert client.get('/api/auth/me', headers={'Cookie': f'jerp_session={token}'}).status_code == 401
    assert client.post('/api/auth/logout').status_code == 204


def test_email_normalization_duplicates_and_generic_login_errors(client):
    assert signup(client, email=' Member@EXAMPLE.com ').status_code == 201
    duplicate = signup(client, email='member@example.com')
    assert duplicate.status_code == 409
    assert 'password' not in duplicate.text
    assert login(client, email='MEMBER@example.COM').status_code == 200
    bad_password = login(client, password='wrong-password').json()
    unknown = login(client, email='nobody@example.com').json()
    assert bad_password == unknown
    with client.session_factory() as db:
        db.scalar(select(User)).is_active = False
        db.commit()
    assert client.get('/api/auth/me').status_code == 401
    assert login(client).json() == unknown


@pytest.mark.parametrize('data', [
    {'email': 'invalid'}, {'name': '   '}, {'name': 'a' * 101},
    {'password': 'short', 'password_confirm': 'short'},
    {'password_confirm': 'not-matching'},
    {'password': ' ' * 12, 'password_confirm': ' ' * 12},
    {'password': 'x' * 129, 'password_confirm': 'x' * 129},
    {'remember_me': 'not-a-boolean'}, {'provider': 'google'},
])
def test_signup_validation_in_korean_without_password_echo(client, data):
    response = signup(client, **data)
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], str)
    assert any('가' <= char <= '힣' for char in response.json()['detail'])
    assert 'Valid-test-password-42' not in response.text
    assert 'input' not in response.json()


def test_missing_and_malformed_login_input(client):
    for data in [{}, {'email': [], 'password': {}}, {'email': 'm@example.com', 'password': ''}]:
        response = client.post('/api/auth/login', json=data)
        assert response.status_code == 422
        assert isinstance(response.json()['detail'], str)


def test_expired_invalid_and_legacy_credentials_are_rejected(client):
    signup(client)
    with client.session_factory() as db:
        db.scalar(select(AuthSession)).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get('/api/auth/me').status_code == 401
    client.cookies.clear()
    assert client.get('/api/documents', headers={'Authorization': 'Bearer old-token'}).status_code == 401
    assert client.get('/api/auth/me', headers={'Cookie': 'jerp_session=invalid'}).status_code == 401
    assert client.get('/api/auth/me', headers={'Cookie': 'jerp_session=' + secrets.token_urlsafe(32)}).status_code == 401


def test_csrf_and_cors_protect_all_mutations(client):
    signup(client)
    for route in ['/api/auth/login', '/api/auth/signup', '/api/auth/logout', '/api/documents', '/api/documents/1/attachments']:
        assert client.post(route, headers={'X-CSRF-Protection': ''}, json={}).status_code == 403
        assert client.post(route, headers={'Origin': 'https://attacker.example'}, json={}).status_code == 403
        assert client.post(route, headers={'Origin': 'null'}, json={}).status_code == 403
    assert client.post('/api/auth/logout', headers={'Origin': 'http://testserver'}).status_code == 204
    response = client.options('/api/auth/login', headers={
        'Origin': 'http://testserver', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'X-CSRF-Protection,Content-Type',
    })
    assert response.headers['access-control-allow-credentials'] == 'true'
    assert response.headers['access-control-allow-origin'] == 'http://testserver'


def test_secure_cookie_and_environment_validation(client):
    settings = get_settings()
    settings.session_cookie_secure = True
    try:
        assert 'secure' in signup(client).headers['set-cookie'].lower()
    finally:
        settings.session_cookie_secure = False
    with pytest.raises(ValueError):
        Settings(app_env='production', session_cookie_secure=False)


def test_provider_identity_can_link_to_same_user_without_password(client):
    user_id = signup(client).json()['id']
    with client.session_factory() as db:
        db.add(AuthAccount(user_id=user_id, provider='google', provider_user_id='future-provider-subject'))
        db.commit()
        accounts = db.scalars(select(AuthAccount).where(AuthAccount.user_id == user_id)).all()
        assert len(accounts) == 2
        assert next(a for a in accounts if a.provider == 'google').password_hash is None
        db.add(AuthAccount(user_id=user_id, provider='google', provider_user_id='future-provider-subject'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert login(client).status_code == 200
    assert client.get('/api/auth/google').status_code == 404
    group = client.post('/api/groups', json={'name': '계정 연결 테스트'}).json()
    assert client.get('/api/users/search', params={'q': '테스트', 'group_id': group['id']}).json()[0].get('email') is None
