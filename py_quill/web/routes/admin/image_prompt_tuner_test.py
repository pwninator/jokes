"""Tests for admin image prompt tuner routes."""

from __future__ import annotations

from agents import constants
from functions import auth_helpers, joke_creation_fns
from web.app import app


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_image_prompt_tuner_page_loads(monkeypatch):
  """Render the prompt tuner with default prompts and reference images."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin/image-prompt-tuner')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Image Prompt Tuner' in html
  assert 'SETUP_IMAGE_DESCRIPTION_HERE' in html
  assert 'PUNCHLINE_IMAGE_DESCRIPTION_HERE' in html
  assert 'name="setup_reference_images"' in html
  assert 'name="punchline_reference_images"' in html
  assert 'name="include_setup_image"' in html
  assert 'name="op"' in html
  assert f'value="{joke_creation_fns.JokeCreationOp.JOKE_IMAGE.value}"' in html
  assert constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0] in html
  assert "/joke_creation_process" in html
  assert 'method="GET"' in html


def test_admin_image_prompt_tuner_post_is_not_allowed(monkeypatch):
  """The tuner route is GET-only; image generation happens elsewhere."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post('/admin/image-prompt-tuner')

  assert resp.status_code == 405
