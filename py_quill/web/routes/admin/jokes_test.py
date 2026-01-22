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
  joke.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/setup.png"
  joke.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/punch.png"
  joke.all_setup_image_urls = [joke.setup_image_url]
  joke.all_punchline_image_urls = [joke.punchline_image_url]

  mock_get = Mock(return_value=([(joke, "joke-1")], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)
  monkeypatch.setattr(
    admin_jokes_routes.firestore,
    "get_all_joke_categories",
    Mock(return_value=[
      models.JokeCategory(id="cats", display_name="Cats", state="APPROVED"),
      models.JokeCategory(id="dogs", display_name="Dogs", state="SEASONAL"),
      models.JokeCategory(
        id="drafts",
        display_name="Drafts",
        state="PROPOSED",
      ),
    ]),
  )

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
  assert kwargs["category_id"] is None

  html = resp.get_data(as_text=True)
  assert 'data-category=""' in html
  assert 'data-category="cats"' in html
  assert 'data-category="dogs"' in html
  assert 'data-category="drafts"' not in html
  assert 'data-state="UNKNOWN"' in html
  assert 'data-state="DRAFT"' in html
  assert 'data-state="UNREVIEWED"' in html
  assert 'data-state="APPROVED"' in html
  assert 'data-state="REJECTED"' in html
  assert 'data-state="DAILY"' in html
  assert 'data-state="PUBLISHED"' in html
  assert '"states": "UNKNOWN,DRAFT,UNREVIEWED,APPROVED"' in html
  assert '"category": null' in html
  assert 'id="admin-new-joke-button"' in html
  assert 'id="admin-edit-joke-modal"' in html
  assert 'id="admin-edit-joke-setup-scene-idea"' not in html
  assert 'id="admin-edit-joke-punchline-scene-idea"' not in html
  assert 'id="admin-edit-joke-scene-ideas-button"' in html
  assert 'id="admin-scene-ideas-modal"' in html
  assert 'id="admin-scene-ideas-generate-button"' in html
  assert "/joke_creation_process" in html
  assert 'data-joke-id="joke-1"' in html
  assert 'joke-edit-button' in html
  assert 'data-joke-data=' in html
  # Spot check a few edit payload fields (HTML-escaped JSON).
  assert 'joke_id' in html
  assert 'joke-1' in html
  assert 'setup_text' in html
  assert 'setup' in html
  assert 'punchline_text' in html
  assert 'punch' in html
  assert 'joke_admin_actions.js' in html
  assert 'initJokeAdminActions' in html

  # New joke modal: tabbing from Punchline should focus Submit before Cancel.
  submit_index = html.find('id="admin-new-joke-submit-button"')
  cancel_index = html.find('id="admin-new-joke-cancel-button"')
  assert submit_index != -1
  assert cancel_index != -1
  assert submit_index < cancel_index


def test_admin_jokes_custom_filters(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  mock_get = Mock(return_value=([], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)
  monkeypatch.setattr(
    admin_jokes_routes.firestore,
    "get_all_joke_categories",
    Mock(return_value=[]),
  )

  with app.test_client() as client:
    resp = client.get("/admin/jokes?states=REJECTED,DAILY,PUBLISHED")

  assert resp.status_code == 200
  _, kwargs = mock_get.call_args
  assert kwargs["states"] == [
    models.JokeState.REJECTED,
    models.JokeState.DAILY,
    models.JokeState.PUBLISHED,
  ]
  assert kwargs["category_id"] is None


def test_admin_jokes_category_filter(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  mock_get = Mock(return_value=([], None))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)
  monkeypatch.setattr(
    admin_jokes_routes.firestore,
    "get_all_joke_categories",
    Mock(return_value=[
      models.JokeCategory(id="cats", display_name="Cats", state="APPROVED"),
      models.JokeCategory(id="dogs", display_name="Dogs", state="SEASONAL"),
      models.JokeCategory(
        id="drafts",
        display_name="Drafts",
        state="PROPOSED",
      ),
    ]),
  )

  with app.test_client() as client:
    resp = client.get("/admin/jokes?states=DRAFT&category=cats")

  assert resp.status_code == 200
  _, kwargs = mock_get.call_args
  assert kwargs["states"] == [models.JokeState.DRAFT]
  assert kwargs["category_id"] == "cats"

  html = resp.get_data(as_text=True)
  assert 'data-category="cats"' in html
  assert 'data-category="dogs"' in html
  assert 'data-category="drafts"' not in html


def test_admin_jokes_load_more(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  joke.key = "joke-1"
  joke.state = models.JokeState.DRAFT
  joke.num_viewed_users = 12
  joke.num_saved_users = 3
  joke.num_shared_users = 1
  joke.setup_image_url = "setup-url"
  joke.punchline_image_url = "punch-url"
  joke.all_setup_image_urls = ["setup-url"]
  joke.all_punchline_image_urls = ["punch-url"]

  mock_get = Mock(return_value=([(joke, "joke-1")], "next-1"))
  monkeypatch.setattr(admin_jokes_routes.firestore, "get_joke_by_state",
                      mock_get)

  with app.test_client() as client:
    resp = client.get(
      "/jokes/feed/load-more-admin-jokes?cursor=joke-0&states=DRAFT&category=cats",
    )

  assert resp.status_code == 200
  assert resp.headers["Content-Type"].startswith("application/json")
  body = resp.get_json()
  assert body["cursor"] == "next-1"
  assert body["has_more"] is True
  assert "joke-admin-stats" in body["html"]
  assert "joke-state-badge" in body["html"]
  assert "joke-edit-button" in body["html"]

  _, kwargs = mock_get.call_args
  assert kwargs["cursor"] == "joke-0"
  assert kwargs["states"] == [models.JokeState.DRAFT]
  assert kwargs["category_id"] == "cats"


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
  monkeypatch.setattr(
    admin_jokes_routes.firestore,
    "get_all_joke_categories",
    Mock(return_value=[]),
  )

  with app.test_client() as client:
    resp = client.get("/admin/jokes?states=DAILY")

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "joke-state-future-daily" in html
  assert "joke-state-daily joke-state-future-daily" not in html
