"""Joke cloud functions."""

import functools
import json
import traceback
from typing import Any

from agents import agents_common, constants
from agents.endpoints import all_agents
from agents.puns import pun_postprocessor_agent
from common import config, image_generation, joke_operations, models, utils
from common.joke_operations import JokePopulationError
from firebase_functions import https_fn, logger, options
from google.cloud.firestore import FieldFilter
from google.cloud.firestore_v1.field_path import FieldPath
from google.cloud.firestore_bundle import FirestoreBundle
from functions import auth_helpers
from functions.function_utils import (error_response, get_bool_param,
                                      get_float_param, get_int_param,
                                      get_param, get_user_id, success_response)
from services import cloud_storage, firestore, search


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  min_instances=1,
  max_instances=1,
  timeout_sec=600,
)
def create_joke(req: https_fn.Request) -> https_fn.Response:
  """Create a new punny joke document in Firestore."""
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    should_populate = get_bool_param(req, 'populate_joke', False)
    admin_owned = get_bool_param(req, 'admin_owned', False)
    punchline_text = get_param(req, 'punchline_text')
    setup_text = get_param(req, 'setup_text')

    user_id = get_user_id(req)

    try:
      saved_joke = joke_operations.create_joke(
        setup_text=setup_text,
        punchline_text=punchline_text,
        admin_owned=admin_owned,
        user_id=user_id,
      )
    except ValueError as creation_error:
      return error_response(str(creation_error))

    # Populate joke if requested
    if should_populate:
      try:
        saved_joke = _populate_joke_internal(
          user_id=user_id,
          joke_id=saved_joke.key,
          image_quality='medium',
          images_only=False,
          overwrite=True,
        )
      except Exception as populate_error:
        print(f"Error populating joke: {populate_error}")
        # Continue without populating if it fails

    return success_response(
      {"joke_data": joke_operations.to_response_joke(saved_joke)})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def get_joke_bundle(req: https_fn.Request) -> https_fn.Response:
  """Build a Firestore bundle and store it in Cloud Storage."""
  # Health check
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'POST':
    return https_fn.Response(
      json.dumps(error_response(f'Method not allowed: {req.method}')),
      status=405,
      mimetype='application/json',
    )

  if not utils.is_emulator():
    verification = auth_helpers.verify_session(req)
    if not verification or verification[1].get('role') != 'admin':
      return https_fn.Response(
        json.dumps(error_response('Unauthorized')),
        status=403,
        mimetype='application/json',
      )

  try:
    client = firestore.db()
    bundle = FirestoreBundle('data-bundle')

    # Feed documents
    feed_docs = client.collection('joke_feed')\
      .order_by(FieldPath.document_id())\
      .stream()
    for doc in feed_docs:
      bundle.add_document(doc)

    # Categories and per-category cache docs
    categories = client.collection('joke_categories')\
      .order_by(FieldPath.document_id())\
      .stream()
    for category in categories:
      bundle.add_document(category)
      cache_doc = category.reference.collection('category_jokes').document(
        'cache').get()
      if cache_doc.exists:
        bundle.add_document(cache_doc)

    # Public jokes
    public_jokes = client.collection('jokes').where(
      filter=FieldFilter('is_public', '==', True)).stream()
    for joke_doc in public_jokes:
      bundle.add_document(joke_doc)

    bundle_bytes = bundle.build()

    gcs_uri = cloud_storage.get_gcs_uri(
      'snickerdoodle_temp_files',
      'firestore_bundle',
      'txt',
    )
    cloud_storage.upload_bytes_to_gcs(
      bundle_bytes,
      gcs_uri,
      'application/octet-stream',
    )
    bundle_url = cloud_storage.get_public_url(gcs_uri)

    return https_fn.Response(
      json.dumps(success_response({'bundle_url': bundle_url})),
      status=200,
      mimetype='application/json',
    )
  except Exception as exc:  # pylint: disable=broad-except
    logger.error("Failed to build Firestore bundle: %s", str(exc))
    logger.error(traceback.format_exc())
    return https_fn.Response(
      json.dumps(error_response(f'Failed to build bundle: {exc}')),
      status=500,
      mimetype='application/json',
    )


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def joke_manual_tag(req: https_fn.Request) -> https_fn.Response:
  """Search for jokes and update their seasonal tag to Halloween."""
  # Health check
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'GET':
    return https_fn.Response(
      json.dumps({
        "error": "Only GET requests are supported",
        "success": False
      }),
      status=405,
      mimetype='application/json',
    )

  try:
    dry_run = get_bool_param(req, 'dry_run', True)
    max_jokes = get_int_param(req, 'max_jokes', 0)
    query = get_param(req, 'query')
    if not query:
      return https_fn.Response(
        json.dumps({
          "error": "query parameter is required",
          "success": False
        }),
        status=400,
        mimetype='application/json',
      )
    threshold = get_float_param(req, 'threshold', 0.3)

    html_response = _run_manual_season_tag(
      query=query,
      threshold=threshold,
      dry_run=dry_run,
      max_jokes=max_jokes,
    )
    return https_fn.Response(html_response, status=200, mimetype='text/html')

  except Exception as e:  # pylint: disable=broad-except
    logger.error(f"Manual seasonal tag failed: {e}")
    logger.error(traceback.format_exc())
    return https_fn.Response(
      json.dumps({
        "success": False,
        "error": str(e),
        "message": "Failed to run manual season tag"
      }),
      status=500,
      mimetype='application/json',
    )


