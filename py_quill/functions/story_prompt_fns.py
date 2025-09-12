"""Story prompt cloud functions."""

from common import models
from firebase_functions import https_fn, options
from functions.prompts import story_prompt
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=20,
  # min_instances=1,
)
def get_random_prompt(req: https_fn.Request) -> https_fn.Response:
  """Returns a random story prompt to help inspire story creation.

  This endpoint generates creative story prompts that can be used as inspiration
  for new stories. The prompts are designed to be engaging and spark imagination
  while being appropriate for children's stories.

  Args:
    req: The request object containing:
      - main_character_ids: List of main character IDs
      - side_character_ids: List of side character IDs
      - reading_level: Integer representing the reading level (0=Pre-K, 1=K, 2=1st, etc.)
  """
  # Ignore health check requests
  if '/__/health' in req.path:
    return {"status": "healthy"}

  if req.method not in ['GET', 'POST']:
    return error_response(f'Method not allowed: {req.method}')

  # try:
  # Get character IDs from request
  if req.is_json:
    json_data = req.get_json()
    # Unwrap the data field from httpsCallable
    data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
    main_character_ids = data.get('main_character_ids', [])
    side_character_ids = data.get('side_character_ids', [])
    reading_level = data.get('reading_level', models.ReadingLevel.THIRD.value)
  else:
    # Handle GET request with query parameters
    main_character_ids = req.args.getlist('main_character_ids')
    side_character_ids = req.args.getlist('side_character_ids')
    reading_level = int(
      req.args.get('reading_level', models.ReadingLevel.THIRD.value))

  # Load all characters in a single batch
  all_character_ids = main_character_ids + side_character_ids
  characters_by_id = {
    c.key: c
    for c in firestore.get_characters(all_character_ids)
  }

  # Split into main and side characters while preserving order
  main_characters = [
    characters_by_id[char_id] for char_id in main_character_ids
    if char_id in characters_by_id
  ]
  side_characters = [
    characters_by_id[char_id] for char_id in side_character_ids
    if char_id in characters_by_id
  ]

  result = story_prompt.get_random_prompt(main_characters=main_characters,
                                          side_characters=side_characters,
                                          reading_level=reading_level)
  if result:
    return success_response(result)
  else:
    return error_response('LLM did not return a valid response')
  # except Exception as e:  # pylint: disable=broad-except
  #   return error_response(f'Failed to generate prompt: {str(e)}')


def success_response(prompt: str) -> https_fn.Response:
  """Return a success response."""
  print(f"Success response: {prompt}")
  return {"data": {"story_prompt": prompt}}


def error_response(message: str) -> https_fn.Response:
  """Return an error response."""
  print(f"Error response: {message}")
  return {"data": {"error": message}}
