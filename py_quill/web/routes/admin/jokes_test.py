"""Tests for admin jokes routes."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

from common import models
from functions import auth_helpers
from web.app import app
from web.routes.admin import admin_jokes as admin_jokes_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(
    auth_helpers,
    "verify_session",
    lambda _req: ("uid123", {
      "role": "admin"
    }),
  )


def test_admin_jokes_requires_auth(monkeypatch):
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get("/admin/jokes")

  assert resp.status_code == 302
  assert "/login" in resp.headers["Location"]


def test_admin_jokes_default_filters(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  joke.key = "joke-1"
  joke.state = models.JokeState.DRAFT

  mock_get = Mock(return_value=([(joke, "joke-1")], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)

  with app.test_client() as client:
    resp = client.get("/admin/jokes")

  assert resp.status_code == 200
  _, kwargs = mock_get.call_args
  assert kwargs["states"] == [
    models.JokeState.UNKNOWN,
    models.JokeState.DRAFT,
    models.JokeState.UNREVIEWED,
    models.JokeState.APPROVED,
  ]

  html = resp.get_data(as_text=True)
  assert 'data-state="UNKNOWN"' in html
  assert 'data-state="DRAFT"' in html
  assert 'data-state="UNREVIEWED"' in html
  assert 'data-state="APPROVED"' in html
  assert 'data-state="REJECTED"' in html
  assert 'data-state="DAILY"' in html
  assert 'data-state="PUBLISHED"' in html
  assert '"states": "UNKNOWN,DRAFT,UNREVIEWED,APPROVED"' in html


def test_admin_jokes_custom_filters(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  mock_get = Mock(return_value=([], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)

  with app.test_client() as client:
    resp = client.get("/admin/jokes?states=REJECTED,DAILY,PUBLISHED")

  assert resp.status_code == 200
  _, kwargs = mock_get.call_args
  assert kwargs["states"] == [
    models.JokeState.REJECTED,
    models.JokeState.DAILY,
    models.JokeState.PUBLISHED,
  ]


def test_admin_jokes_load_more(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  joke.key = "joke-1"
  joke.state = models.JokeState.DRAFT
  joke.num_viewed_users = 12
  joke.num_saved_users = 3
  joke.num_shared_users = 1

  mock_get = Mock(return_value=([(joke, "joke-1")], "next-1"))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)

  with app.test_client() as client:
    resp = client.get(
      "/jokes/feed/load-more-admin-jokes?cursor=joke-0&states=DRAFT", )

  assert resp.status_code == 200
  assert resp.headers["Content-Type"].startswith("application/json")
  body = resp.get_json()
  assert body["cursor"] == "next-1"
  assert body["has_more"] is True
  assert "joke-admin-stats" in body["html"]
  assert "joke-state-badge" in body["html"]

  _, kwargs = mock_get.call_args
  assert kwargs["cursor"] == "joke-0"
  assert kwargs["states"] == [models.JokeState.DRAFT]


def test_admin_jokes_future_daily_badge_uses_future_class(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  joke.key = "joke-future"
  joke.state = models.JokeState.DAILY
  joke.public_timestamp = datetime.datetime.now(
    datetime.timezone.utc) + datetime.timedelta(days=30)

  mock_get = Mock(return_value=([(joke, "joke-future")], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)

  with app.test_client() as client:
    resp = client.get("/admin/jokes?states=DAILY")

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "joke-state-future-daily" in html
  assert "joke-state-daily joke-state-future-daily" not in html
