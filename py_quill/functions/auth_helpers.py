"""Authentication helpers for admin web routes."""

from __future__ import annotations

import datetime
import functools
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import flask
from firebase_admin import auth
from firebase_functions import logger
from common import config
from common import utils


def create_session_cookie(id_token: str) -> str:
  """Exchange an ID token for a Firebase session cookie."""
  expires_in = datetime.timedelta(seconds=config.SESSION_MAX_AGE_SECONDS)
  session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)
  logger.info('Created admin session cookie')
  return session_cookie


def set_session_cookie(response: flask.Response,
                       session_cookie: str,
                       *,
                       domain: str | None = None) -> None:
  """Attach the session cookie to the response."""
  response.set_cookie(
    config.SESSION_COOKIE_NAME,
    session_cookie,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    httponly=True,
    secure=True,
    samesite='Lax',
    domain=domain,
    path='/',
  )

  # If we scoped the cookie to the parent domain (".snickerdoodlejokes.com"),
  # also set a host-only cookie for the same host. This overwrites any legacy
  # host-only value so we don't end up with two different __session cookies
  # being sent to snickerdoodlejokes.com.
  if domain and domain.startswith('.') and not utils.is_emulator():
    response.set_cookie(
      config.SESSION_COOKIE_NAME,
      session_cookie,
      max_age=config.SESSION_MAX_AGE_SECONDS,
      httponly=True,
      secure=True,
      samesite='Lax',
      path='/',
    )


def clear_session_cookie(response: flask.Response,
                         *,
                         domain: str | None = None) -> None:
  """Remove the session cookie from the response."""
  response.set_cookie(
    config.SESSION_COOKIE_NAME,
    '',
    expires=0,
    httponly=True,
    secure=True,
    samesite='Lax',
    domain=domain,
    path='/',
  )

  # See set_session_cookie() for why we clear a host-only cookie too.
  if domain and domain.startswith('.') and not utils.is_emulator():
    response.set_cookie(
      config.SESSION_COOKIE_NAME,
      '',
      expires=0,
      httponly=True,
      secure=True,
      samesite='Lax',
      path='/',
    )


def external_host_for_request(request: flask.Request) -> str | None:
  """Return the externally visible host for the current request."""
  if utils.is_emulator():
    host = (request.host or '').split(':')[0]
    return host.lower() if host else 'localhost'
  return config.ADMIN_HOST


def external_scheme_for_request(request: flask.Request) -> str:
  """Return the externally visible scheme (http/https)."""
  if utils.is_emulator():
    return request.scheme or 'http'
  return 'https'


def cookie_domain_for_request(request: flask.Request) -> str | None:
  """Determine the cookie domain for the current request."""
  host = external_host_for_request(request)
  if not host:
    return None

  if utils.is_emulator():
    return host

  # In production we want the admin session cookie to be shared across
  # snickerdoodlejokes.com and api.snickerdoodlejokes.com.
  parent = config.ADMIN_HOST.lstrip(".").lower()
  return f".{parent}"


def resolve_admin_redirect(request: flask.Request, target: str | None,
                           fallback_path: str) -> str:
  """Normalise an admin redirect target to an absolute on-site URL."""
  host = external_host_for_request(request)
  scheme = external_scheme_for_request(request)
  if not host:
    return target or fallback_path

  chosen = target or fallback_path
  parsed = urlparse(chosen)
  # Strip external hosts; only keep path/query from relative targets.
  if parsed.scheme or parsed.netloc:
    path = parsed.path or '/'
    query = f"?{parsed.query}" if parsed.query else ''
    chosen = f"{path}{query}"

  if not chosen.startswith('/'):
    chosen = '/' + chosen

  return urlunparse((scheme, host, chosen, '', '', ''))


def verify_session(request: flask.Request, ) -> Optional[Tuple[str, dict]]:
  """Verify the admin session cookie, returning (uid, claims) if valid."""
  session_cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
  if not session_cookie:
    return None

  try:
    decoded = auth.verify_session_cookie(session_cookie, check_revoked=True)
  except auth.RevokedSessionCookieError:
    logger.warn('Revoked admin session cookie encountered')
    return None
  except auth.InvalidSessionCookieError:
    logger.warn('Invalid admin session cookie encountered')
    return None
  except Exception as exc:  # pragma: no cover - defensive
    logger.error(f'Unexpected error verifying session cookie: {exc}')
    return None

  uid = decoded.get('uid')
  if not uid:
    logger.warn('Session cookie missing uid claim')
    return None

  return uid, decoded


def require_admin(view_func: Callable) -> Callable:
  """Decorator enforcing that the request comes from an admin user."""

  @functools.wraps(view_func)
  def wrapper(*args, **kwargs):
    if utils.is_emulator():
      return view_func(*args, **kwargs)

    verification = verify_session(flask.request)
    if not verification:
      logger.warn(
        'Unauthenticated access to admin route %s (host=%s xfh=%s scheme=%s cookies=%s)',
        flask.request.path,
        flask.request.host,
        flask.request.headers.get('X-Forwarded-Host'),
        flask.request.scheme,
        flask.request.headers.get('Cookie'),
      )
      login_path = flask.url_for('web.login', next=flask.request.path)
      login_url = resolve_admin_redirect(flask.request, login_path,
                                         flask.url_for('web.login'))
      return flask.redirect(login_url)

    _, claims = verification
    role = claims.get('role')
    if role != 'admin':
      logger.warn('Forbidden access to admin route %s with role %s',
                  flask.request.path, role)
      return flask.Response('Forbidden', status=403)

    return view_func(*args, **kwargs)

  return wrapper
