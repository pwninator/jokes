"""Tests for auth_helpers."""

import flask
import pytest
from firebase_admin import auth as firebase_auth

from common import config
from functions import auth_helpers


@pytest.fixture
def flask_app():
  """Provide a minimal Flask app for request context tests."""
  return flask.Flask(__name__)


def test_create_session_cookie_uses_configured_expiry(monkeypatch):
  captured = {}

  def fake_create_session_cookie(id_token, expires_in):
    captured['id_token'] = id_token
    captured['expires_in'] = expires_in
    return 'session-cookie-value'

  monkeypatch.setattr(auth_helpers.auth, 'create_session_cookie',
                      fake_create_session_cookie)

  result = auth_helpers.create_session_cookie('id-token')

  assert result == 'session-cookie-value'
  assert captured['id_token'] == 'id-token'
  assert captured['expires_in'].total_seconds() == pytest.approx(
    config.SESSION_MAX_AGE_SECONDS)


def test_set_session_cookie_sets_secure_attributes():
  response = flask.Response('ok')

  auth_helpers.set_session_cookie(response,
                                  'cookie-value',
                                  domain='example.com')

  header = response.headers.get('Set-Cookie')
  assert f"{config.SESSION_COOKIE_NAME}=cookie-value" in header
  assert 'HttpOnly' in header
  assert 'Secure' in header
  assert 'SameSite=Lax' in header
  assert 'Path=/' in header
  assert 'Domain=example.com' in header


def test_clear_session_cookie_expires_cookie():
  response = flask.Response('ok')

  auth_helpers.clear_session_cookie(response, domain='example.com')

  header = response.headers.get('Set-Cookie')
  assert f"{config.SESSION_COOKIE_NAME}=" in header
  assert 'expires=' in header or 'Expires=' in header
  assert 'Domain=example.com' in header
  assert 'Path=/' in header


def test_set_session_cookie_parent_domain_also_sets_host_cookie():
  response = flask.Response('ok')

  auth_helpers.set_session_cookie(response,
                                  'cookie-value',
                                  domain='.snickerdoodlejokes.com')

  headers = response.headers.getlist('Set-Cookie')
  assert len(headers) == 2
  # Werkzeug normalizes away the leading dot on cookie domains.
  assert any('Domain=snickerdoodlejokes.com' in h for h in headers)
  assert any('Domain=' not in h for h in headers)


def test_clear_session_cookie_parent_domain_also_clears_host_cookie():
  response = flask.Response('ok')

  auth_helpers.clear_session_cookie(response, domain='.snickerdoodlejokes.com')

  headers = response.headers.getlist('Set-Cookie')
  assert len(headers) == 2
  assert any('Domain=snickerdoodlejokes.com' in h for h in headers)
  assert any('Domain=' not in h for h in headers)


def test_verify_session_returns_none_without_cookie(flask_app):
  with flask_app.test_request_context('/admin'):
    assert auth_helpers.verify_session(flask.request) is None


def test_verify_session_returns_tuple_when_valid(monkeypatch, flask_app):

  def fake_verify(cookie, check_revoked):
    assert cookie == 'session-token'
    assert check_revoked is True
    return {'uid': 'admin-user', 'role': 'admin'}

  monkeypatch.setattr(auth_helpers.auth, 'verify_session_cookie', fake_verify)

  cookie_header = f"{config.SESSION_COOKIE_NAME}=session-token"
  with flask_app.test_request_context('/admin',
                                      headers={'Cookie': cookie_header}):
    result = auth_helpers.verify_session(flask.request)

  assert result == ('admin-user', {'uid': 'admin-user', 'role': 'admin'})


def test_verify_session_handles_invalid_cookie(monkeypatch, flask_app):

  def fake_verify(cookie, check_revoked):
    raise firebase_auth.InvalidSessionCookieError('invalid cookie')

  monkeypatch.setattr(auth_helpers.auth, 'verify_session_cookie', fake_verify)

  cookie_header = f"{config.SESSION_COOKIE_NAME}=invalid"
  with flask_app.test_request_context('/admin',
                                      headers={'Cookie': cookie_header}):
    assert auth_helpers.verify_session(flask.request) is None


