"""Tests for admin image prompt tuner routes."""

from __future__ import annotations

from unittest.mock import MagicMock

from werkzeug.datastructures import MultiDict

from agents import constants
from functions import auth_helpers, function_utils, joke_creation_fns
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


def test_admin_image_prompt_tuner_generates_images(monkeypatch):
  """POSTing prompts triggers setup and punchline image generation."""
  _mock_admin_session(monkeypatch)

  mock_process = MagicMock(
    return_value=function_utils.success_response({
      "setup_image_url": "http://example.com/setup.png",
      "punchline_image_url": "http://example.com/punchline.png",
    }))
  monkeypatch.setattr(joke_creation_fns, "joke_creation_process", mock_process)

  data = MultiDict([
    ('setup_image_prompt', 'Setup prompt'),
    ('punchline_image_prompt', 'Punch prompt'),
    ('setup_reference_images', constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0]),
    ('setup_reference_images', constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1]),
    ('punchline_reference_images',
     constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2]),
    ('include_setup_image', 'true'),
    ('image_quality', 'low'),
    ('op', joke_creation_fns.JokeCreationOp.JOKE_IMAGE.value),
  ])

  with app.test_client() as client:
    resp = client.post('/admin/image-prompt-tuner', data=data)

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'http://example.com/setup.png' in html
  assert 'http://example.com/punchline.png' in html

  mock_process.assert_called_once()
