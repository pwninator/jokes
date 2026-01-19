"""Tests for admin social routes."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

from common import models
from functions import auth_helpers
from web.app import app
from web.routes.admin import social as social_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(
    auth_helpers,
    "verify_session",
    lambda _req: ("uid123", {
      "role": "admin"
    }),
  )


def test_admin_social_requires_auth(monkeypatch):
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get("/admin/social")

  assert resp.status_code == 302
  assert "/login" in resp.headers["Location"]


def test_admin_social_filters_public_jokes(monkeypatch):
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
                   (private_joke, "joke-private")], None))
  monkeypatch.setattr(social_routes.firestore, "get_joke_by_state", mock_get)
  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[]),
  )
  monkeypatch.setattr(
    social_routes.firestore,
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
    resp = client.get("/admin/social")

  assert resp.status_code == 200
  _, kwargs = mock_get.call_args
  assert kwargs["states"] == [
    models.JokeState.DAILY,
    models.JokeState.PUBLISHED,
  ]
  assert kwargs["category_id"] is None

  html = resp.get_data(as_text=True)
  assert 'data-category=""' in html
  assert 'data-category="cats"' in html
  assert 'data-category="dogs"' in html
  assert 'data-category="drafts"' not in html
  assert 'data-state="' not in html
  assert 'data-joke-id="joke-public"' in html
  assert 'data-joke-id="joke-private"' not in html
  assert '--joke-card-max-width: 200px' in html
  assert '/jokes/feed/load-more-admin-social' in html
  assert 'admin-social-create-button' in html
  assert 'admin-social-post-type' in html
  assert 'social_post_creation_process' in html
  assert "createPostEndpoint = '/social_post_creation_process'" in html
  assert 'data-selectable="true"' in html
  assert 'joke-admin-stats' in html
  assert 'joke-edit-button' not in html


def test_admin_social_load_more(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  public_joke = models.PunnyJoke(setup_text="setup", punchline_text="punch")
  public_joke.key = "joke-public"
  public_joke.state = models.JokeState.PUBLISHED
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
                   (private_joke, "joke-private")], "next-1"))
  monkeypatch.setattr(social_routes.firestore, "get_joke_by_state", mock_get)
  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[]),
  )

  with app.test_client() as client:
    resp = client.get(
      "/jokes/feed/load-more-admin-social?cursor=joke-0&category=cats",
    )

  assert resp.status_code == 200
  assert resp.headers["Content-Type"].startswith("application/json")
  body = resp.get_json()
  assert body["cursor"] == "next-1"
  assert body["has_more"] is True
  assert 'data-joke-id="joke-public"' in body["html"]
  assert 'data-joke-id="joke-private"' not in body["html"]
  assert 'data-selectable="true"' in body["html"]
  assert "joke-admin-stats" in body["html"]
  assert "joke-edit-button" not in body["html"]

  _, kwargs = mock_get.call_args
  assert kwargs["cursor"] == "joke-0"
  assert kwargs["states"] == [
    models.JokeState.DAILY,
    models.JokeState.PUBLISHED,
  ]
  assert kwargs["category_id"] == "cats"


def test_admin_social_renders_social_posts(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/social",
    pinterest_title="Title",
    pinterest_description="Description",
    instagram_caption="Insta caption",
    facebook_message="FB message",
    pinterest_image_urls=["https://example.com/pin.png"],
  )
  created_at = datetime.datetime(2024, 1, 2, 3, 4, 5,
                                 tzinfo=datetime.timezone.utc)

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[(post, created_at)]),
  )
  monkeypatch.setattr(
    social_routes.firestore,
    "get_all_joke_categories",
    Mock(return_value=[]),
  )
  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_by_state",
    Mock(return_value=([], None)),
  )

  with app.test_client() as client:
    resp = client.get("/admin/social")

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Social Posts" in html
  assert "Title" in html
  assert "Description" in html
  assert "Insta caption" in html
  assert "FB message" in html
  assert "JOKE_GRID" in html
  assert "https://snickerdoodlejokes.com/jokes/social" in html
  assert "pin.png" in html
  assert "Edit" in html
  assert "Regenerate text" in html
  assert "Post" in html
