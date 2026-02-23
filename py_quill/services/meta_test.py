"""Tests for Meta Graph API helpers."""

from __future__ import annotations

import json

from common import config, models
from services import meta


class _FakeResponse:

  def __init__(self, status_code: int, payload: dict):
    self.status_code = status_code
    self._payload = payload
    self.text = json.dumps(payload)

  def json(self):
    return self._payload


def _make_image(url: str, alt_text: str | None = None) -> models.Image:
  return models.Image(url=url, alt_text=alt_text)


def test_publish_instagram_single_image(monkeypatch):
  monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "ig_1")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"id": "container_1"}),
    _FakeResponse(200, {"id": "media_1"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_instagram_post(
    images=[_make_image("https://example.com/ig.png")],
    caption="Hello",
  )

  assert result == "media_1"
  assert calls[0]["url"].endswith("/v24.0/ig_1/media")
  assert calls[0]["data"]["image_url"] == "https://example.com/ig.png"
  assert calls[0]["data"]["caption"] == "Hello"
  assert calls[1]["url"].endswith("/v24.0/ig_1/media_publish")
  assert calls[1]["data"]["creation_id"] == "container_1"


def test_publish_instagram_single_image_includes_alt_text(monkeypatch):
  monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "ig_1")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"id": "container_1"}),
    _FakeResponse(200, {"id": "media_1"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_instagram_post(
    images=[_make_image("https://example.com/ig.png", alt_text="Alt text")],
    caption="Hello",
  )

  assert result == "media_1"
  assert calls[0]["data"]["alt_text"] == "Alt text"


def test_publish_instagram_carousel(monkeypatch):
  monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "ig_2")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"id": "item_1"}),
    _FakeResponse(200, {"id": "item_2"}),
    _FakeResponse(200, {"id": "carousel_1"}),
    _FakeResponse(200, {"id": "media_2"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_instagram_post(
    images=[
      _make_image("https://example.com/1.png"),
      _make_image("https://example.com/2.png"),
    ],
    caption="Carousel",
  )

  assert result == "media_2"
  assert calls[0]["data"]["is_carousel_item"] == "true"
  assert calls[1]["data"]["is_carousel_item"] == "true"
  assert calls[2]["data"]["media_type"] == "CAROUSEL"
  assert calls[2]["data"]["children"] == "item_1,item_2"


def test_publish_instagram_carousel_alt_text_for_each_image(monkeypatch):
  monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "ig_2")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"id": "item_1"}),
    _FakeResponse(200, {"id": "item_2"}),
    _FakeResponse(200, {"id": "carousel_1"}),
    _FakeResponse(200, {"id": "media_2"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_instagram_post(
    images=[
      _make_image("https://example.com/1.png", alt_text="Alt text 1"),
      _make_image("https://example.com/2.png", alt_text="Alt text 2"),
    ],
    caption="Carousel",
  )

  assert result == "media_2"
  assert calls[0]["data"]["alt_text"] == "Alt text 1"
  assert calls[1]["data"]["alt_text"] == "Alt text 2"


def test_publish_facebook_single_with_alt_text(monkeypatch):
  monkeypatch.setattr(config, "FACEBOOK_PAGE_ID", "page_1")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"access_token": "page_token_1"}),
    _FakeResponse(200, {"post_id": "post_1"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_facebook_post(
    images=[_make_image("https://example.com/fb.png", alt_text="Alt text")],
    message="FB post",
  )

  assert result == "post_1"
  assert calls[0]["url"].endswith("/v24.0/page_1")
  assert calls[0]["params"]["fields"] == "access_token"
  assert calls[1]["url"].endswith("/v24.0/page_1/photos")
  assert calls[1]["data"]["alt_text_custom"] == "Alt text"
  assert calls[1]["data"]["access_token"] == "page_token_1"


def test_publish_facebook_carousel_alt_text_for_each_image(monkeypatch):
  monkeypatch.setattr(config, "FACEBOOK_PAGE_ID", "page_2")
  monkeypatch.setattr(config, "get_meta_long_lived_token", lambda: "token")

  calls = []
  responses = [
    _FakeResponse(200, {"access_token": "page_token_2"}),
    _FakeResponse(200, {"id": "photo_1"}),
    _FakeResponse(200, {"id": "photo_2"}),
    _FakeResponse(200, {"id": "post_2"}),
  ]

  def fake_request(method, url, params=None, data=None, timeout=None):
    calls.append({
      "method": method,
      "url": url,
      "data": data,
      "params": params
    })
    return responses.pop(0)

  monkeypatch.setattr(meta.requests, "request", fake_request)

  result = meta.publish_facebook_post(
    images=[
      _make_image("https://example.com/1.png", alt_text="Alt text 1"),
      _make_image("https://example.com/2.png", alt_text="Alt text 2"),
    ],
    message="Multi",
  )

  assert result == "post_2"
  assert calls[0]["url"].endswith("/v24.0/page_2")
  assert calls[1]["data"]["alt_text_custom"] == "Alt text 1"
  assert calls[1]["data"]["access_token"] == "page_token_2"
  assert calls[2]["data"]["alt_text_custom"] == "Alt text 2"
  attached_media = json.loads(calls[3]["data"]["attached_media"])
  assert attached_media == [{
    "media_fbid": "photo_1"
  }, {
    "media_fbid": "photo_2"
  }]
