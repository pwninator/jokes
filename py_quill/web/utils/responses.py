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
  vary_cookie: bool = False,
) -> flask.Response:
  """Create an HTML response with caching + ETag headers."""
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  payload = html.encode('utf-8')
  resp.headers['ETag'] = hashlib.md5(payload).hexdigest()  # nosec B303
  resp.headers['Cache-Control'] = (
    f'public, max-age={cache_seconds}, s-maxage={cdn_seconds}, '
    'stale-while-revalidate=86400')
  if vary_cookie:
    existing_vary = resp.headers.get('Vary')
    vary_values = []
    if existing_vary:
      vary_values.extend(
        value.strip() for value in existing_vary.split(',') if value.strip())
    if 'cookie' not in {value.lower() for value in vary_values}:
      vary_values.append('Cookie')
    resp.headers['Vary'] = ', '.join(vary_values)
  resp.headers['Last-Modified'] = (datetime.datetime.now(
    datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
  return resp


def html_no_store_response(html: str, *, status: int = 200) -> flask.Response:
  """Create an HTML response that should never be cached."""
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  resp.headers['Cache-Control'] = 'no-store'
  return resp
