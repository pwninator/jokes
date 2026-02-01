"""Tests for social_fns."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

import pytest
from common import models
from functions import joke_creation_fns
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
  return resp.get_json()


@pytest.fixture(autouse=True)
def _stub_recent_posts(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(
    social_fns.social_operations.firestore,
    "get_joke_social_posts",
    lambda **_kwargs: [],
  )


def test_social_post_creation_process_success(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  joke_ids = ["j1", "j2"]
  jokes = [
    models.PunnyJoke(key="j1", setup_text="Setup 1", punchline_text="Punch 1"),
    models.PunnyJoke(key="j2", setup_text="Setup 2", punchline_text="Punch 2"),
  ]
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_punny_jokes", lambda ids: jokes)
  expected_link_url = ("https://snickerdoodlejokes.com/jokes/"
                       f"{jokes[-1].human_readable_setup_text_slug}")

  def _fake_prompt(pin_image_bytes: list[bytes], *, post_type, recent_posts):
    assert pin_image_bytes[0].startswith(b"\x89PNG")
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    assert recent_posts == []
    return "Title", "Description", "Alt text", {}

  def _fake_instagram_prompt(image_bytes: list[bytes], *, post_type,
                             recent_posts):
    assert image_bytes[0].startswith(b"\x89PNG")
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    assert recent_posts == []
    return "IG caption", "IG alt", {}

  def _fake_facebook_prompt(image_bytes: list[bytes], *, post_type, link_url,
                            recent_posts):
    assert image_bytes[0].startswith(b"\x89PNG")
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    assert link_url == expected_link_url
    assert recent_posts == []
    return "FB message", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)
  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_instagram_post_text", _fake_instagram_prompt)
  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_facebook_post_text", _fake_facebook_prompt)

  create_image_mock = Mock(
    return_value=Image.new('RGB', (1000, 500), color='white'))
  create_4by5_image_mock = Mock(
    return_value=Image.new('RGB', (1000, 1000), color='white'))
  monkeypatch.setattr(
    social_fns.social_operations.image_operations,
    "create_joke_grid_image_3x2",
    create_image_mock,
  )
  monkeypatch.setattr(
    social_fns.social_operations.image_operations,
    "create_joke_grid_image_4by5",
    create_4by5_image_mock,
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

  req = DummyReq(
    data={
      "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
      "joke_ids": joke_ids,
      "type": "JOKE_GRID_TEASER",
    })
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  # link_url is used by the Facebook prompt generator.
  assert post_data["pinterest_title"] == "Title"
  assert post_data["pinterest_description"] == "Description"
  assert post_data["pinterest_alt_text"] == "Alt text"
  assert post_data["pinterest_image_urls"] == [
    "https://cdn.example.com/pin.png"
  ]
  assert post_data["instagram_caption"] == "IG caption"
  assert post_data["instagram_alt_text"] == "IG alt"
  assert post_data["instagram_image_urls"] == [
    "https://cdn.example.com/pin.png"
  ]
  assert post_data["facebook_message"] == "FB message"
  assert post_data["facebook_image_urls"] == [
    "https://cdn.example.com/pin.png"
  ]
  assert post_data["type"] == "JOKE_GRID_TEASER"
  assert post_data["link_url"] == expected_link_url

  create_image_mock.assert_called_once_with(
    jokes=jokes,
    block_last_panel=True,
  )
  assert create_4by5_image_mock.call_count == 1
  create_4by5_image_mock.assert_called_with(
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
  assert created_arg.instagram_caption == "IG caption"
  assert created_arg.instagram_alt_text == "IG alt"
  assert created_arg.facebook_message == "FB message"
  assert [joke.key for joke in created_arg.jokes] == ["j1", "j2"]
  assert [joke.setup_text for joke in created_arg.jokes] == [
    "Setup 1",
    "Setup 2",
  ]
  assert [joke.punchline_text for joke in created_arg.jokes] == [
    "Punch 1",
    "Punch 2",
  ]
  assert created_arg.pinterest_image_urls == [
    "https://cdn.example.com/pin.png"
  ]
  assert created_arg.instagram_image_urls == [
    "https://cdn.example.com/pin.png"
  ]
  assert created_arg.facebook_image_urls == ["https://cdn.example.com/pin.png"]
  assert created_arg.link_url == expected_link_url


def test_initialize_social_post_joke_grid_picks_most_shared_tag(
    monkeypatch: pytest.MonkeyPatch):
  jokes = [
    models.PunnyJoke(key="j1",
                     setup_text="Setup 1",
                     punchline_text="Punch 1",
                     tags=["cat", "dog"]),
    models.PunnyJoke(key="j2",
                     setup_text="Setup 2",
                     punchline_text="Punch 2",
                     tags=["cat", "fish"]),
    models.PunnyJoke(key="j3",
                     setup_text="Setup 3",
                     punchline_text="Punch 3",
                     tags=["dog", "cat"]),
  ]
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_punny_jokes", lambda ids: jokes)

  post, _updated = social_fns.social_operations.initialize_social_post(
    post_id=None,
    joke_ids=["j1", "j2", "j3"],
    post_type=models.JokeSocialPostType.JOKE_GRID,
  )

  assert post.link_url == "https://snickerdoodlejokes.com/jokes/cat"


def test_initialize_social_post_joke_grid_breaks_tie_by_earliest_tag_position(
    monkeypatch: pytest.MonkeyPatch):
  # dog and cat each appear in 2 jokes; dog wins because it appears at position 0,
  # while cat's lowest position is 1.
  jokes = [
    models.PunnyJoke(key="j1",
                     setup_text="Setup 1",
                     punchline_text="Punch 1",
                     tags=["dog", "cat"]),
    models.PunnyJoke(key="j2",
                     setup_text="Setup 2",
                     punchline_text="Punch 2",
                     tags=["bird", "cat"]),
    models.PunnyJoke(key="j3",
                     setup_text="Setup 3",
                     punchline_text="Punch 3",
                     tags=["dog", "fish"]),
  ]
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_punny_jokes", lambda ids: jokes)

  post, _updated = social_fns.social_operations.initialize_social_post(
    post_id=None,
    joke_ids=["j1", "j2", "j3"],
    post_type=models.JokeSocialPostType.JOKE_GRID,
  )

  assert post.link_url == "https://snickerdoodlejokes.com/jokes/dog"


def test_social_post_creation_process_invalid_type(
    monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  req = DummyReq(
    data={
      "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
      "joke_ids": ["j1"],
      "type": "BAD",
    })
  resp = joke_creation_fns.joke_creation_process(req)

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
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "pinterest_title": "New title",
    "pinterest_description": "",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

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
    pinterest_image_urls=["https://cdn.example.com/pin.png"],
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

  def _fake_prompt(pin_image_bytes: list[bytes], *, post_type, recent_posts):
    assert pin_image_bytes == [b"image-bytes"]
    assert post_type == models.JokeSocialPostType.JOKE_GRID
    assert recent_posts == []
    return "New", "Desc", "Alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(
    data={
      "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
      "post_id": "post1",
      "regenerate_text": True,
    })
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "New"
  assert post_data["pinterest_description"] == "Desc"
  assert post_data["pinterest_alt_text"] == "Alt"
  assert post_data["pinterest_image_urls"] == [
    "https://cdn.example.com/pin.png"
  ]
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
    pinterest_image_urls=["https://cdn.example.com/old.png"],
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  captured = {}

  def _fake_generate_images(post):
    captured["joke_ids"] = [j.key for j in post.jokes if j.key]
    captured["post_type"] = post.type
    post.pinterest_image_urls = ["https://cdn.example.com/new.png"]
    return post, {models.SocialPlatform.PINTEREST: [b"new-image"]}, True

  monkeypatch.setattr(social_fns.social_operations,
                      "generate_social_post_images", _fake_generate_images)

  def _fake_prompt(pin_image_bytes: list[bytes], *, post_type, recent_posts):
    assert pin_image_bytes == [b"new-image"]
    assert post_type == models.JokeSocialPostType.JOKE_GRID_TEASER
    assert recent_posts == []
    return "New", "Desc", "Alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)
  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "regenerate_text": True,
    "regenerate_image": True,
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_image_urls"] == [
    "https://cdn.example.com/new.png"
  ]
  update_mock.assert_called_once()
  assert captured["joke_ids"] == ["j1", "j2"]
  assert captured["post_type"] == models.JokeSocialPostType.JOKE_GRID_TEASER


def test_social_post_creation_process_regenerate_overrides_manual(monkeypatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/old",
    pinterest_title="Old",
    pinterest_image_urls=["https://cdn.example.com/pin.png"],
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

  def _fake_prompt(pin_image_bytes: list[bytes], *, post_type, recent_posts):
    assert pin_image_bytes == [b"image-bytes"]
    assert post_type == models.JokeSocialPostType.JOKE_GRID
    assert recent_posts == []
    return "Generated", "Generated desc", "Generated alt", {}

  monkeypatch.setattr(social_fns.social_operations.social_post_prompts,
                      "generate_pinterest_post_text", _fake_prompt)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "pinterest_title": "Manual",
    "regenerate_text": True,
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

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
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "instagram_caption": "New caption",
    "instagram_alt_text": "New alt",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

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
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "mark_posted_platform": "instagram",
    "platform_post_id": "ig-123",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["instagram_post_id"] == "ig-123"
  assert isinstance(post_data["instagram_post_time"], str)

  saved_post = update_mock.call_args[0][0]
  assert saved_post.instagram_post_id == "ig-123"
  assert isinstance(saved_post.instagram_post_time, datetime.datetime)


def test_social_post_creation_process_publish_platform_instagram(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/ig",
    instagram_caption="Caption",
    instagram_alt_text="Alt",
    instagram_image_urls=["https://cdn.example.com/ig.png"],
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  captured = {}

  def _fake_publish_instagram_post(*, images, caption, alt_text=None):
    captured["caption"] = caption
    captured["alt_text"] = alt_text
    captured["urls"] = [img.url for img in images]
    return "ig-999"

  monkeypatch.setattr(social_fns.social_operations.meta_service,
                      "publish_instagram_post", _fake_publish_instagram_post)

  update_mock = Mock(side_effect=lambda post, **_kwargs: post)
  monkeypatch.setattr(social_fns.firestore, "upsert_social_post", update_mock)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "publish_platform": "instagram",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["instagram_post_id"] == "ig-999"
  assert isinstance(post_data["instagram_post_time"], str)

  assert captured["caption"] == "Caption"
  assert captured["alt_text"] == "Alt"
  assert captured["urls"] == ["https://cdn.example.com/ig.png"]

  saved_post = update_mock.call_args[0][0]
  assert saved_post.instagram_post_id == "ig-999"

  assert update_mock.call_args.kwargs["operation"] == "PUBLISH_INSTAGRAM"


def test_social_post_creation_process_rejects_publish_and_manual_mark(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/ig",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "publish_platform": "instagram",
    "mark_posted_platform": "pinterest",
    "platform_post_id": "pin-1",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert "publish_platform cannot be combined" in payload["data"]["error"]


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
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "pinterest_title": "New",
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  post_data = payload["data"]["post_data"]
  assert post_data["pinterest_title"] == "Existing"
  update_mock.assert_not_called()


def test_social_post_creation_process_deletes_post(monkeypatch: pytest.MonkeyPatch):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/post",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  delete_mock = Mock(return_value=True)
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "delete_joke_social_post", delete_mock)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "delete": True,
    # Should be ignored.
    "regenerate_text": True,
    "type": "JOKE_GRID",
    "joke_ids": ["j1"],
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 200
  payload = _json_payload(resp)
  assert payload["data"]["post_id"] == "post1"
  assert payload["data"]["deleted"] is True
  delete_mock.assert_called_once_with("post1")


def test_social_post_creation_process_delete_rejects_posted(
  monkeypatch: pytest.MonkeyPatch, ):
  monkeypatch.setattr(social_fns.utils, "is_emulator", lambda: True)

  post = models.JokeSocialPost(
    type=models.JokeSocialPostType.JOKE_GRID,
    link_url="https://snickerdoodlejokes.com/jokes/post",
    instagram_post_id="ig-123",
  )
  post.key = "post1"
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "get_joke_social_post", lambda _post_id: post)

  delete_mock = Mock(return_value=True)
  monkeypatch.setattr(social_fns.social_operations.firestore,
                      "delete_joke_social_post", delete_mock)

  req = DummyReq(data={
    "op": joke_creation_fns.JokeCreationOp.SOCIAL.value,
    "post_id": "post1",
    "delete": True,
  }, )
  resp = joke_creation_fns.joke_creation_process(req)

  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert "Cannot delete" in payload["data"]["error"]
  delete_mock.assert_not_called()
