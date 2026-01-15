"""Tests for canonical trailing slash redirects."""

from __future__ import annotations

from web.app import app


def test_trailing_slash_redirects_to_canonical_path():
  with app.test_client() as client:
    resp = client.get('/printables/notes/all/')

  assert resp.status_code == 308
  assert resp.headers["Location"] == "/printables/notes/all"


def test_trailing_slash_redirect_preserves_query_string():
  with app.test_client() as client:
    resp = client.get('/printables/notes/all/?source=test')

  assert resp.status_code == 308
  assert resp.headers["Location"] == "/printables/notes/all?source=test"
