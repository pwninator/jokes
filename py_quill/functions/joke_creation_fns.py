"""Cloud functions for orchestrating joke creation workflows."""

from __future__ import annotations

import traceback

from common import image_generation, joke_operations
from firebase_functions import https_fn, logger, options
from functions.function_utils import (error_response, get_bool_param,
                                      get_param, get_user_id, success_response)
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
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

    # Joke input data
    joke_id = get_param(req, 'joke_id')
    setup_text = get_param(req, 'setup_text')
    punchline_text = get_param(req, 'punchline_text')
    setup_scene_idea = get_param(req, 'setup_scene_idea')
    punchline_scene_idea = get_param(req, 'punchline_scene_idea')
    setup_image_description = get_param(req, 'setup_image_description')
    punchline_image_description = get_param(req, 'punchline_image_description')
    admin_owned = get_bool_param(req, 'admin_owned', False)

    # Modifiers
    setup_suggestion = get_param(req, 'setup_suggestion')
    punchline_suggestion = get_param(req, 'punchline_suggestion')
    image_quality = get_param(req, 'image_quality', 'low')

    # Action flags
    regenerate_scene_ideas = get_bool_param(req, 'regenerate_scene_ideas',
                                            False)
    generate_descriptions = get_bool_param(req, 'generate_descriptions', False)
    populate_images = get_bool_param(req, 'populate_images', False)
    create_share_image = get_bool_param(req, 'create_share_image', False)

    if image_quality not in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
      return error_response(
        f'Invalid image_quality: {image_quality}. Must be one of: '
        f'{", ".join(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())}')

    # Joke initialization and patching
    try:
      joke = joke_operations.initialize_joke(
        joke_id=joke_id,
        user_id=user_id,
        admin_owned=admin_owned,
        setup_text=setup_text,
        punchline_text=punchline_text,
        setup_scene_idea=setup_scene_idea,
        punchline_scene_idea=punchline_scene_idea,
        setup_image_description=setup_image_description,
        punchline_image_description=punchline_image_description,
      )
    except joke_operations.JokeNotFoundError as exc:
      return error_response(str(exc))
    except ValueError:
      return error_response(
        'Unsupported parameter combination for joke creation',
        error_type='unsupported_parameters')

    saved_joke = None
    operation = None
    has_suggestions = bool(setup_suggestion or punchline_suggestion)

    # Generate scene ideas for new jokes or when requested
    if (not joke_id) or regenerate_scene_ideas:
      operation = "CREATE"
      joke = joke_operations.regenerate_scene_ideas(joke)

    # Apply scene idea suggestions
    if has_suggestions:
      operation = "UPDATE_SCENE_IDEAS"
      joke = joke_operations.modify_image_scene_ideas(
        joke,
        setup_suggestion,
        punchline_suggestion,
      )

    # Generate image descriptions if requested
    if generate_descriptions:
      operation = "GENERATE_IMAGE_DESCRIPTIONS"
      joke = joke_operations.generate_image_descriptions(joke)

    # Generate images if descriptions changed or requested
    if generate_descriptions or populate_images:
      operation = "GENERATE_IMAGES"
      joke = joke_operations.generate_joke_images(joke, image_quality)

    if create_share_image:
      operation = "CREATE_SHARE_IMAGE"
      joke = joke_operations.populate_share_images(joke)

    saved_joke = firestore.upsert_punny_joke(joke, operation=operation)

    if saved_joke:
      return success_response(
        {"joke_data": joke_operations.to_response_joke(saved_joke)})
    else:
      return error_response('Failed to save joke')

  except joke_operations.SafetyCheckError as exc:
    error_string = f"Safety check failed: {str(exc)}"
    logger.error(error_string)
    return error_response(error_string, error_type='safety_failed')
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error handling joke_creation_process: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type='internal_error')
