"""Admin cloud functions."""

import traceback

from firebase_admin import auth
from firebase_functions import https_fn, options
from functions.function_utils import (AuthError, error_response, get_user_id,
                                      success_response)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=30,
)
def set_user_role(req: https_fn.Request) -> https_fn.Response:
  """Set a custom role claim for a user."""

  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    # Get the target user_id and role from request body or args
    if req.is_json:
      # JSON request
      json_data = req.get_json()
      data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
      target_user_id = data.get('user_id')
      role = data.get('role')
    else:
      # Non-JSON request, get from args
      target_user_id = req.args.get('user_id')
      role = req.args.get('role')

    if not target_user_id:
      return error_response('user_id parameter is required')

    if not role:
      return error_response('role parameter is required')

    # Get the requesting user ID for authentication
    try:
      requesting_user_id = get_user_id(req, allow_unauthenticated=True)
    except AuthError:
      return error_response('Authentication required', status=401)
    # if not requesting_user_id:
    #   return error_response('Authentication required')

    # Verify the requesting user has admin privileges
    # try:
    #   requesting_user = auth.get_user(requesting_user_id)
    #   custom_claims = requesting_user.custom_claims or {}
    #   if not custom_claims.get('admin'):
    #     return error_response('Admin privileges required')
    # except Exception as e:
    #   return error_response(f'Failed to verify admin privileges: {str(e)}')

    print(
      f"Admin {requesting_user_id} setting role '{role}' for user {target_user_id}"
    )

    # Set the custom role claim for the target user
    auth.set_custom_user_claims(target_user_id, {'role': role})

    return success_response({
      "user_id":
      target_user_id,
      "role":
      role,
      "message":
      f"Successfully set role '{role}' for user {target_user_id}"
    })

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error setting user role: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to set user role: {str(e)}')
