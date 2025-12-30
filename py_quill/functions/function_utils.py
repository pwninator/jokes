"""Utility functions for Cloud Functions."""

import json
from typing import Any

from common import utils
from firebase_admin import auth
from firebase_functions import https_fn, logger


# CORS constants
_CORS_HEADERS = {
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Bundle-Secret",
}


def _allowed_origins() -> set[str]:
  """Return allowed origins based on environment (emulator vs prod)."""
  if utils.is_emulator():
    return {
      "http://127.0.0.1:5000",
      "http://localhost:5000",
      "http://127.0.0.1",
      "http://localhost",
      "http://localhost:5173", # Vite
    }
  else:
    return {
      "https://snickerdoodlejokes.com",
    }


def get_cors_headers(req: https_fn.Request | None) -> dict[str, str]:
  """Return CORS headers only for allowed origins."""
  if not req:
    return {}

  origin = req.headers.get("Origin")
  if origin and origin.rstrip("/") in _allowed_origins():
    return {**_CORS_HEADERS, "Access-Control-Allow-Origin": origin}

  # If origin is not in allowed origins, we might still want to allow specific cases
  # or just return empty. For now, strict checking as per previous implementation.
  return {}


def handle_cors_preflight(req: https_fn.Request) -> https_fn.Response | None:
  """Handle OPTIONS requests for CORS preflight."""
  if req.method == "OPTIONS":
    cors_headers = get_cors_headers(req) or _CORS_HEADERS
    return https_fn.Response(
      "",
      status=204,
      headers=cors_headers,
    )
  return None


def handle_health_check(req: https_fn.Request) -> https_fn.Response | None:
  """Handle health check requests."""
  if req.path == "/__/health":
    cors_headers = get_cors_headers(req)
    return https_fn.Response("OK", status=200, headers=cors_headers)
  return None


def get_user_id(
  req: https_fn.Request,
  allow_unauthenticated: bool = False,
) -> str | None:
  """Get the user's uid from the request."""
  auth_header = req.headers.get('Authorization')
  if not auth_header:
    if allow_unauthenticated:
      return None
    else:
      raise ValueError("Authorization header is missing")

  id_token = auth_header.split(' ')[1]

  try:
    decoded_token = auth.verify_id_token(id_token)
    return decoded_token['uid']
  except Exception as e:
    logger.error(f"Error verifying ID token '{id_token}': {e}")
    return None


def success_response(
  data: dict[str, Any],
  req: https_fn.Request | None = None,
  status: int = 200,
) -> https_fn.Response:
  """Return a success response with CORS headers."""
  logger.info(f"Success response: {data}")
  cors_headers = get_cors_headers(req)
  return https_fn.Response(
    json.dumps({"data": data}),
    status=status,
    headers=cors_headers,
    mimetype='application/json',
  )


def error_response(
  message: str,
  *,
  error_type: str | None = None,
  req: https_fn.Request | None = None,
  status: int = 500,
) -> https_fn.Response:
  """Return an error response with optional typed error code and CORS headers."""
  logger.error(f"Error response: {message} ({error_type})")
  payload: dict[str, Any] = {"error": message}
  if error_type:
    payload["error_type"] = error_type

  cors_headers = get_cors_headers(req)
  return https_fn.Response(
    json.dumps({"data": payload}),
    status=status,
    headers=cors_headers,
    mimetype='application/json',
  )


def html_response(
  html_content: str,
  req: https_fn.Request | None = None,
  status: int = 200,
) -> https_fn.Response:
  """Return an HTML response with CORS headers."""
  cors_headers = get_cors_headers(req)
  return https_fn.Response(
    html_content,
    status=status,
    headers={'Content-Type': 'text/html', **cors_headers},
  )


def get_param(
  req: https_fn.Request,
  param_name: str,
  default: Any | None = None,
  required: bool = False,
) -> Any | None:
  """Get a parameter from the request."""
  if req.is_json:
    json_data = req.get_json()
    data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
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


def get_bool_param(
  req: https_fn.Request,
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
  req: https_fn.Request,
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
  req: https_fn.Request,
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
