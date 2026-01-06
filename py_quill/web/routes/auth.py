"""Authentication routes for the web layer."""

from __future__ import annotations

import datetime
from urllib.parse import urlparse

import flask
from firebase_functions import logger

from common import config
from functions import auth_helpers
from web.routes import web_bp
from web.utils import urls
from web.utils.responses import html_no_store_response


def _firebase_web_config() -> dict[str, str]:
  """Return Firebase config for the web login."""
  return config.FIREBASE_WEB_CONFIG


def _is_admin_target(target: str | None) -> bool:
  """Return True if the redirect target points at an admin route."""
  if not target:
    return False

  parsed = urlparse(target)
  path = parsed.path or target
  if not path.startswith('/'):
    path = f'/{path}'
  return path.startswith('/admin')


@web_bp.route('/login')
def login():
  """Render the login page or redirect if already authenticated."""
  verification = auth_helpers.verify_session(flask.request)
  next_arg = flask.request.args.get('next')
  resolved_next = auth_helpers.resolve_admin_redirect(
    flask.request,
    next_arg,
    '/',
  )

  if verification:
    _, claims = verification
    role = claims.get('role')
    if not (_is_admin_target(next_arg) and role != 'admin'):
      return flask.redirect(resolved_next)

  html = flask.render_template(
    'login.html',
    firebase_config=_firebase_web_config(),
    login_next_url=resolved_next,
    canonical_url=urls.canonical_url(flask.url_for('web.login')),
    prev_url=None,
    next_url=None,
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return html_no_store_response(html)


@web_bp.route('/session', methods=['POST'])
def login_session():
  """Exchange an ID token for a session cookie."""
  payload = flask.request.get_json(silent=True) or {}
  id_token = payload.get('idToken')
  if not id_token:
    return flask.jsonify({'error': 'idToken is required'}), 400

  try:
    session_cookie = auth_helpers.create_session_cookie(id_token)
  except Exception as exc:
    logger.error(f'Failed to create session cookie: {exc}')
    return flask.jsonify({'error': 'Unauthorized'}), 401

  response = flask.jsonify({'status': 'ok'})
  cookie_domain = auth_helpers.cookie_domain_for_request(flask.request)
  auth_helpers.set_session_cookie(response,
                                  session_cookie,
                                  domain=cookie_domain)
  logger.info(
    'Issued session cookie (host=%s xfh=%s scheme=%s cookie_domain=%s)',
    flask.request.host,
    flask.request.headers.get('X-Forwarded-Host'),
    flask.request.scheme,
    cookie_domain,
  )
  return response


@web_bp.route('/logout', methods=['POST'])
def logout():
  """Clear the session cookie."""
  response = flask.jsonify({'status': 'signed_out'})
  cookie_domain = auth_helpers.cookie_domain_for_request(flask.request)
  auth_helpers.clear_session_cookie(response, domain=cookie_domain)
  return response


@web_bp.route('/session-info')
def session_info():
  """Return basic session info for client-side user menu rendering."""
  verification = auth_helpers.verify_session(flask.request)
  if not verification:
    response = flask.jsonify({'authenticated': False})
    response.headers['Cache-Control'] = 'no-store'
    return response

  _, claims = verification
  response = flask.jsonify({
    'authenticated': True,
    'email': claims.get('email'),
    'uid': claims.get('uid'),
    'role': claims.get('role'),
  })
  response.headers['Cache-Control'] = 'no-store'
  return response


@web_bp.route('/login-test')
def login_test():
  """Render a simple login state page for manual testing."""
  verification = auth_helpers.verify_session(flask.request)
  user_email = None
  if verification:
    _, claims = verification
    user_email = claims.get('email') or claims.get('uid')

  html = flask.render_template(
    'login_test.html',
    user_email=user_email,
    login_url=flask.url_for('web.login', next='/login-test'),
    logout_url=flask.url_for('web.logout'),
    canonical_url=urls.canonical_url(flask.url_for('web.login_test')),
    prev_url=None,
    next_url=None,
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return html_no_store_response(html)