def _run_manual_season_tag(
  query: str,
  threshold: float,
  dry_run: bool,
  max_jokes: int,
) -> str:
  """
    Sets the 'seasonal' field to 'Halloween' for jokes matching a search query.

    Args:
        query: The search query for jokes.
        threshold: The search distance threshold.
        dry_run: If True, only log the changes that would be made.
        max_jokes: The maximum number of jokes to modify. If 0, all jokes will be processed.

    Returns:
        An HTML page listing the jokes that were updated.
    """
  logger.info("Starting manual season tag operation...")

  search_results = search.search_jokes(
    query=query,
    label="manual_season_tag",
    limit=1000,  # A reasonable upper limit on search results to check
    field_filters=[],
    distance_threshold=threshold,
  )

  updated_jokes = []
  skipped_jokes = []
  updated_count = 0

  for result in search_results:
    if max_jokes and updated_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    joke_id = result.joke_id
    if not joke_id:
      continue

    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      logger.warn(f"Could not retrieve joke with id: {joke_id}")
      continue

    if joke.seasonal != "Halloween":
      updated_jokes.append({
        "id": joke_id,
        "setup": joke.setup_text,
        "punchline": joke.punchline_text,
        "old_seasonal": joke.seasonal,
        "distance": result.vector_distance,
      })
      if not dry_run:
        firestore.update_punny_joke(joke_id, {"seasonal": "Halloween"})
      updated_count += 1
    else:
      skipped_jokes.append({
        "id": joke_id,
        "setup": joke.setup_text,
        "punchline": joke.punchline_text,
      })

  # Generate HTML response
  html = "<html><body>"
  html += "<h1>Manual Season Tag Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"
  if updated_jokes:
    html += "<ul>"
    for joke in updated_jokes:
      html += f"<li>{round(joke['distance'], 4)}: <b>{joke['id']}</b>: {joke['setup']} / {joke['punchline']} (Old seasonal: {joke['old_seasonal']})</li>"
    html += "</ul>"
  else:
    html += "<p>No jokes were updated.</p>"

  html += f"<h2>Skipped Jokes (already Halloween) ({len(skipped_jokes)})</h2>"
  if skipped_jokes:
    html += "<ul>"
    for joke in skipped_jokes:
      html += f"<li><b>{joke['id']}</b>: {joke['setup']} / {joke['punchline']}</li>"
    html += "</ul>"
  else:
    html += "<p>No jokes were skipped.</p>"

  html += "</body></html>"

  return html


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  min_instances=1,
  timeout_sec=30,
)
def search_jokes(req: https_fn.Request) -> https_fn.Response:
  """Search for jokes."""

  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    # Get the search query and max results from request body or args
    search_query = get_param(req, 'search_query')
    if not search_query:
      return error_response('Search query is required')

    label = get_param(req, 'label', "unknown")
    max_results = get_param(req, 'max_results', 10)
    if not isinstance(max_results, int):
      try:
        max_results = int(max_results)
      except (ValueError, TypeError):
        return error_response(f'Max results must be an integer: {max_results}')

    match_mode = get_param(req, 'match_mode', "TIGHT")
    if match_mode == "TIGHT":
      distance_threshold = config.JOKE_SEARCH_TIGHT_THRESHOLD
    elif match_mode == "LOOSE":
      distance_threshold = config.JOKE_SEARCH_LOOSE_THRESHOLD
    else:
      return error_response(f'Invalid match_mode: {match_mode}')

    # Filter: public_only (default True) => public_timestamp <= now in LA
    public_only = get_bool_param(req, 'public_only', True)
    field_filters = []
    if public_only:
      field_filters.extend([
        ("state", "in",
         [models.JokeState.PUBLISHED.value, models.JokeState.DAILY.value]),
        ("is_public", "==", True),
      ])

    # Search for jokes
    search_results = search.search_jokes(
      query=search_query,
      label=label,
      limit=max_results,
      field_filters=field_filters,
      distance_threshold=distance_threshold,
    )

    # Return jokes with id and vector distance
    jokes = [{
      "joke_id": result.joke_id,
      "vector_distance": result.vector_distance
    } for result in search_results]
    return success_response({"jokes": jokes})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error searching jokes: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to search jokes: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def populate_joke(req: https_fn.Request) -> https_fn.Response:
  """Populate a joke with images and enhanced data using the joke populator agent."""

  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req, allow_unauthenticated=True)
    if not user_id:
      user_id = "ANONYMOUS"

    # Get the joke ID, images_only, and image_quality params from request body or args
    joke_id = get_param(req, 'joke_id')
    image_quality = get_param(req, 'image_quality', 'low')
    images_only = get_bool_param(req, 'images_only', False)
    overwrite = get_bool_param(req, 'overwrite', False)

    if not joke_id:
      return error_response('Joke ID is required')

    # Validate image_quality parameter
    if image_quality not in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
      return error_response(
        f'Invalid image_quality: {image_quality}. Must be one of: {", ".join(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())}'
      )

    logger.info(
      f"CLOUD_FUNCTION populate_joke: {joke_id} with params: joke_id={joke_id}, image_quality={image_quality}, images_only={images_only}, overwrite={overwrite}"
    )

    saved_joke = _populate_joke_internal(
      user_id=user_id,
      joke_id=joke_id,
      image_quality=image_quality,
      images_only=images_only,
      overwrite=overwrite,
    )

    return success_response(
      {"joke_data": joke_operations.to_response_joke(saved_joke)})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error populating joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to populate joke: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def modify_joke_image(req: https_fn.Request) -> https_fn.Response:
  """Modify a joke's images using instructions."""

  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    # Get the joke ID and instructions from request body or args
    joke_id = get_param(req, 'joke_id')
    setup_instruction = get_param(req, 'setup_instruction')
    punchline_instruction = get_param(req, 'punchline_instruction')

    if not joke_id:
      return error_response('Joke ID is required')

    if not setup_instruction and not punchline_instruction:
      return error_response(
        'At least one instruction (setup_instruction or punchline_instruction) is required'
      )

    # Load the joke from firestore
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      return error_response(f'Joke not found: {joke_id}')

    if setup_instruction:
      error = _modify_and_set_image(
        image_url=joke.setup_image_url,
        instruction=setup_instruction,
        image_setter=functools.partial(joke.set_setup_image,
                                       update_text=False),
        error_message='Joke has no setup image to modify')
      if error:
        return error_response(error)

    if punchline_instruction:
      error = _modify_and_set_image(
        image_url=joke.punchline_image_url,
        instruction=punchline_instruction,
        image_setter=functools.partial(joke.set_punchline_image,
                                       update_text=False),
        error_message='Joke has no punchline image to modify')
      if error:
        return error_response(error)

    # Save the updated joke back to firestore
    saved_joke = firestore.upsert_punny_joke(joke)
    if not saved_joke:
      return error_response('Failed to save modified joke')

    return success_response(
      {"joke_data": joke_operations.to_response_joke(saved_joke)})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error modifying joke image: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to modify joke image: {str(e)}')


