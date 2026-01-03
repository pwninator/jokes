"""Admin authentication routes (login + session cookie)."""

from __future__ import annotations

import flask
from firebase_functions import logger

from common import config
from functions import auth_helpers
from web.routes import web_bp


def _firebase_web_config() -> dict[str, str]:
  """Return Firebase config for the web admin login."""
  return config.FIREBASE_WEB_CONFIG


def _redirect_to_admin_dashboard() -> flask.Response:
  """Redirect helper that always points to the admin dashboard."""
  dashboard_path = flask.url_for('web.admin_dashboard')
  dashboard_url = auth_helpers.resolve_admin_redirect(flask.request,
                                                      dashboard_path,
                                                      dashboard_path)
  return flask.redirect(dashboard_url)


@web_bp.route('/admin/login')
def admin_login():
  """Render the admin login page with Google Sign-In."""
  verification = auth_helpers.verify_session(flask.request)
  if verification:
    _, claims = verification
    if claims.get('role') == 'admin':
      target = flask.request.args.get('next')
      if target:
        redirect_url = auth_helpers.resolve_admin_redirect(
          flask.request,
          target,
          flask.url_for('web.admin_dashboard'),
        )
        return flask.redirect(redirect_url)
      return _redirect_to_admin_dashboard()

  next_arg = flask.request.args.get('next')
  resolved_next = auth_helpers.resolve_admin_redirect(
    flask.request,
    next_arg,
    flask.url_for('web.admin_dashboard'),
  )
  firebase_config = _firebase_web_config()
  return flask.render_template(
    'admin/login.html',
    firebase_config=firebase_config,
    next_url=resolved_next,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/session', methods=['POST'])
def admin_session():
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
    'Issued admin session cookie (host=%s xfh=%s scheme=%s cookie_domain=%s)',
    flask.request.host,
    flask.request.headers.get('X-Forwarded-Host'),
    flask.request.scheme,
    cookie_domain,
  )
  return response


@web_bp.route('/admin/logout', methods=['POST'])
def admin_logout():
  """Clear the admin session cookie."""
  response = flask.jsonify({'status': 'signed_out'})
  cookie_domain = auth_helpers.cookie_domain_for_request(flask.request)
  auth_helpers.clear_session_cookie(response, domain=cookie_domain)
  return response
