"""Flask response helpers for HTML + caching headers."""

from __future__ import annotations

import datetime
import hashlib

import flask


def html_response(
  html: str,
  *,
  status: int = 200,
  cache_seconds: int = 300,
  cdn_seconds: int = 1800,
) -> flask.Response:
  """Create an HTML response with caching + ETag headers.

  Cache behavior:
  - cache_seconds <= 0: no caching anywhere (private, no-store).
  - cdn_seconds is None or <= 0: browser-only caching (private, max-age).
  - otherwise: browser + shared CDN caching (public, s-maxage).
  """
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  payload = html.encode('utf-8')
  resp.headers['ETag'] = hashlib.md5(payload).hexdigest()  # nosec B303
  if cache_seconds is None or cache_seconds <= 0:
    resp.headers['Cache-Control'] = 'private, no-store'
  elif cdn_seconds is None or cdn_seconds <= 0:
    resp.headers['Cache-Control'] = f'private, max-age={cache_seconds}'
  else:
    resp.headers['Cache-Control'] = (
      f'public, max-age={cache_seconds}, s-maxage={cdn_seconds}, '
      'stale-while-revalidate=86400')
  resp.headers['Last-Modified'] = (datetime.datetime.now(
    datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
  return resp


def html_no_store_response(html: str, *, status: int = 200) -> flask.Response:
  """Create an HTML response that should never be cached."""
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  resp.headers['Cache-Control'] = 'no-store'
  return resp
