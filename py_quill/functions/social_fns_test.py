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


def test_social_post_creation_process_success(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  joke_ids = ["j1", "j2"]
  jokes = [
    models.PunnyJoke(key="j1", setup_text="Setup 1", punchline_text="Punch 1"),
    models.PunnyJoke(key="j2", setup_text="Setup 2", punchline_text="Punch 2"),
  ]
  monkeypatch.setattr(social_fns.social_operations.firestore, "get_punny_jokes",
                      lambda ids: jokes)
  def _fake_generate_pinterest_post_text(post, pin_image_bytes):
    assert pin_image_bytes.startswith(b"\x89PNG")
    assert post.type == models.JokeSocialPostType.JOKE_GRID_TEASER
    post.pinterest_title = "Title"
    post.pinterest_description = "Description"
    post.pinterest_alt_text = "Alt text"
    return post

  monkeypatch.setattr(
    social_fns.social_operations,
    "generate_pinterest_post_text",
    _fake_generate_pinterest_post_text,
  )

  create_image_mock = Mock(
    return_value=Image.new('RGB', (1000, 500), color='white'))
  monkeypatch.setattr(
    social_fns.social_operations.image_operations,
    "create_pinterest_pin_image",
    create_image_mock,
  )

  monkeypatch.setattr(social_fns.social_operations.cloud_storage,
                      "get_image_gcs_uri",
                      lambda base, ext: "gs://bucket/pin.png")
  monkeypatch.setattr(social_fns.social_operations.cloud_storage,
                      "upload_bytes_to_gcs",
                      lambda _bytes, _uri, _content_type: None)
  monkeypatch.setattr(social_fns.social_operations.cloud_storage,
                      "get_public_cdn_url",
                      lambda _uri: "https://cdn.example.com/pin.png")
  created_post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID_TEASER,
    pinterest_title="Title",
    pinterest_description="Description",
    pinterest_alt_text="Alt text",
    jokes=jokes,
    pinterest_image_url="https://cdn.example.com/pin.png",
  )
  created_post.key = "post1"
  create_mock = Mock(return_value=created_post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", create_mock)

  req = DummyReq(data={"joke_ids": joke_ids, "type": "JOKE_GRID_TEASER"})
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "Title"
  assert post_data["pinterest_description"] == "Description"
  assert post_data["pinterest_alt_text"] == "Alt text"
  assert post_data["pinterest_image_url"] == "https://cdn.example.com/pin.png"
  assert post_data["type"] == "JOKE_GRID_TEASER"

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
  assert [joke.key for joke in created_arg.jokes] == ["j1", "j2"]
  assert [joke.setup_text for joke in created_arg.jokes] == [
    "Setup 1",
    "Setup 2",
  ]
  assert [joke.punchline_text for joke in created_arg.jokes] == [
    "Punch 1",
    "Punch 2",
  ]
  assert created_arg.pinterest_image_url == "https://cdn.example.com/pin.png"


def test_social_post_creation_process_invalid_type(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  req = DummyReq(data={"joke_ids": ["j1"], "type": "BAD"})
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert "type must be one of" in payload["data"]["error"]


def test_social_post_creation_process_updates_text_manual(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    pinterest_title="Old",
    pinterest_description="Old desc",
    pinterest_alt_text="Old alt",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)
  monkeypatch.setattr(social_fns.social_operations,
                      "generate_pinterest_post_text",
                      Mock(side_effect=AssertionError("LLM should not run")))

  req = DummyReq(
    data={
      "post_id": "post1",
      "pinterest_title": "New title",
      "pinterest_description": "",
    },
  )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "New title"
  assert post_data["pinterest_description"] == ""
  assert post_data["pinterest_alt_text"] == "Old alt"
  update_mock.assert_called_once()


def test_social_post_creation_process_regenerates_text(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    pinterest_image_url="https://cdn.example.com/pin.png",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  monkeypatch.setattr(
    social_fns.social_operations.cloud_storage,
    "extract_gcs_uri_from_image_url",
    lambda _url: "gs://bucket/pin.png",
  )
  monkeypatch.setattr(social_fns.social_operations.cloud_storage,
                      "download_bytes_from_gcs",
                      lambda _uri: b"image-bytes")

  def _fake_generate_text(post, pin_image_bytes):
    post.pinterest_title = "New"
    post.pinterest_description = "Desc"
    post.pinterest_alt_text = "Alt"
    return post

  monkeypatch.setattr(
    social_fns.social_operations,
    "generate_pinterest_post_text",
    _fake_generate_text,
  )
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={"post_id": "post1", "regenerate_text": True})
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "New"
  assert post_data["pinterest_description"] == "Desc"
  assert post_data["pinterest_alt_text"] == "Alt"
  assert post_data["pinterest_image_url"] == "https://cdn.example.com/pin.png"
  update_mock.assert_called_once()


def test_social_post_creation_process_regenerates_text_and_image(
  monkeypatch: pytest.MonkeyPatch,
):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID_TEASER,
    jokes=[
      models.PunnyJoke(key="j1", setup_text="Setup 1",
                       punchline_text="Punch 1"),
      models.PunnyJoke(key="j2", setup_text="Setup 2",
                       punchline_text="Punch 2"),
    ],
    pinterest_image_url="https://cdn.example.com/old.png",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  captured = {}

  def _fake_create_assets(post):
    captured["joke_ids"] = [j.key for j in post.jokes if j.key]
    captured["post_type"] = post.type
    post.pinterest_image_url = "https://cdn.example.com/new.png"
    return post, b"new-image"

  monkeypatch.setattr(social_fns.social_operations,
                      "create_pinterest_pin_assets", _fake_create_assets)
  def _fake_generate_text(post, pin_image_bytes):
    post.pinterest_title = "New"
    post.pinterest_description = "Desc"
    post.pinterest_alt_text = "Alt"
    return post

  monkeypatch.setattr(
    social_fns.social_operations,
    "generate_pinterest_post_text",
    _fake_generate_text,
  )
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(
    data={
      "post_id": "post1",
      "regenerate_text": True,
      "regenerate_image": True,
    },
  )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_image_url"] == "https://cdn.example.com/new.png"
  update_mock.assert_called_once()
  assert captured["joke_ids"] == ["j1", "j2"]
  assert captured["post_type"] == models.JokeSocialPostType.JOKE_GRID_TEASER


def test_social_post_creation_process_regenerate_overrides_manual(monkeypatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    pinterest_title="Old",
    pinterest_image_url="https://cdn.example.com/pin.png",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)
  monkeypatch.setattr(
    social_fns.social_operations.cloud_storage,
    "extract_gcs_uri_from_image_url",
    lambda _url: "gs://bucket/pin.png",
  )
  monkeypatch.setattr(social_fns.social_operations.cloud_storage,
                      "download_bytes_from_gcs",
                      lambda _uri: b"image-bytes")
  def _fake_generate_text(post, pin_image_bytes):
    post.pinterest_title = "Generated"
    post.pinterest_description = "Generated desc"
    post.pinterest_alt_text = "Generated alt"
    return post

  monkeypatch.setattr(
    social_fns.social_operations,
    "generate_pinterest_post_text",
    _fake_generate_text,
  )

  req = DummyReq(
    data={
      "post_id": "post1",
      "pinterest_title": "Manual",
      "regenerate_text": True,
    },
  )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "Generated"
  update_mock.assert_called_once()
