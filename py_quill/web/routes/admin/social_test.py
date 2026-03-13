"""Tests for admin social routes."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

from common import config, models
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


def test_admin_social_renders_picker_shell(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[]),
  )

  with app.test_client() as client:
    resp = client.get("/admin/social")

  assert resp.status_code == 200

  html = resp.get_data(as_text=True)
  assert 'id="admin-social-picker"' in html
  assert 'data-role="grid"' in html
  assert '/static/js/joke_picker.js' in html
  assert 'new window.JokePicker' in html
  assert 'admin-social-create-button' in html
  assert 'admin-social-post-type' in html
  assert f"https://{config.JOKE_CREATION_BIG_API_HOST}" in html
  assert (f'createPostEndpoint = "https://{config.JOKE_CREATION_BIG_API_HOST}"'
          ) in html
  assert 'value="JOKE_REEL_VIDEO"' in html
  assert 'option value="JOKE_REEL_VIDEO" selected' in html
  assert "op: 'social'" in html
  assert 'id="admin-social-post-modal-title"' in html
  assert "postModalInput.focus()" in html
  assert "openPostModal(card, platform);" in html
  assert 'class="text-button js-social-post-button" data-platform="pinterest"' in html
  assert ('class="text-button js-social-manual-post-button" data-platform="instagram"'
          ) in html
  assert ('class="text-button js-social-manual-post-button" data-platform="facebook"'
          ) in html
  assert 'class="text-button social-post-card__expand-toggle js-social-expand-toggle"' in html
  assert "setCardExpanded(card, false);" in html
  assert "toggleCardExpanded(card);" in html
  assert 'postModalTitle.textContent = `Mark ${formatPlatformName(platform)} as posted`;' in html


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
  created_at = datetime.datetime(2024,
                                 1,
                                 2,
                                 3,
                                 4,
                                 5,
                                 tzinfo=datetime.timezone.utc)
  post.creation_time = created_at

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[post]),
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
  html_dom = html.split("<script>", 1)[0]
  assert "Social Posts" in html
  assert "Title" in html
  assert "Description" in html
  assert "Insta caption" in html
  assert "FB message" in html
  assert "JOKE_GRID" in html
  assert "https://snickerdoodlejokes.com/jokes/social" in html
  assert "pin.png" in html
  assert 'cdn-cgi/image/width=250,format=auto,quality=50/pin.png' in html_dom
  assert 'class="social-post-card is-collapsed social-post-card--unposted"' in html_dom
  assert 'class="social-post-card__collapsed-media js-social-collapsed-media"' in html_dom
  assert 'class="text-button social-post-card__expand-toggle js-social-expand-toggle"' in html_dom
  assert "Expand" in html_dom
  assert 'class="icon-button icon-button--danger js-social-delete"' in html_dom
  assert 'class="text-button js-social-post-button" data-platform="pinterest"' in html_dom
  assert 'class="text-button js-social-post-button" data-platform="instagram"' in html_dom
  assert ('class="text-button js-social-manual-post-button" data-platform="instagram"'
          ) in html_dom
  assert 'class="text-button js-social-post-button" data-platform="facebook"' in html_dom
  assert ('class="text-button js-social-manual-post-button" data-platform="facebook"'
          ) in html_dom
  assert "Edit" in html
  assert "Regenerate text" in html
  assert 'class="text-button js-social-manual-post-button" data-platform="instagram">' in html
  assert 'class="text-button js-social-manual-post-button" data-platform="facebook">' in html


def test_admin_social_hides_delete_when_posted(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/social",
    pinterest_post_id="pin-123",
  )
  created_at = datetime.datetime(2024,
                                 1,
                                 2,
                                 3,
                                 4,
                                 5,
                                 tzinfo=datetime.timezone.utc)
  post.creation_time = created_at

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[post]),
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
  html_dom = html.split("<script>", 1)[0]
  assert "pin-123" in html
  assert 'class="social-post-card is-collapsed social-post-card--unposted"' not in html_dom
  assert 'class="icon-button icon-button--danger js-social-delete"' not in html_dom
  assert 'class="text-button js-social-post-button" data-platform="pinterest">' not in html_dom


def test_admin_social_renders_carousel_grid(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_CAROUSEL,
    link_url="https://snickerdoodlejokes.com/jokes/carousel",
    pinterest_image_urls=[
      "https://example.com/pin-giraffe.png",
    ],
    instagram_image_urls=[
      "https://example.com/carousel-1.png",
      "https://example.com/carousel-2.png",
    ],
  )
  created_at = datetime.datetime(2024,
                                 2,
                                 3,
                                 4,
                                 5,
                                 6,
                                 tzinfo=datetime.timezone.utc)
  post.creation_time = created_at

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[post]),
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
  assert 'data-post-type="JOKE_CAROUSEL"' in html
  assert 'class="social-posts-carousel js-social-carousel"' in html
  assert 'class="social-posts-carousel-pin"' in html
  assert 'alt="Pinterest giraffe image"' in html
  assert 'href="https://example.com/pin-giraffe.png"' in html
  assert 'href="https://example.com/carousel-1.png"' in html
  assert 'href="https://example.com/carousel-2.png"' in html
  assert 'alt="Carousel image 1"' in html
  assert 'alt="Carousel image 2"' in html


def test_admin_social_renders_video_preview(monkeypatch):
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: False)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_REEL_VIDEO,
    link_url="https://snickerdoodlejokes.com/jokes/video",
    preview_image_gcs_uri="gs://bucket/social/reel-preview.png",
    pinterest_video_gcs_uri="gs://bucket/social/video.mp4",
    instagram_video_gcs_uri="gs://bucket/social/video.mp4",
    facebook_video_gcs_uri="gs://bucket/social/video.mp4",
    instagram_caption="Video caption",
    facebook_message="Video message",
  )
  created_at = datetime.datetime(2024,
                                 2,
                                 3,
                                 4,
                                 5,
                                 6,
                                 tzinfo=datetime.timezone.utc)
  post.creation_time = created_at

  monkeypatch.setattr(
    social_routes.firestore,
    "get_joke_social_posts",
    Mock(return_value=[post]),
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
  assert 'data-post-type="JOKE_REEL_VIDEO"' in html
  assert 'data-instagram-video-gcs-uri="gs://bucket/social/video.mp4"' in html
  assert 'data-facebook-video-gcs-uri="gs://bucket/social/video.mp4"' in html
  assert 'data-pinterest-video-gcs-uri="gs://bucket/social/video.mp4"' in html
  assert 'data-preview-image-gcs-uri="gs://bucket/social/reel-preview.png"' in html
  assert 'src="https://bucket/social/video.mp4"' in html
  assert ('cdn-cgi/image/width=250,format=auto,quality=50/social/reel-preview.png'
          ) in html
  assert 'class="social-posts-reel-video js-social-reel-video"' in html
  assert ('.social-posts-reel-video-slot .social-posts-video-thumb {\n'
          '    aspect-ratio: 9 / 16;') in html

  collapsed_start = html.index(
    '<div class="social-post-card__collapsed-media js-social-collapsed-media">')
  collapsed_end = html.index('<div class="social-post-card__expanded">',
                             collapsed_start)
  collapsed_html = html[collapsed_start:collapsed_end]
  assert "<video" not in collapsed_html
  assert "Reel preview image" in collapsed_html

  html_dom = html.split("<script>", 1)[0]
  assert html_dom.count("<video") == 1
