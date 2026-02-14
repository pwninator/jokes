"""Utility functions for Cloud Functions."""

import json
from http.cookies import SimpleCookie
from typing import Any, cast

import flask
from common import config, utils
from firebase_admin import auth
from firebase_functions import logger


class AuthError(Exception):
  """Raised when authentication or authorization fails."""


# CORS constants
_CORS_HEADERS = {
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers":
  "Content-Type, Authorization, X-Bundle-Secret",
  "Access-Control-Allow-Credentials": "true",
}


def _allowed_origins() -> set[str]:
  """Return allowed origins based on environment (emulator vs prod)."""
  if utils.is_emulator():
    return {
      "http://127.0.0.1:5000",
      "http://localhost:5000",
      "http://127.0.0.1",
      "http://localhost",
      "http://localhost:5173",  # Vite
    }
  else:
    return {
      "https://snickerdoodlejokes.com",
    }


def get_cors_headers(req: flask.Request | None) -> dict[str, str]:
  """Return CORS headers only for allowed origins."""
  if not req:
    return {}

  origin = req.headers.get("Origin")
  if origin and origin.rstrip("/") in _allowed_origins():
    return {
      **_CORS_HEADERS,
      "Access-Control-Allow-Origin": origin,
      "Vary": "Origin",
    }

  # If origin is not in allowed origins, we might still want to allow specific cases
  # or just return empty. For now, strict checking as per previous implementation.
  return {}


def handle_cors_preflight(req: flask.Request) -> flask.Response | None:
  """Handle OPTIONS requests for CORS preflight."""
  if req.method == "OPTIONS":
    cors_headers = get_cors_headers(req) or _CORS_HEADERS
    return flask.Response(
      "",
      status=204,
      headers=cors_headers,
    )
  return None


def handle_health_check(req: flask.Request) -> flask.Response | None:
  """Handle health check requests."""
  if req.path == "/__/health":
    cors_headers = get_cors_headers(req)
    return flask.Response("OK", status=200, headers=cors_headers)
  return None


def get_user_id(
  req: flask.Request,
  allow_unauthenticated: bool = False,
  require_admin: bool = False,
) -> str | None:
  """Get the user's uid from the request.

  Returns None only when unauthenticated access is allowed and no auth is present.
  Raises AuthError for any authentication/authorization failure.
  """

  uid = None
  is_admin = False
  if auth_header := req.headers.get('Authorization'):
    # Authorize with ID token (used by Flutter app)
    parts = auth_header.split(' ')
    if len(parts) < 2:
      raise AuthError("Authorization header is malformed")
    id_token = parts[1]

    try:
      decoded_token = cast(dict[str, object], auth.verify_id_token(id_token))
    except Exception as e:
      logger.error(f"Error verifying ID token '{id_token}': {e}")
      raise AuthError("Invalid authorization token") from e

    is_admin = _has_admin_role(decoded_token)
    uid = decoded_token.get('uid')
    if not uid:
      raise AuthError("Authorization token missing uid")

  elif verification := _get_session_claims(req):
    # Authorize with session cookie (used by web app)
    uid, claims = verification
    is_admin = _has_admin_role(claims)

  if require_admin and not is_admin:
    raise AuthError("Admin privileges required")
  if not allow_unauthenticated and not uid:
    raise AuthError("Authorization required")
  return cast(str, uid) if uid else None


def _has_admin_role(claims: dict | None) -> bool:
  return bool(claims and claims.get('role') == 'admin')


def _get_session_cookie(req: flask.Request) -> str | None:
  if hasattr(req, "cookies"):
    session_cookie = req.cookies.get(config.SESSION_COOKIE_NAME)
    if session_cookie:
      return session_cookie

  cookie_header = req.headers.get('Cookie') or req.headers.get('cookie')
  if not cookie_header:
    return None

  try:
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    session_cookie_morsel = cookies.get(config.SESSION_COOKIE_NAME)
    return session_cookie_morsel.value if session_cookie_morsel else None
  except Exception as e:
    logger.error(f"Error parsing session cookie header: {e}")
    return None


def _get_session_claims(
    req: flask.Request) -> tuple[str, dict[str, object]] | None:
  session_cookie = _get_session_cookie(req)
  if not session_cookie:
    return None
  try:
    decoded = cast(
      dict[str, object],
      auth.verify_session_cookie(session_cookie, check_revoked=True))
  except Exception as e:
    raise AuthError("Invalid session cookie") from e
  uid = decoded.get('uid')
  if not uid:
    raise AuthError("Session cookie missing uid claim")
  return cast(str, uid), decoded


