"""Social post cloud functions."""

from __future__ import annotations

import traceback
from typing import Any

from common import models, social_operations, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, success_response)
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def social_post_creation_process(req: https_fn.Request) -> https_fn.Response:
  """Handle social post creation and updates."""
  if response := handle_cors_preflight(req):
    return response

  if response := handle_health_check(req):
    return response

  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  if not utils.is_emulator():
    try:
      get_user_id(req, require_admin=True)
    except AuthError:
      return error_response('Unauthorized', req=req, status=403)

  try:
    post_id = get_param(req, 'post_id')
    joke_ids = get_param(req, 'joke_ids')
    type_raw = get_param(req, 'type')

    regenerate_text = get_bool_param(req, 'regenerate_text', False)
    regenerate_image = get_bool_param(req, 'regenerate_image', False)

    pinterest_title = get_param(req, 'pinterest_title')
    pinterest_description = get_param(req, 'pinterest_description')
    pinterest_alt_text = get_param(req, 'pinterest_alt_text')

    if post_id and (joke_ids is not None or type_raw is not None):
      raise social_operations.SocialPostRequestError(
        'post_id cannot be combined with joke_ids or type')
    if not post_id and joke_ids is None and type_raw is None:
      raise social_operations.SocialPostRequestError(
        'joke_ids and type are required to create a social post')
    if regenerate_image and not regenerate_text:
      raise social_operations.SocialPostRequestError(
        'regenerate_image requires regenerate_text',
        status=400,
      )

    operation = None
    post_type = None
    joke_id_list = None
    if post_id is None:
      if not isinstance(type_raw, str) or not type_raw:
        raise social_operations.SocialPostRequestError('type is required')
      try:
        post_type = models.JokeSocialPostType(type_raw)
      except ValueError as exc:
        allowed = ", ".join(t.value for t in models.JokeSocialPostType)
        raise social_operations.SocialPostRequestError(
          f'type must be one of: {allowed}') from exc
      if not isinstance(joke_ids, list) or not joke_ids:
        raise social_operations.SocialPostRequestError(
          'joke_ids must be a non-empty list')
      joke_id_list = joke_ids
      operation = "CREATE"

    # Initialize social post state (existing or new).
    post = social_operations.initialize_social_post(
      post_id=post_id,
      joke_ids=joke_id_list,
      post_type=post_type,
      pinterest_title=pinterest_title,
      pinterest_description=pinterest_description,
      pinterest_alt_text=pinterest_alt_text,
    )
    is_new = post_id is None

    if _any_not_none(
        pinterest_title,
        pinterest_description,
        pinterest_alt_text,
    ):
      operation = "UPDATE_TEXT"

    # Generate Pinterest image when creating or explicitly requested.
    pin_image_bytes: bytes | None = None
    if is_new or regenerate_image:
      operation = "GENERATE_PIN_IMAGE"
      joke_id_list = [j.key for j in post.jokes if j.key]
      post, pin_image_bytes = social_operations.create_pinterest_pin_assets(
        post)

    # Generate Pinterest text from the image when needed.
    if is_new or pin_image_bytes or regenerate_text:
      operation = "GENERATE_PIN_TEXT"
      post = social_operations.generate_pinterest_post_text(
        post, pin_image_bytes)

    # Persist updates.
    if not operation:
      return error_response("No operation to perform", req=req, status=400)

    if saved_post := firestore.upsert_social_post(post, operation=operation):
      return success_response(
        {
          "post_id": saved_post.key,
          "post_data": saved_post.to_dict(),
        },
        req=req,
      )
    else:
      return error_response('Failed to save social post', req=req, status=500)

  except social_operations.SocialPostRequestError as exc:
    return error_response(str(exc), req=req, status=exc.status)
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed to create social post: {exc}")
    logger.error(traceback.format_exc())
    return error_response(f'Failed to create social post: {exc}',
                          req=req,
                          status=500)


def _any_not_none(*vals: Any) -> bool:
  return any(val is not None for val in vals)