def _modify_and_set_image(
    image_url: str | None, instruction: str, image_setter: callable,
    error_message: str) -> str | None:  # Return error string or None
  if not image_url:
    return error_message

  image_to_modify = models.Image(
    url=image_url,
    gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(image_url),
  )

  new_image = image_generation.modify_image(
    image_to_modify,
    instruction,
  )

  image_setter(new_image)
  return None


def _populate_joke_internal(
  user_id: str,
  joke_id: str,
  image_quality: str,
  images_only: bool,
  overwrite: bool,
) -> models.PunnyJoke:
  """Populate a joke with images and enhanced data using the joke populator agent."""
  print(f"Populating joke: {joke_id}")

  if not joke_id or not user_id:
    raise JokePopulationError('Joke ID and user ID are required')

  # Load the joke from firestore
  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise JokePopulationError(f'Joke not found: {joke_id}')

  if images_only:
    joke = joke_operations.generate_joke_images(joke, image_quality)
  else:
    joke = _populate_entire_joke_internal(joke, user_id, overwrite)

  if joke.state == models.JokeState.DRAFT:
    joke.state = models.JokeState.UNREVIEWED

  # Save the updated joke back to firestore
  saved_joke = firestore.upsert_punny_joke(joke)
  if not saved_joke:
    raise JokePopulationError('Failed to save populated joke')

  return saved_joke


