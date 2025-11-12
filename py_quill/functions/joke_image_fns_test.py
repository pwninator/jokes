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
  monkeypatch.setattr(joke_image_fns.image_operations,
                      'create_ad_assets',
                      lambda joke_id: f'https://cdn.example.com/{joke_id}.png')

  req = DummyReq(data={'joke_id': 'joke123'})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'text/html'
  assert resp.status_code == 200
  html = _html_response(resp)
  assert '<img' in html
  assert 'https://cdn.example.com/joke123.png' in html


def test_create_ad_assets_requires_joke_id(monkeypatch: pytest.MonkeyPatch):
  """Missing joke_id should return a 400 JSON error response."""
  req = DummyReq(data={})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'application/json'
  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert payload == {
    'success': False,
    'error': 'joke_id is required',
  }


def test_create_ad_assets_value_error(monkeypatch: pytest.MonkeyPatch):
  """ValueErrors from image operations should surface as 400 responses."""
  monkeypatch.setattr(joke_image_fns.image_operations,
                      'create_ad_assets',
                      Mock(side_effect=ValueError('Joke not found: jokeX')))

  req = DummyReq(data={'joke_id': 'jokeX'})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'application/json'
  assert resp.status_code == 400
  payload = _json_payload(resp)
  assert payload == {
    'success': False,
    'error': 'Joke not found: jokeX',
  }


def test_create_ad_assets_method_not_allowed():
  """Non-GET/POST methods should be rejected."""
  req = DummyReq(method='PUT', data={'joke_id': 'j1'})

  resp = joke_image_fns.create_ad_assets(req)

  assert resp.mimetype == 'application/json'
  assert resp.status_code == 405
  payload = _json_payload(resp)
  assert payload['success'] is False
  assert payload['error'].startswith('Method not allowed')


