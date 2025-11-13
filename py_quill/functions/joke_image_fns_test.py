"""Tests for the joke_image_fns module."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from firebase_functions import https_fn

from functions import joke_image_fns


class DummyReq:
  """Minimal request stub for testing."""

  def __init__(self,
               *,
               method: str = 'POST',
               data: dict | None = None,
               args: dict | None = None,
               path: str = ""):
    self.method = method
    self.is_json = True
    self._data = data or {}
    self.args = args or {}
    self.path = path

  def get_json(self):
    return {"data": self._data}


def _html_response(resp: https_fn.Response) -> str:
  """Decode HTML response body."""
  return resp.get_data(as_text=True)


def _json_payload(resp: https_fn.Response) -> dict:
  """Parse JSON response body."""
  return json.loads(resp.get_data(as_text=True))


def test_create_ad_assets_returns_html(monkeypatch: pytest.MonkeyPatch):
  """Successful requests should return HTML rendering the creative."""
  called_ids: list[str] = []

  def _fake_create(joke_id: str, *, overwrite: bool = False) -> list[str]:
    called_ids.append(joke_id)
    return [f'https://cdn.example.com/{joke_id}.png']

  monkeypatch.setattr(joke_image_fns.image_operations, 'create_ad_assets',
                      _fake_create)

  def _fake_set_params(cdn_url: str, width: int | None = None,
                       image_format: str | None = None,
                       quality: int | None = None) -> str:
    return cdn_url

  monkeypatch.setattr(joke_image_fns.cloud_storage, 'set_cdn_url_params',
                      _fake_set_params)

  req = DummyReq(data={'joke_ids': 'joke123, joke456 '})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'text/html'
  assert resp.status_code == 200
  html = _html_response(resp)
  assert called_ids == ['joke123', 'joke456']
  assert html.count('<img') == 2
  assert 'https://cdn.example.com/joke123.png' in html
  assert 'https://cdn.example.com/joke456.png' in html


def test_create_ad_assets_uses_top_jokes_when_missing_param(
    monkeypatch: pytest.MonkeyPatch):
  """When joke_ids missing, fallback to top jokes."""
  mock_top_jokes = [
    Mock(key=f'top{i}')
    for i in range(1, joke_image_fns._DEFAULT_TOP_JOKES_LIMIT + 1)
  ]
  monkeypatch.setattr(joke_image_fns.firestore, 'get_top_jokes',
                      Mock(return_value=mock_top_jokes))

  called_ids: list[str] = []

  def _fake_create(joke_id: str, *, overwrite: bool = False) -> list[str]:
    called_ids.append(joke_id)
    return [f'https://cdn.example.com/{joke_id}.png']

  monkeypatch.setattr(joke_image_fns.image_operations, 'create_ad_assets',
                      _fake_create)

  def _fake_set_params(cdn_url: str, width: int | None = None,
                       image_format: str | None = None,
                       quality: int | None = None) -> str:
    return cdn_url

  monkeypatch.setattr(joke_image_fns.cloud_storage, 'set_cdn_url_params',
                      _fake_set_params)

  req = DummyReq(data={})

  resp = joke_image_fns.create_ad_assets(req)

  joke_image_fns.firestore.get_top_jokes.assert_called_once_with(
    'popularity_score_recent', joke_image_fns._DEFAULT_TOP_JOKES_LIMIT)
  expected_ids = [
    f'top{i}' for i in range(1, joke_image_fns._DEFAULT_TOP_JOKES_LIMIT + 1)
  ]
  assert called_ids == expected_ids
  assert resp.mimetype == 'text/html'
  assert resp.status_code == 200
  html = _html_response(resp)
  assert html.count('<img') == len(expected_ids)
  for joke_id in expected_ids:
    assert f'https://cdn.example.com/{joke_id}.png' in html


def test_create_ad_assets_no_top_jokes_available(
    monkeypatch: pytest.MonkeyPatch):
  """If no jokes available, return a 404 error."""
  monkeypatch.setattr(joke_image_fns.firestore, 'get_top_jokes',
                      Mock(return_value=[]))
  mock_create = Mock()
  monkeypatch.setattr(joke_image_fns.image_operations, 'create_ad_assets',
                      mock_create)

  req = DummyReq(data={})

  resp = joke_image_fns.create_ad_assets(req)

  joke_image_fns.firestore.get_top_jokes.assert_called_once_with(
    'popularity_score_recent',
    joke_image_fns._DEFAULT_TOP_JOKES_LIMIT,
  )
  mock_create.assert_not_called()
  assert resp.mimetype == 'application/json'
  assert resp.status_code == 404
  payload = _json_payload(resp)
  assert payload == {
    'success': False,
    'error': 'No jokes available to create ad assets',
  }


def test_create_ad_assets_value_error(monkeypatch: pytest.MonkeyPatch):
  """ValueErrors from image operations should surface as 400 responses."""

  def _fake_create(joke_id: str, *, overwrite: bool = False) -> list[str]:
    if joke_id == 'joke_bad':
      raise ValueError('Joke missing')
    return [f'https://cdn.example.com/{joke_id}.png']

  monkeypatch.setattr(joke_image_fns.image_operations, 'create_ad_assets',
                      _fake_create)

  req = DummyReq(data={'joke_ids': 'joke_good, joke_bad'})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'application/json'
  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert payload == {
    'success': False,
    'error': 'joke_bad: Joke missing',
  }


def test_create_ad_assets_method_not_allowed():
  """Non-GET/POST methods should be rejected."""
  req = DummyReq(method='PUT', data={'joke_ids': 'j1'})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'application/json'
  assert resp.status_code == 405
  payload = _json_payload(resp)
  assert payload['success'] is False
  assert payload['error'].startswith('Method not allowed')
