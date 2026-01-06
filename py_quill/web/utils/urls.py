"""URL helpers for the public web layer."""

from __future__ import annotations

import os

import flask


def public_base_url() -> str:
  """Return the canonical public base URL for SEO links."""
  base_url = os.environ.get('PUBLIC_BASE_URL',
                            'https://snickerdoodlejokes.com')
  return base_url.rstrip('/')


def canonical_url(path: str, query: str | None = None) -> str:
  """Build a canonical absolute URL from a path and optional query string."""
  normalized_path = path if path.startswith('/') else f'/{path}'
  base_url = public_base_url()
  if normalized_path == '/':
    url = f'{base_url}/'
  else:
    url = f'{base_url}{normalized_path}'
  if query:
    return f'{url}?{query}'
  return url


def canonical_url_for_request(req: flask.Request,
                              include_query: bool = False) -> str:
  """Return a canonical URL for the current request."""
  query = None
  if include_query and req.query_string:
    query = req.query_string.decode('utf-8')
  return canonical_url(req.path, query=query)
