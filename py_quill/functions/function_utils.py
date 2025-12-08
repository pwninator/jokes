"""Utility functions for Cloud Functions."""

from typing import Any

from firebase_admin import auth
from firebase_functions import https_fn, logger


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


def success_response(data: dict[str, Any]) -> https_fn.Response:
  """Return a success response."""
  logger.info(f"Success response: {data}")
  return {"data": data}


def error_response(
  message: str,
  *,
  error_type: str | None = None,
) -> https_fn.Response:
  """Return an error response with optional typed error code."""
  logger.error(f"Error response: {message} ({error_type})")
  payload: dict[str, Any] = {"error": message}
  if error_type:
    payload["error_type"] = error_type
  return {"data": payload}


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
