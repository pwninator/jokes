"""Tests for admin joke picker API routes."""

from __future__ import annotations

from unittest.mock import Mock

from common import models
from functions import auth_helpers
from web.app import app
from web.routes.admin import joke_picker_api as picker_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(
    auth_helpers,
    "verify_session",
    lambda _req: ("uid123", {
      "role": "admin"
    }),
  )


def test_admin_joke_picker_requires_states(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  with app.test_client() as client:
    resp = client.get("/admin/api/jokes/picker")

  assert resp.status_code == 400
  assert resp.get_json()["error"] == "states parameter required"


def test_admin_joke_picker_filters_public(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  public_joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  public_joke.key = "joke-public"
  public_joke.state = models.JokeState.DAILY
  public_joke.is_public = True
  public_joke.setup_image_url = "setup-url"
  public_joke.punchline_image_url = "punch-url"
  public_joke.all_setup_image_urls = ["setup-url"]
  public_joke.all_punchline_image_urls = ["punch-url"]

  private_joke = models.PunnyJoke(setup_text="hidden", punchline_text="secret")
  private_joke.key = "joke-private"
  private_joke.state = models.JokeState.DAILY
  private_joke.is_public = False

  mock_get = Mock(
    return_value=([(public_joke, "joke-public"),
                   (private_joke, "joke-private")], "next-1"),
  )
  monkeypatch.setattr(picker_routes.firestore, "get_joke_by_state", mock_get)

  with app.test_client() as client:
    resp = client.get(
      "/admin/api/jokes/picker?"
      "states=DAILY,PUBLISHED&public_only=true&category=cats&cursor=joke-0&"
      "limit=2&image_size=210",
    )

  assert resp.status_code == 200
  assert resp.headers["Content-Type"].startswith("application/json")
  body = resp.get_json()
  assert body["cursor"] == "next-1"
  assert body["has_more"] is True
  assert 'data-joke-id="joke-public"' in body["html"]
  assert 'data-joke-id="joke-private"' not in body["html"]
  assert len(body["jokes"]) == 1
  assert body["jokes"][0]["id"] == "joke-public"

  _, kwargs = mock_get.call_args
  assert kwargs["cursor"] == "joke-0"
  assert kwargs["limit"] == 2
  assert kwargs["states"] == [
    models.JokeState.DAILY,
    models.JokeState.PUBLISHED,
  ]
  assert kwargs["category_id"] == "cats"


def test_admin_joke_picker_categories(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  monkeypatch.setattr(
    picker_routes.firestore,
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
    resp = client.get("/admin/api/jokes/categories")

  assert resp.status_code == 200
  body = resp.get_json()
  categories = body["categories"]
  assert [c["id"] for c in categories] == ["cats", "dogs"]
