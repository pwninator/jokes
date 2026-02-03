"""Tests for admin joke media generator routes."""

from __future__ import annotations

from functions import auth_helpers, joke_creation_fns
from web.app import app


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_joke_media_generator_page_loads(monkeypatch):
  """Render the generator with picker + generate buttons."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin/joke-media-generator')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Joke Media Generator' in html
  assert 'id="script-template"' in html
  assert 'id="speaker1-name"' in html
  assert 'id="speaker1-voice"' in html
  assert 'id="speaker2-name"' in html
  assert 'id="speaker2-voice"' in html
  assert 'id="generate-audio-button"' in html
  assert 'id="generate-video-button"' in html
  assert 'joke_picker.js' in html
  assert 'name="op"' in html
  assert f'value="{joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value}"' in html
  assert f'value="{joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value}"' in html


def test_admin_joke_media_generator_post_is_not_allowed(monkeypatch):
  """The generator route is GET-only; generation happens elsewhere."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post('/admin/joke-media-generator')

  assert resp.status_code == 405
