"""Cloud functions for orchestrating joke creation workflows."""

from __future__ import annotations

import traceback

from common import image_generation, joke_operations
from firebase_functions import https_fn, logger, options
from functions.function_utils import (error_response, get_bool_param,
                                      get_param, get_user_id, success_response)
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  min_instances=1,
  timeout_sec=600,
)
def joke_creation_process(req: https_fn.Request) -> https_fn.Response:
  """Handle joke creation scenarios for text entry, suggestions, and images."""
  try:
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req, allow_unauthenticated=False)

    joke_id = get_param(req, 'joke_id')
    setup_text = get_param(req, 'setup_text')
    punchline_text = get_param(req, 'punchline_text')
    admin_owned = get_bool_param(req, 'admin_owned', False)
    setup_suggestion = get_param(req, 'setup_suggestion')
    punchline_suggestion = get_param(req, 'punchline_suggestion')
    populate_images = get_bool_param(req, 'populate_images', False)

    if joke_id:
      joke = firestore.get_punny_joke(joke_id)
      if not joke:
        return error_response(f'Joke not found: {joke_id}')
    else:
      joke = None

    saved_joke = None
    if not joke and setup_text and punchline_text:
      # Scenario 1: create a new joke from setup/punchline strings.
      saved_joke = joke_operations.create_joke(
        joke_data=None,
        setup_text=setup_text,
        punchline_text=punchline_text,
        admin_owned=admin_owned,
        user_id=user_id,
      )
      if not saved_joke:
        return error_response('Failed to save joke after creating')

    elif joke and (setup_suggestion or punchline_suggestion):
      # Scenario 2: apply image description suggestions for an existing joke.
      saved_joke = joke_operations.modify_image_descriptions(
        joke,
        setup_suggestion,
        punchline_suggestion,
      )
      if not saved_joke:
        return error_response('Failed to save joke after applying suggestions')

    elif joke and populate_images:
      # Scenario 3: regenerate joke images.
      image_quality = get_param(req, 'image_quality', 'low')
      if image_quality not in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
        return error_response(
          f'Invalid image_quality: {image_quality}. Must be one of: '
          f'{", ".join(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())}')

      updated_joke = joke_operations.generate_joke_images(
        joke,
        image_quality,
      )

      saved_joke = firestore.upsert_punny_joke(updated_joke)
      if not saved_joke:
        return error_response('Failed to save joke after generating images')

    else:
      return error_response(
        'Unsupported parameter combination for joke_creation_process')

    if saved_joke:
      return success_response(
        {"joke_data": joke_operations.to_response_joke(saved_joke)})
    else:
      return error_response('Failed to save joke')

  except Exception as exc:  # pylint: disable=broad-except
    error_string = f"Error handling joke_creation_process: {str(exc)}\n{traceback.format_exc()}"
    logger.error(error_string)
    return error_response(error_string)
