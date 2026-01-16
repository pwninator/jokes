"""Tests for social_fns."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from PIL import Image

from common import models
from functions import social_fns


class DummyReq:
  """Minimal request stub for testing."""

  def __init__(self,
               *,
               method: str = 'POST',
               data: dict | None = None,
               path: str = ""):
    self.method = method
    self.is_json = True
    self._data = data or {}
    self.path = path
    self.headers = {}

  def get_json(self, silent: bool = False):
    return {"data": self._data}


def _json_payload(resp) -> dict:
  return json.loads(resp.get_data(as_text=True))


def test_create_social_post_success(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  joke_ids = ["j1", "j2"]
  jokes = [
    models.PunnyJoke(key="j1", setup_text="Setup 1", punchline_text="Punch 1"),
    models.PunnyJoke(key="j2", setup_text="Setup 2", punchline_text="Punch 2"),
  ]
  monkeypatch.setattr(social_fns.firestore, "get_punny_jokes", lambda ids: jokes)
  def _fake_generate_pinterest_post_text(image_bytes, post_type):
    assert image_bytes.startswith(b"\x89PNG")
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    return "Title", "Description", "Alt text"

  monkeypatch.setattr(
    social_fns.social_operations,
    "generate_pinterest_post_text",
    _fake_generate_pinterest_post_text,
  )

  create_image_mock = Mock(
    return_value=Image.new('RGB', (1000, 500), color='white'))
  monkeypatch.setattr(social_fns.image_operations,
                      "create_pinterest_pin_image", create_image_mock)

  monkeypatch.setattr(social_fns.cloud_storage, "get_image_gcs_uri",
                      lambda base, ext: "gs://bucket/pin.png")
  monkeypatch.setattr(social_fns.cloud_storage, "upload_bytes_to_gcs",
                      lambda _bytes, _uri, _content_type: None)
  monkeypatch.setattr(social_fns.cloud_storage, "get_public_cdn_url",
                      lambda _uri: "https://cdn.example.com/pin.png")
  created_post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID_TEASER,
    pinterest_title="Title",
    pinterest_description="Description",
    pinterest_alt_text="Alt text",
    jokes=[{"key": "j1"}, {"key": "j2"}],
    pinterest_image_url="https://cdn.example.com/pin.png",
  )
  created_post.key = "post1"
  create_mock = Mock(return_value=created_post)
  monkeypatch.setattr(social_fns.firestore, "create_joke_social_post",
                      create_mock)

  req = DummyReq(data={"joke_ids": joke_ids, "type": "JOKE_GRID_TEASER"})
  resp = social_fns.create_social_post(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  assert payload["data"]["pinterest_title"] == "Title"
  assert payload["data"]["pinterest_description"] == "Description"
  assert payload["data"]["pinterest_alt_text"] == "Alt text"
  assert payload["data"]["pinterest_image_url"] == "https://cdn.example.com/pin.png"
  assert payload["data"]["type"] == "JOKE_GRID_TEASER"

  create_image_mock.assert_called_once_with(
    joke_ids,
    block_last_panel=True,
  )
  create_mock.assert_called_once()
  created_arg = create_mock.call_args[0][0]
  assert isinstance(created_arg, models.JokeSocialPost)
  assert created_arg.type == models.JokeSocialPostType.JOKE_GRID_TEASER
  assert created_arg.pinterest_title == "Title"
  assert created_arg.pinterest_description == "Description"
  assert created_arg.pinterest_alt_text == "Alt text"
  assert created_arg.jokes == [
    {
      "key": "j1",
      "setup_text": "Setup 1",
      "punchline_text": "Punch 1",
      "setup_image_url": None,
      "punchline_image_url": None,
    },
    {
      "key": "j2",
      "setup_text": "Setup 2",
      "punchline_text": "Punch 2",
      "setup_image_url": None,
      "punchline_image_url": None,
    },
  ]
  assert created_arg.pinterest_image_url == "https://cdn.example.com/pin.png"


def test_create_social_post_invalid_type(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  req = DummyReq(data={"joke_ids": ["j1"], "type": "BAD"})
  resp = social_fns.create_social_post(req)

  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert "type must be one of" in payload["data"]["error"]
