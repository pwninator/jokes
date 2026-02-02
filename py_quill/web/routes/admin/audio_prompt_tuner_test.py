"""Tests for admin audio prompt tuner routes."""

from __future__ import annotations

from functions import auth_helpers, joke_creation_fns
from web.app import app


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_audio_prompt_tuner_page_loads(monkeypatch):
  """Render the prompt tuner with picker + generate button."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.get('/admin/audio-prompt-tuner')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Audio Prompt Tuner' in html
  assert 'id="generate-button"' in html
  assert 'joke_picker.js' in html
  assert 'name="op"' in html
  assert f'value="{joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value}"' in html


def test_admin_audio_prompt_tuner_post_is_not_allowed(monkeypatch):
  """The tuner route is GET-only; audio generation happens elsewhere."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post('/admin/audio-prompt-tuner')

  assert resp.status_code == 405