def success_response(
  data: dict[str, Any],
  req: flask.Request | None = None,
  status: int = 200,
) -> flask.Response:
  """Return a success response with CORS headers."""
  logger.info(f"Success response: {data}")
  cors_headers = get_cors_headers(req)
  return flask.Response(
    json.dumps({"data": data}),
    status=status,
    headers=cors_headers,
    mimetype='application/json',
  )


def error_response(
  message: str,
  *,
  error_type: str | None = None,
  req: flask.Request | None = None,
  status: int = 500,
) -> flask.Response:
  """Return an error response with optional typed error code and CORS headers."""
  logger.error(f"Error response: {message} ({error_type})")
  payload: dict[str, Any] = {"error": message}
  if error_type:
    payload["error_type"] = error_type

  cors_headers = get_cors_headers(req)
  return flask.Response(
    json.dumps({"data": payload}),
    status=status,
    headers=cors_headers,
    mimetype='application/json',
  )


def html_response(
  html_content: str,
  req: flask.Request | None = None,
  status: int = 200,
) -> flask.Response:
  """Return an HTML response with CORS headers."""
  cors_headers = get_cors_headers(req)
  return flask.Response(
    html_content,
    status=status,
    headers={
      'Content-Type': 'text/html',
      **cors_headers
    },
  )


def get_param(
  req: flask.Request,
  param_name: str,
  default: Any | None = None,
  required: bool = False,
) -> Any | None:
  """Get a parameter from the request."""
  if req.is_json:
    json_data = req.get_json()
    data = cast(
      dict[str, object],
      json_data.get('data', {}) if isinstance(json_data, dict) else {})
    val = data.get(param_name, default)
  else:
    val = req.args.get(param_name, default)
    if (val is None or val == default) and hasattr(req, "form"):
      try:
        form_val = req.form.get(param_name)
        if form_val is not None:
          val = form_val
      except Exception:
        # If form is unavailable or raises, keep existing val
        pass

  if val is None and required:
    raise ValueError(f"Missing required parameter '{param_name}'")
  return val


def get_list_param(req: flask.Request, param_name: str) -> list[str]:
  """Get a list parameter from JSON, form, or query args."""
  if req.is_json:
    json_data = req.get_json()
    data = cast(
      dict[str, object],
      json_data.get('data', {}) if isinstance(json_data, dict) else {})
    value = cast(list[object] | str, data.get(param_name, []))
    if isinstance(value, list):
      return [str(item) for item in value if str(item)]
    if value:
      return [str(value)]
    return []

  if hasattr(req, "form"):
    return [str(item) for item in req.form.getlist(param_name) if str(item)]

  if hasattr(req, "args"):
    value = req.args.get(param_name)
    if value:
      return [str(value)]
  return []


def get_str_param(
  req: flask.Request,
  param_name: str,
  default: str | None = None,
  required: bool = False,
) -> str | None:
  """Get a string parameter from the request.

  Falls back to the provided default if the parameter is missing.
  """
  value = get_param(req, param_name, default, required=required)
  if value is None:
    return default
  return str(value)


def get_bool_param(
  req: flask.Request,
  param_name: str,
  default: bool = False,
  required: bool = False,
) -> bool:
  """Get a boolean parameter from the request."""
  str_param = get_param(req, param_name, str(default), required=required)
  if str_param is None:
    return default
  elif isinstance(str_param, bool):
    return str_param
  else:
    return str_param.lower() == 'true'


def get_int_param(
  req: flask.Request,
  param_name: str,
  default: int = 0,
  required: bool = False,
) -> int:
  """Get an integer parameter from the request.

  Falls back to the provided default if the parameter is missing or
  cannot be converted to an integer.
  """
  value = get_param(req, param_name, default, required=required)
  if value is None:
    return default
  if isinstance(value, int):
    return value
  try:
    return int(value)
  except (ValueError, TypeError):
    return default


def get_float_param(
  req: flask.Request,
  param_name: str,
  default: float = 0.0,
  required: bool = False,
) -> float:
  """Get a float parameter from the request.

  Falls back to the provided default if the parameter is missing or
  cannot be converted to a float.
  """
  value = get_param(req, param_name, default, required=required)
  if value is None:
    return default
  if isinstance(value, (float, int)):
    return float(value)
  try:
    return float(value)
  except (ValueError, TypeError):
    return default