def _populate_entire_joke_internal(
  joke: models.PunnyJoke,
  user_id: str,
  overwrite: bool,
) -> models.PunnyJoke:
  """Populate a joke with images and enhanced data using the joke populator agent."""
  if not joke.setup_text or not joke.punchline_text:
    raise JokePopulationError('Joke is missing setup or punchline text')

  # Convert joke to pun format for the agent
  joke_lines = [joke.setup_text, joke.punchline_text]

  generation_metadata = models.GenerationMetadata()

  populator_agent_fields = {
    "pun_word",
    "punned_word",
    "setup_image_description",
    "punchline_image_description",
    "setup_image_prompt",
    "punchline_image_prompt",
    "setup_image_url",
    "punchline_image_url",
  }

  if overwrite or joke.unpopulated_fields.intersection(populator_agent_fields):
    # Set up inputs for the populator agent
    inputs = {
      constants.STATE_USER_INPUT: "Create funny pun-based joke images",
      constants.STATE_ITEMS_NEW: [str(joke_lines)],
    }

    # Run the populator agent
    joke_populator_agent = all_agents.get_joke_populator_agent_adk_app()
    _, final_state, agent_generation_metadata = agents_common.run_agent(
      adk_app=joke_populator_agent,
      inputs=inputs,
      user_id=user_id,
    )
    generation_metadata.add_generation(agent_generation_metadata)

    # Extract the populated pun data
    finalized_puns = final_state.get(constants.STATE_FINALIZED_PUNS, [])
    if not finalized_puns:
      raise JokePopulationError(
        'Failed to populate joke - no results from agent')

    # Get the first (and should be only) populated pun
    populated_pun_data = finalized_puns[0]
    populated_pun = pun_postprocessor_agent.Pun.model_validate(
      populated_pun_data)

    # Update the joke with the populated data
    if len(populated_pun.pun_lines) >= 2:
      setup_line = populated_pun.pun_lines[0]
      punchline_line = populated_pun.pun_lines[1]

      joke.set_setup_image(
        models.Image(
          url=setup_line.image_url,
          original_prompt=setup_line.image_description,
          final_prompt=setup_line.image_prompt,
        ))
      joke.set_punchline_image(
        models.Image(
          url=punchline_line.image_url,
          original_prompt=punchline_line.image_description,
          final_prompt=punchline_line.image_prompt,
        ))
    else:
      raise JokePopulationError(
        f'Populator agent returned insufficient pun lines: expected 2, got {len(populated_pun.pun_lines)}'
      )

    # Update metadata from the pun
    if not joke.pun_word and populated_pun.pun_word:
      joke.pun_word = populated_pun.pun_word
    if not joke.punned_word and populated_pun.punned_word:
      joke.punned_word = populated_pun.punned_word
    joke.pun_theme = populated_pun.pun_theme
    joke.phrase_topic = populated_pun.phrase_topic
    joke.tags = [t.lower() for t in populated_pun.tags]
    joke.for_kids = populated_pun.for_kids
    joke.for_adults = populated_pun.for_adults
    joke.seasonal = populated_pun.seasonal

  # Add generation metadata
  if joke.generation_metadata:
    joke.generation_metadata.add_generation(generation_metadata)
  else:
    joke.generation_metadata = generation_metadata

  return joke


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def critique_jokes(req: https_fn.Request) -> https_fn.Response:
  """Critique a list of jokes using the joke critic agent."""

  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req, allow_unauthenticated=True)
    if not user_id:
      user_id = "ANONYMOUS"

    # Get the instructions and jokes from request body or args
    if req.is_json:
      # JSON request
      json_data = req.get_json()
      data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
      instructions = data.get('instructions')
      jokes = data.get('jokes')
    else:
      # Non-JSON request, get from args
      instructions = req.args.get('instructions')
      jokes_str = req.args.get('jokes')

      # Parse jokes from JSON string if provided
      if jokes_str:
        try:
          jokes = json.loads(jokes_str)
        except json.JSONDecodeError as e:
          return error_response(f'Invalid JSON format for jokes: {str(e)}')
      else:
        jokes = []

    if not instructions:
      return error_response('Instructions are required')

    print(f"Critiquing {len(jokes)} jokes with instructions: {instructions}")

    # Set up inputs for the critic agent
    inputs = {
      constants.STATE_USER_INPUT: instructions,
      constants.STATE_ITEMS_NEW: jokes,
    }

    # Run the critic agent
    joke_critic_agent: Any = all_agents.get_joke_critic_agent_adk_app()
    _, final_state, _ = agents_common.run_agent(
      adk_app=joke_critic_agent,
      inputs=inputs,
      user_id=user_id,
    )

    # Extract the critique data
    critique_data = final_state.get(constants.STATE_CRITIQUE, {})
    if not critique_data:
      return error_response('Failed to critique jokes - no results from agent')

    return success_response({"critique_data": critique_data})

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error critiquing jokes: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to critique jokes: {str(e)}')


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def upscale_joke(req: https_fn.Request) -> https_fn.Response:
  """Upscale a joke's images."""
  try:
    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    joke_id = get_param(req, 'joke_id')
    if not joke_id:
      return error_response('joke_id is required')

    mime_type = get_param(req, 'mime_type', 'image/png')
    compression_quality = get_int_param(req, 'compression_quality', 0)
    if not compression_quality:
      compression_quality = None

    try:
      joke = joke_operations.upscale_joke(
        joke_id,
        mime_type=mime_type,
        compression_quality=compression_quality,
      )
    except Exception as e:
      return error_response(f'Failed to upscale joke: {str(e)}')

    return success_response(
      {"joke_data": joke_operations.to_response_joke(joke)})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error upscaling joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to upscale joke: {str(e)}')