def test_require_admin_redirects_when_unauthenticated(monkeypatch, flask_app):
  monkeypatch.setattr(auth_helpers, 'verify_session', lambda request: None)
  monkeypatch.setattr(flask, 'url_for',
                      lambda *args, **kwargs: '/login')  # noqa: ARG005

  @auth_helpers.require_admin
  def protected():
    return 'secret'

  headers = {
    'Host': 'snickerdoodlejokes.com',
    'X-Forwarded-Host': 'snickerdoodlejokes.com',
    'X-Forwarded-Proto': 'https',
  }
  with flask_app.test_request_context('/admin/secret', headers=headers):
    response = protected()

  assert response.status_code == 302
  assert response.headers['Location'] == 'https://snickerdoodlejokes.com/login'


def test_require_admin_forbids_non_admin(monkeypatch, flask_app):
  monkeypatch.setattr(
    auth_helpers,
    'verify_session',
    lambda request: ('user-id', {
      'role': 'user'
    }),
  )

  @auth_helpers.require_admin
  def protected():
    return 'secret'

  with flask_app.test_request_context('/admin/secret'):
    response = protected()

  assert response.status_code == 403
  assert response.data == b'Forbidden'


def test_require_admin_allows_admin(monkeypatch, flask_app):
  monkeypatch.setattr(
    auth_helpers,
    'verify_session',
    lambda request: ('admin-id', {
      'role': 'admin'
    }),
  )

  @auth_helpers.require_admin
  def protected():
    return 'OK'

  with flask_app.test_request_context('/admin/dashboard'):
    result = protected()

  assert result == 'OK'


def test_cookie_domain_for_request_uses_host(monkeypatch, flask_app):
  with flask_app.test_request_context('/'):
    domain = auth_helpers.cookie_domain_for_request(flask.request)
  assert domain == f".{config.ROOT_HOST}"


def test_cookie_domain_for_request_ignores_localhost(monkeypatch, flask_app):
  with flask_app.test_request_context('/', headers={'Host': 'localhost:5000'}):
    domain = auth_helpers.cookie_domain_for_request(flask.request)
  assert domain == f".{config.ROOT_HOST}"


def test_cookie_domain_for_request_env_override(monkeypatch, flask_app):
  with flask_app.test_request_context('/', headers={'Host': 'ignored.com'}):
    domain = auth_helpers.cookie_domain_for_request(flask.request)
  assert domain == f".{config.ROOT_HOST}"


def test_cookie_domain_for_request_emulator(monkeypatch, flask_app):
  monkeypatch.setattr('common.utils.is_emulator', lambda: True)
  with flask_app.test_request_context('/', headers={'Host': '127.0.0.1:5000'}):
    domain = auth_helpers.cookie_domain_for_request(flask.request)
  assert domain == '127.0.0.1'
  monkeypatch.setattr('common.utils.is_emulator', lambda: False)


def test_cookie_domain_prefers_forwarded_host(flask_app):
  headers = {
    'Host': 'internal.run.app',
    'X-Forwarded-Host': 'snickerdoodlejokes.com',
    'X-Forwarded-Proto': 'https',
  }
  with flask_app.test_request_context('/', headers=headers):
    domain = auth_helpers.cookie_domain_for_request(flask.request)
  assert domain == '.snickerdoodlejokes.com'


def test_resolve_admin_redirect_relative_path(flask_app):
  with flask_app.test_request_context('/admin',
                                      headers={
                                        'X-Forwarded-Host':
                                        'snickerdoodlejokes.com',
                                        'X-Forwarded-Proto': 'https'
                                      }):
    url = auth_helpers.resolve_admin_redirect(flask.request,
                                              '/admin/joke-books', '/admin')
  assert url == 'https://snickerdoodlejokes.com/admin/joke-books'


def test_resolve_admin_redirect_strips_external_host(flask_app):
  headers = {
    'X-Forwarded-Host': 'snickerdoodlejokes.com',
    'X-Forwarded-Proto': 'https'
  }
  with flask_app.test_request_context('/admin', headers=headers):
    url = auth_helpers.resolve_admin_redirect(flask.request,
                                              'https://evil.example.com/path',
                                              '/admin')
  assert url == 'https://snickerdoodlejokes.com/path'


def test_resolve_admin_redirect_emulator(monkeypatch, flask_app):
  monkeypatch.setattr('common.utils.is_emulator', lambda: True)
  with flask_app.test_request_context('http://127.0.0.1:5000/admin'):
    url = auth_helpers.resolve_admin_redirect(flask.request,
                                              '/admin/dashboard', '/admin')
  assert url == 'http://127.0.0.1/admin/dashboard'
  monkeypatch.setattr('common.utils.is_emulator', lambda: False)
