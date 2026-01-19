"""Tests for admin image prompt tuner routes."""

from __future__ import annotations

from unittest.mock import MagicMock

from werkzeug.datastructures import MultiDict

from agents import constants
from functions import auth_helpers
from web.app import app
from web.routes.admin import image_prompt_tuner as prompt_routes


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
  assert constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0] in html


def test_admin_image_prompt_tuner_generates_images(monkeypatch):
  """POSTing prompts triggers setup and punchline image generation."""
  _mock_admin_session(monkeypatch)

  mock_client = MagicMock()
  mock_select_client = MagicMock(return_value=mock_client)
  monkeypatch.setattr(prompt_routes, "_select_image_client", mock_select_client)

  mock_setup_image = MagicMock()
  mock_setup_image.url = "http://example.com/setup.png"
  mock_setup_image.gcs_uri = "gs://bucket/setup.png"
  mock_setup_image.custom_temp_data = {
    "image_generation_call_id": "call-123"
  }

  mock_punchline_image = MagicMock()
  mock_punchline_image.url = "http://example.com/punchline.png"
  mock_punchline_image.custom_temp_data = {}

  mock_client.generate_image.side_effect = [
    mock_setup_image,
    mock_punchline_image,
  ]

  data = MultiDict([
    ('setup_image_prompt', 'Setup prompt'),
    ('punchline_image_prompt', 'Punch prompt'),
    ('setup_reference_images', constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0]),
    ('setup_reference_images', constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1]),
    ('punchline_reference_images',
     constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2]),
    ('include_setup_image', 'true'),
    ('image_quality', 'low'),
  ])

  with app.test_client() as client:
    resp = client.post('/admin/image-prompt-tuner', data=data)

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'http://example.com/setup.png' in html
  assert 'http://example.com/punchline.png' in html

  mock_select_client.assert_called_once_with('low')
  assert mock_client.generate_image.call_count == 2

  first_call = mock_client.generate_image.call_args_list[0]
  assert first_call.args[0] == 'Setup prompt'
  assert first_call.args[1] == [
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
  ]
  assert first_call.kwargs['save_to_firestore'] is False

  second_call = mock_client.generate_image.call_args_list[1]
  assert second_call.args[0] == 'Punch prompt'
  assert second_call.args[1] == [
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2],
    'call-123',
  ]
  assert second_call.kwargs['save_to_firestore'] is False
