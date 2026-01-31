"""Social post cloud functions."""

from __future__ import annotations

import datetime
import traceback
from typing import Any

from common import models, social_operations, utils
from firebase_functions import https_fn, logger
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, success_response)
from services import firestore


def run_social_post_creation_process(
    req: https_fn.Request) -> https_fn.Response:
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
    delete = get_bool_param(req, 'delete', False)

    if delete:
      if not post_id:
        raise social_operations.SocialPostRequestError(
          'post_id is required to delete a social post')
      social_operations.delete_social_post(post_id=post_id)
      return success_response(
        {
          "post_id": post_id,
          "deleted": True,
        },
        req=req,
      )

    joke_ids = get_param(req, 'joke_ids')
    type_raw = get_param(req, 'type')

    regenerate_text = get_bool_param(req, 'regenerate_text', False)
    regenerate_image = get_bool_param(req, 'regenerate_image', False)

    pinterest_title = get_param(req, 'pinterest_title')
    pinterest_description = get_param(req, 'pinterest_description')
    pinterest_alt_text = get_param(req, 'pinterest_alt_text')
    instagram_caption = get_param(req, 'instagram_caption')
    instagram_alt_text = get_param(req, 'instagram_alt_text')
    facebook_message = get_param(req, 'facebook_message')
    mark_posted_platform_raw = get_param(req, 'mark_posted_platform')
    platform_post_id = get_param(req, 'platform_post_id')
    mark_posted_platform = _parse_platform(mark_posted_platform_raw)

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
    if mark_posted_platform and not post_id:
      raise social_operations.SocialPostRequestError(
        'post_id is required to mark a social post as posted')

    operation = None
    post_type = None
    if post_id is None:
      if not isinstance(type_raw, str) or not type_raw:
        raise social_operations.SocialPostRequestError('type is required')
      try:
        # `type_raw` comes from the API and matches the enum member name
        # (e.g. "JOKE_GRID"), so prefer public name-based lookup.
        post_type = models.JokeSocialPostType[type_raw]
      except KeyError as exc:
        allowed = ", ".join(t.value for t in models.JokeSocialPostType)
        raise social_operations.SocialPostRequestError(
          f'type must be one of: {allowed}') from exc
      if not isinstance(joke_ids, list) or not joke_ids:
        raise social_operations.SocialPostRequestError(
          'joke_ids must be a non-empty list')
      operation = "CREATE"

    # Initialize social post state (existing or new).
    post, manual_updates_applied = social_operations.initialize_social_post(
      post_id=post_id,
      joke_ids=joke_ids,
      post_type=post_type,
      pinterest_title=pinterest_title,
      pinterest_description=pinterest_description,
      pinterest_alt_text=pinterest_alt_text,
      instagram_caption=instagram_caption,
      instagram_alt_text=instagram_alt_text,
      facebook_message=facebook_message,
    )
    is_new = post_id is None

    if manual_updates_applied:
      operation = "UPDATE_TEXT"

    image_bytes_by_platform: dict[models.SocialPlatform, list[bytes]] = {}
    # Generate images when creating or explicitly requested.
    if is_new or regenerate_image:
      post, image_bytes_by_platform, did_generate_images = (
        social_operations.generate_social_post_images(post))
      if did_generate_images:
        operation = "GENERATE_IMAGES"

    # Generate text from the image when needed.
    if is_new or image_bytes_by_platform or regenerate_text:
      post, did_generate_text = social_operations.generate_social_post_text(
        post,
        image_bytes_by_platform=image_bytes_by_platform,
      )
      if did_generate_text:
        operation = "GENERATE_TEXT"

    if mark_posted_platform:
      post = social_operations.mark_platform_posted(
        post,
        platform=mark_posted_platform,
        platform_post_id=platform_post_id,
        post_time=datetime.datetime.now(datetime.timezone.utc),
      )
      operation = f"MARK_POSTED_{mark_posted_platform.value.upper()}"

    # Persist updates.
    if not operation:
      return success_response(
        {
          "post_id": post.key,
          "post_data": _serialize_social_post(post),
        },
        req=req,
      )

    if saved_post := firestore.upsert_social_post(post, operation=operation):
      return success_response(
        {
          "post_id": saved_post.key,
          "post_data": _serialize_social_post(saved_post),
        },
        req=req,
      )

    return error_response('Failed to save social post', req=req, status=500)

  except social_operations.SocialPostRequestError as exc:
    return error_response(str(exc), req=req, status=exc.status)
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed to create social post: {exc}")
    logger.error(traceback.format_exc())
    return error_response(f'Failed to create social post: {exc}',
                          req=req,
                          status=500)


def _serialize_social_post(post: models.JokeSocialPost) -> dict[str, Any]:
  data = post.to_dict()
  for key, value in data.items():
    if isinstance(value, datetime.datetime):
      data[key] = value.isoformat()
  return data


def _parse_platform(
  platform_raw: str | None, ) -> models.SocialPlatform | None:
  if platform_raw is None:
    return None
  if not isinstance(platform_raw, str) or not platform_raw.strip():
    raise social_operations.SocialPostRequestError(
      "mark_posted_platform is required")
  normalized = platform_raw.strip().lower()
  try:
    return models.SocialPlatform(normalized)
  except ValueError as exc:
    allowed = ", ".join(p.value for p in models.SocialPlatform)
    raise social_operations.SocialPostRequestError(
      f"mark_posted_platform must be one of: {allowed}") from exc
