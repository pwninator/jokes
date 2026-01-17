"""Tests for social_fns."""

from __future__ import annotations

import datetime
import json
from unittest.mock import Mock

import pytest
from common import models
from functions import social_fns
from PIL import Image


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
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_punny_jokes", lambda ids: jokes)

  def _fake_generate_pinterest_post_text(post, pin_image_bytes):
    assert pin_image_bytes.startswith(b"\x89PNG")
    assert post.type == models.JokeSocialPostType.JOKE_GRID_TEASER
    return post

  def _fake_prompt(pin_image_bytes: bytes, *, post_type):
    assert pin_image_bytes.startswith(b"\x89PNG")
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    return "Title", "Description", "Alt text", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)

  create_image_mock = Mock(
    return_value=Image.new('RGB', (1000, 500), color='white'))
  monkeypatch.setattr(
    social_fns.social_operations.image_operations,
    "create_joke_grid_image_3x2",
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

  def _fake_upsert(post, **_kwargs):
    post.key = "post1"
    return post

  create_mock = Mock(side_effect=_fake_upsert)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", create_mock)

  req = DummyReq(data={"joke_ids": joke_ids, "type": "JOKE_GRID_TEASER"})
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  expected_link_url = ("https://snickerdoodlejokes.com/jokes/"
                       f"{jokes[-1].human_readable_setup_text_slug}")
  assert post_data["pinterest_title"] == "Title"
  assert post_data["pinterest_description"] == "Description"
  assert post_data["pinterest_alt_text"] == "Alt text"
  assert post_data["pinterest_image_url"] == "https://cdn.example.com/pin.png"
  assert post_data["type"] == "JOKE_GRID_TEASER"
  assert post_data["link_url"] == expected_link_url

  create_image_mock.assert_called_once_with(
    jokes=jokes,
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
  assert created_arg.link_url == expected_link_url


def test_social_post_creation_process_invalid_type(
    monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  req = DummyReq(data={"joke_ids": ["j1"], "type": "BAD"})
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert "type must be one of" in payload["data"]["error"]


def test_social_post_creation_process_updates_text_manual(
    monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/old",
    pinterest_title="Old",
    pinterest_description="Old desc",
    pinterest_alt_text="Old alt",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)
  monkeypatch.setattr(
    social_fns.social_operations.social_post_prompts,
    "generate_pinterest_post_text",
    Mock(side_effect=AssertionError("LLM should not run")),
  )

  req = DummyReq(data={
    "post_id": "post1",
    "pinterest_title": "New title",
    "pinterest_description": "",
  }, )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "New title"
  assert post_data["pinterest_description"] == "Old desc"
  assert post_data["pinterest_alt_text"] == "Old alt"
  update_mock.assert_called_once()


def test_social_post_creation_process_regenerates_text(
    monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/pin",
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
                      "download_bytes_from_gcs", lambda _uri: b"image-bytes")

  def _fake_prompt(pin_image_bytes: bytes, *, post_type):
    assert pin_image_bytes == b"image-bytes"
    assert post_type == models.JokeSocialPostType.JOKE_GRID
    return "New", "Desc", "Alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)
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
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID_TEASER,
    link_url="https://snickerdoodlejokes.com/jokes/teaser",
    jokes=[
      models.PunnyJoke(key="j1",
                       setup_text="Setup 1",
                       punchline_text="Punch 1"),
      models.PunnyJoke(key="j2",
                       setup_text="Setup 2",
                       punchline_text="Punch 2"),
    ],
    pinterest_image_url="https://cdn.example.com/old.png",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  captured = {}

  def _fake_generate_images(post):
    captured["joke_ids"] = [j.key for j in post.jokes if j.key]
    captured["post_type"] = post.type
    post.pinterest_image_url = "https://cdn.example.com/new.png"
    return post, {models.SocialPlatform.PINTEREST: b"new-image"}, True

  monkeypatch.setattr(social_fns.social_operations, "generate_social_post_images",
                      _fake_generate_images)

  def _fake_prompt(pin_image_bytes: bytes, *, post_type):
    assert pin_image_bytes == b"new-image"
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    return "New", "Desc", "Alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "post_id": "post1",
    "regenerate_text": True,
    "regenerate_image": True,
  }, )
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
    link_url="https://snickerdoodlejokes.com/jokes/old",
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
                      "download_bytes_from_gcs", lambda _uri: b"image-bytes")

  def _fake_prompt(pin_image_bytes: bytes, *, post_type):
    assert pin_image_bytes == b"image-bytes"
    assert post_type == models.JokeSocialPostType.JOKE_GRID
    return "Generated", "Generated desc", "Generated alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)

  req = DummyReq(data={
    "post_id": "post1",
    "pinterest_title": "Manual",
    "regenerate_text": True,
  }, )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "Generated"
  update_mock.assert_called_once()


def test_social_post_creation_process_updates_instagram_fields(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/ig",
    instagram_caption="Old caption",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "post_id": "post1",
    "instagram_caption": "New caption",
    "instagram_alt_text": "New alt",
  }, )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["instagram_caption"] == "New caption"
  assert post_data["instagram_alt_text"] == "New alt"
  update_mock.assert_called_once()


def test_social_post_creation_process_marks_platform_posted(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/ig",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "post_id": "post1",
    "mark_posted_platform": "instagram",
    "platform_post_id": "ig-123",
  }, )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["instagram_post_id"] == "ig-123"
  assert isinstance(post_data["instagram_post_time"], str)

  saved_post = update_mock.call_args[0][0]
  assert saved_post.instagram_post_id == "ig-123"
  assert isinstance(saved_post.instagram_post_time, datetime.datetime)


def test_social_post_creation_process_skips_pinterest_updates_when_posted(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/pin",
    pinterest_title="Existing",
    pinterest_post_time=datetime.datetime(2024,
                                          1,
                                          2,
                                          tzinfo=datetime.timezone.utc),
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "post_id": "post1",
    "pinterest_title": "New",
  }, )
  resp = social_fns.social_post_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "Existing"
  update_mock.assert_not_called()
