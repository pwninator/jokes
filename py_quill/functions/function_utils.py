"""Utility functions for Cloud Functions."""

from typing import Any

from firebase_admin import auth
from firebase_functions import https_fn


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
    print(f"Error verifying ID token '{id_token}': {e}")
    return None


def success_response(data: dict[str, Any]) -> https_fn.Response:
  """Return a success response."""
  print(f"Success response: {data}")
  return {"data": data}


def error_response(message: str) -> https_fn.Response:
  """Return an error response."""
  print(f"Error response: {message}")
  return {"data": {"error": message}}


def get_param(req: https_fn.Request,
              param_name: str,
              default: Any | None = None) -> Any | None:
  """Get a parameter from the request."""
  if req.is_json:
    json_data = req.get_json()
    data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
    return data.get(param_name, default)
  else:
    return req.args.get(param_name, default)


def get_bool_param(req: https_fn.Request,
                   param_name: str,
                   default: bool = False) -> bool:
  """Get a boolean parameter from the request."""
  str_param = get_param(req, param_name, str(default))
  if str_param is None:
    return default
  elif isinstance(str_param, bool):
    return str_param
  else:
    return str_param.lower() == 'true'


def get_int_param(req: https_fn.Request,
                  param_name: str,
                  default: int = 0) -> int:
  """Get an integer parameter from the request.

  Falls back to the provided default if the parameter is missing or
  cannot be converted to an integer.
  """
  value = get_param(req, param_name, default)
  if value is None:
    return default
  if isinstance(value, int):
    return value
  try:
    return int(value)
  except (ValueError, TypeError):
    return default


def get_float_param(req: https_fn.Request,
                    param_name: str,
                    default: float = 0.0) -> float:
  """Get a float parameter from the request.

  Falls back to the provided default if the parameter is missing or
  cannot be converted to a float.
  """
  value = get_param(req, param_name, default)
  if value is None:
    return default
  if isinstance(value, (float, int)):
    return float(value)
  try:
    return float(value)
  except (ValueError, TypeError):
    return default
