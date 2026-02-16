"""Tests for admin joke media generator routes."""

from __future__ import annotations

from common import models
from functions import auth_helpers, joke_creation_fns
from services import audio_client, gen_audio, firestore
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
  monkeypatch.setattr(
    firestore,
    "get_posable_character_defs",
    lambda: [
      models.PosableCharacterDef(key="char-1", name="Cat"),
      models.PosableCharacterDef(key="char-2", name="Dog"),
    ],
  )

  with app.test_client() as client:
    resp = client.get('/admin/joke-media-generator')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Joke Media Generator' in html
  assert 'id="audio-model"' in html
  assert f'value="{audio_client.AudioModel.ELEVENLABS_ELEVEN_V3.value}" selected' in html
  assert 'id="turn1-voice-gemini"' in html
  assert 'id="turn1-voice-eleven"' in html
  assert 'id="turn1-script"' in html
  assert 'id="turn1-pause-after"' in html
  assert 'id="turn2-voice-gemini"' in html
  assert 'id="turn2-voice-eleven"' in html
  assert 'id="turn2-script"' in html
  assert 'id="turn2-pause-after"' in html
  assert 'id="turn3-voice-gemini"' in html
  assert 'id="turn3-voice-eleven"' in html
  assert 'id="turn3-script"' in html
  assert 'id="turn3-pause-after"' in html
  assert 'id="turn4-voice-gemini"' in html
  assert 'id="turn4-voice-eleven"' in html
  assert 'id="turn4-script"' in html
  assert 'id="turn4-pause-after"' in html
  assert html.count(
    f'value="{gen_audio.Voice.ELEVENLABS_LULU_LOLLIPOP.name}" selected') == 3
  assert html.count(
    f'value="{gen_audio.Voice.ELEVENLABS_AERISITA.name}" selected') == 1
  assert 'id="generate-audio-button"' in html
  assert 'id="generate-video-button"' in html
  assert 'id="video-teller-character-id"' in html
  assert 'id="video-listener-character-id"' in html
  assert 'id="use-audio-cache"' in html
  assert 'Use Audio Cache' in html
  assert 'id="use-audio-cache" type="checkbox" checked' in html
  assert 'Cat' in html
  assert 'Dog' in html
  assert html.count('value="char-1" selected') == 1
  assert html.count('value="char-2" selected') == 1
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
