"""Tests for response helpers."""

from __future__ import annotations

from web.app import app
from web.utils.responses import html_response


def test_html_response_no_store_when_cache_seconds_zero():
  """Cache disabled when cache_seconds is zero."""
  with app.test_request_context('/'):
    resp = html_response('ok', cache_seconds=0, cdn_seconds=1200)

  assert resp.headers['Cache-Control'] == 'private, no-store'


def test_html_response_private_when_cdn_disabled():
  """Browser-only caching when CDN seconds are zero."""
  with app.test_request_context('/'):
    resp = html_response('ok', cache_seconds=60, cdn_seconds=0)

  assert resp.headers['Cache-Control'] == 'private, max-age=60'


def test_html_response_private_when_cdn_seconds_none():
  """Browser-only caching when CDN seconds are None."""
  with app.test_request_context('/'):
    resp = html_response('ok', cache_seconds=60, cdn_seconds=None)

  assert resp.headers['Cache-Control'] == 'private, max-age=60'


def test_html_response_public_when_cdn_enabled():
  """Shared caching when CDN seconds are positive."""
  with app.test_request_context('/'):
    resp = html_response('ok', cache_seconds=60, cdn_seconds=120)

  assert resp.headers[
    'Cache-Control'] == ('public, max-age=60, s-maxage=120, '
                         'stale-while-revalidate=86400')
