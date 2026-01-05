"""Tests for shared web authentication routes."""

from __future__ import annotations

from functions import auth_helpers
from web.app import app


def test_login_test_shows_prompt_when_logged_out(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get('/login-test')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Please log in.' in html
  assert 'logout-btn' not in html


def test_login_test_shows_email_when_logged_in(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("user-123", {
                        "email": "user@example.com",
                        "uid": "user-123"
                      }))

  with app.test_client() as client:
    resp = client.get('/login-test')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Logged in as user@example.com.' in html
  assert 'id="logout-btn"' in html


def test_login_redirects_authenticated_user(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("user-123", {
                        "role": "user"
                      }))

  with app.test_client() as client:
    resp = client.get('/login?next=/login-test')

  assert resp.status_code == 302
  assert resp.headers['Location'] == 'https://snickerdoodlejokes.com/login-test'


def test_login_renders_when_non_admin_targets_admin(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("user-123", {
                        "role": "user"
                      }))

  with app.test_client() as client:
    resp = client.get('/login?next=/admin')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'id="google-signin"' in html


def test_login_redirects_admin_target_for_admin(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("admin-123", {
                        "role": "admin"
                      }))

  with app.test_client() as client:
    resp = client.get('/login?next=/admin')

  assert resp.status_code == 302
  assert resp.headers['Location'] == 'https://snickerdoodlejokes.com/admin'


def test_session_info_returns_logged_out(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get('/session-info')

  assert resp.status_code == 200
  assert resp.get_json() == {'authenticated': False}
  assert resp.headers['Cache-Control'] == 'no-store'


def test_session_info_returns_claims(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("user-123", {
                        "email": "user@example.com",
                        "uid": "user-123",
                        "role": "admin"
                      }))

  with app.test_client() as client:
    resp = client.get('/session-info')

  assert resp.status_code == 200
  assert resp.get_json() == {
    'authenticated': True,
    'email': 'user@example.com',
    'uid': 'user-123',
    'role': 'admin',
  }
  assert resp.headers['Cache-Control'] == 'no-store'
