"""Social post cloud functions."""

from __future__ import annotations

import traceback
from io import BytesIO

from common import image_operations, models, social_operations, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (AuthError, error_response, get_param,
                                      handle_cors_preflight,
                                      handle_health_check, success_response,
                                      get_user_id)
from services import cloud_storage, firestore

_MAX_SOCIAL_POST_JOKES = 5


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def create_social_post(req: https_fn.Request) -> https_fn.Response:
  """Create a social post with generated title/description and pin image."""
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
    joke_ids = get_param(req, 'joke_ids', default=None)
    type_raw = get_param(req, 'type', default=None)

    if not isinstance(joke_ids, list) or not joke_ids:
      return error_response('joke_ids must be a non-empty list',
                            req=req,
                            status=400)
    if len(joke_ids) > _MAX_SOCIAL_POST_JOKES:
      return error_response('joke_ids must have at most 5 items',
                            req=req,
                            status=400)
    if not isinstance(type_raw, str) or not type_raw:
      return error_response('type is required', req=req, status=400)

    try:
      post_type = models.JokeSocialPostType(type_raw)
    except ValueError:
      allowed = ", ".join(t.value for t in models.JokeSocialPostType)
      return error_response(f'type must be one of: {allowed}',
                            req=req,
                            status=400)

    jokes = firestore.get_punny_jokes(joke_ids)
    jokes_by_id = {joke.key: joke for joke in jokes if joke.key}
    ordered_jokes = [jokes_by_id.get(joke_id) for joke_id in joke_ids]
    if any(joke is None for joke in ordered_jokes):
      missing = [
        jid for jid, joke in zip(joke_ids, ordered_jokes) if joke is None
      ]
      return error_response(f'Jokes not found: {missing}', req=req, status=400)

    title, description = social_operations.generate_social_post_text(
      ordered_jokes, post_type)

    pin_image = image_operations.create_pinterest_pin_image(
      joke_ids,
      block_last_panel=post_type == models.JokeSocialPostType.JOKE_GRID_TEASER,
    )

    buffer = BytesIO()
    pin_image.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()

    gcs_uri = cloud_storage.get_image_gcs_uri('social_pinterest', 'png')
    cloud_storage.upload_bytes_to_gcs(
      image_bytes,
      gcs_uri,
      'image/png',
    )
    pin_url = cloud_storage.get_public_cdn_url(gcs_uri)

    post = models.JokeSocialPost(
      type=post_type,
      title=title,
      description=description,
      jokes=[joke.get_minimal_joke_data() for joke in ordered_jokes],
      pinterest_image_url=pin_url,
    )
    post = firestore.create_joke_social_post(post)

    return success_response(
      {
        'post_id': post.key,
        'title': title,
        'description': description,
        'pinterest_image_url': pin_url,
        'type': post_type.value,
      },
      req=req,
    )
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed to create social post: {exc}")
    logger.error(traceback.format_exc())
    return error_response(f'Failed to create social post: {exc}',
                          req=req,
                          status=500)
