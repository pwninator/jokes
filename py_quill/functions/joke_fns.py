"""Joke cloud functions."""

import datetime
import functools
import json
import random
import traceback
import zoneinfo
from typing import Any

from agents import agents_common, constants
from agents.endpoints import all_agents
from agents.puns import pun_postprocessor_agent
from common import config, image_generation, joke_operations, models
from firebase_functions import (firestore_fn, https_fn, logger, options,
                                scheduler_fn)
from functions.function_utils import (error_response, get_bool_param,
                                      get_param, get_user_id, success_response)
from google.cloud.firestore_v1.vector import Vector
from services import cloud_storage, firebase_cloud_messaging, firestore, search


class Error(Exception):
  """Base class for exceptions in this module."""


class JokePopulationError(Error):
  """Exception raised for errors in joke population."""


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

    # Get the joke data from request body or args
    joke_data = get_param(req, 'joke_data', {})
    should_populate = get_bool_param(req, 'populate_joke', False)
    # Default to user-owned unless explicitly marked as admin-owned
    admin_owned = get_bool_param(req, 'admin_owned', False)
    punchline_text = get_param(req, 'punchline_text')
    setup_text = get_param(req, 'setup_text')
    if not joke_data and setup_text and punchline_text:
      joke_data = {
        'setup_text': setup_text,
        'punchline_text': punchline_text,
      }

    if not joke_data:
      return error_response(f'Joke data is required: {req.get_json()}')

    if not isinstance(joke_data, dict):
      return error_response(f'Joke data is not a dictionary: {joke_data}')

    if not joke_data.get('setup_text'):
      return error_response('Setup text is required')

    if not joke_data.get('punchline_text'):
      return error_response('Punchline text is required')

    user_id = get_user_id(req, allow_unauthenticated=True)
    if not user_id:
      user_id = "ANONYMOUS"

    # Set ownership: admin-owned overrides request user
    joke_data["owner_user_id"] = "ADMIN" if admin_owned else user_id

    # Initialize state to DRAFT if not provided
    if not joke_data.get("state"):
      joke_data["state"] = models.JokeState.DRAFT

    # Initialize random_id as 32-bit positive integer (0 to 2^31-1)
    joke_data["random_id"] = random.randint(0, 2**31 - 1)

    print(f"Creating joke: {joke_data}")

    # Create the joke model
    joke = models.PunnyJoke(**joke_data)

    # Save to firestore
    saved_joke = firestore.upsert_punny_joke(joke)
    if not saved_joke:
      return error_response('Failed to save joke - may already exist')

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

    return success_response({"joke_data": _to_response_joke(saved_joke)})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error creating joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to create joke: {str(e)}')


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
      now_la = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
      field_filters.append(('public_timestamp', '<=', now_la))

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
      "joke_id": result.joke.key,
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
    image_quality = get_param(req, 'image_quality', 'medium')
    images_only = get_bool_param(req, 'images_only', False)
    overwrite = get_bool_param(req, 'overwrite', False)

    if not joke_id:
      return error_response('Joke ID is required')

    # Validate image_quality parameter
    valid_qualities = ['low', 'medium', 'high']
    if image_quality not in valid_qualities:
      return error_response(
        f'Invalid image_quality: {image_quality}. Must be one of: {", ".join(valid_qualities)}'
      )

    saved_joke = _populate_joke_internal(
      user_id=user_id,
      joke_id=joke_id,
      image_quality=image_quality,
      images_only=images_only,
      overwrite=overwrite,
    )

    return success_response({"joke_data": _to_response_joke(saved_joke)})

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

    return success_response({"joke_data": _to_response_joke(saved_joke)})

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


def get_joke_embedding(
    joke: models.PunnyJoke) -> tuple[Vector, models.GenerationMetadata]:
  """Get an embedding for a joke."""
  return search.get_embedding(
    text=f"{joke.setup_text} {joke.punchline_text}",
    task_type=search.TaskType.RETRIEVAL_DOCUMENT,
    model="gemini-embedding-001",
    output_dimensionality=2048,
  )


def calculate_popularity_score(joke: models.PunnyJoke) -> int:
  """Calculate popularity score for a joke.
  
  The popularity_score is calculated as:
    `num_saves + (num_shares * 5)`
  
  Args:
    joke: The joke to calculate popularity score for.
    
  Returns:
    The calculated popularity score.
  """
  num_saves = joke.num_saves or 0
  num_shares = joke.num_shares or 0
  return num_saves + (num_shares * 5)


def _sync_joke_to_search_subcollection(
  joke: models.PunnyJoke,
  new_embedding: Vector | None,
  new_popularity_score: int,
) -> None:
  """Syncs joke data to a search subcollection document."""
  if not joke.key:
    return

  joke_id = joke.key
  search_doc_ref = firestore.db().collection("jokes").document(
    joke_id).collection("search").document("search")
  search_doc = search_doc_ref.get()
  search_data = search_doc.to_dict() if search_doc.exists else {}

  update_payload = {}

  # 1. Sync embedding
  if new_embedding:
    update_payload["text_embedding"] = new_embedding
  elif "text_embedding" not in search_data and joke.zzz_joke_text_embedding:
    update_payload["text_embedding"] = joke.zzz_joke_text_embedding

  # 2. Sync state
  if search_data.get("state") != joke.state.value:
    update_payload["state"] = joke.state.value

  # 3. Sync public_timestamp
  if search_data.get("public_timestamp") != joke.public_timestamp:
    update_payload["public_timestamp"] = joke.public_timestamp

  # 4. Sync popularity_score
  if search_data.get("popularity_score") != new_popularity_score:
    update_payload["popularity_score"] = new_popularity_score

  if update_payload:
    logger.info(
      "Syncing joke to search subcollection: %s with payload keys %s",
      joke_id,
      list(update_payload.keys()),
    )
    search_doc_ref.set(update_payload, merge=True)


@firestore_fn.on_document_written(
  document="jokes/{joke_id}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def on_joke_write(event: firestore_fn.Event[firestore_fn.Change]) -> None:
  """A cloud function that triggers on joke document changes."""
  if not event.data.after:
    logger.info("Joke document deleted: %s", event.params["joke_id"])
    return

  after_data = event.data.after.to_dict()
  after_joke = models.PunnyJoke.from_firestore_dict(after_data,
                                                    event.params["joke_id"])

  before_joke = None
  if event.data.before:
    before_data = event.data.before.to_dict()
    before_joke = models.PunnyJoke.from_firestore_dict(before_data,
                                                       event.params["joke_id"])

  should_update_embedding = False
  should_update_popularity_score = False

  # Check if embedding needs updating
  if after_joke.state == models.JokeState.DRAFT:
    # Don't bother creating embeddings for draft jokes
    should_update_embedding = False
  elif not before_joke:
    # Document created
    should_update_embedding = True
    logger.info("New joke created, calculating embedding for: %s",
                after_joke.key)
  elif (after_joke.zzz_joke_text_embedding is None
        or isinstance(after_joke.zzz_joke_text_embedding, list)):
    # Document updated without text change
    should_update_embedding = True
    logger.info("Joke missing embedding, calculating embedding for: %s",
                after_joke.key)
  elif (before_joke.setup_text != after_joke.setup_text
        or before_joke.punchline_text != after_joke.punchline_text):
    # Document updated with relevant text change
    should_update_embedding = True
    logger.info("Joke text changed, recalculating embedding for: %s",
                after_joke.key)
  else:
    logger.info(
      "Joke updated without text change, skipping embedding update for: %s",
      after_joke.key)

  # Prepare update data for Firestore
  update_data = {}
  new_embedding = None

  if should_update_embedding:
    embedding, metadata = get_joke_embedding(after_joke)
    new_embedding = embedding

    current_metadata = after_joke.generation_metadata
    if isinstance(current_metadata, dict):
      current_metadata = models.GenerationMetadata.from_dict(current_metadata)
    elif not current_metadata:
      current_metadata = models.GenerationMetadata()
    current_metadata.add_generation(metadata)

    update_data.update({
      "zzz_joke_text_embedding": embedding,
      "generation_metadata": current_metadata.as_dict,
    })

  # Check if popularity score needs updating
  expected_popularity_score = calculate_popularity_score(after_joke)
  if after_joke.popularity_score != expected_popularity_score:
    update_data["popularity_score"] = expected_popularity_score
    logger.info(
      "Joke popularity score mismatch, updating from %s to %s for: %s",
      after_joke.popularity_score, expected_popularity_score, after_joke.key)

  _sync_joke_to_search_subcollection(
    joke=after_joke,
    new_embedding=new_embedding,
    new_popularity_score=expected_popularity_score,
  )

  # Perform single Firestore update if any updates are needed
  if update_data and after_joke.key:
    firestore.update_punny_joke(after_joke.key, update_data)

    if should_update_embedding:
      logger.info("Successfully updated embedding for joke: %s",
                  after_joke.key)
    if should_update_popularity_score:
      logger.info("Successfully updated popularity score for joke: %s",
                  after_joke.key)


@firestore_fn.on_document_written(
  document="joke_categories/{category_id}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def on_joke_category_write(
    event: firestore_fn.Event[firestore_fn.Change]) -> None:
  """Trigger on writes to `joke_categories` collection.

  If the document is newly created or the `image_description` field value
  changed compared to before, log that the description changed.
  """
  # Handle deletes
  if not event.data.after:
    logger.info("Joke category deleted: %s", event.params.get("category_id"))
    return

  after_data = event.data.after.to_dict() or {}
  before_data = event.data.before.to_dict() if event.data.before else None

  if (before_data is None or (before_data or {}).get("image_description")
      != after_data.get("image_description")):
    image_description = after_data.get("image_description")
    if not image_description:
      logger.info("image_description missing; skipping image generation")
      return

    # Generate a category image at high quality without pun text or references
    generated_image = image_generation.generate_pun_image(
      pun_text=None,
      image_description=image_description,
      image_quality="high",
      reference_images=None,
    )

    if not generated_image or not generated_image.url:
      logger.info("Image generation returned no URL; skipping update")
      return

    category_id = event.params.get("category_id")
    if not category_id:
      logger.info("Missing category_id param; cannot update Firestore")
      return

    # Get the current document to check for existing all_image_urls
    doc_ref = firestore.db().collection("joke_categories").document(
      category_id)
    current_doc = doc_ref.get()

    if current_doc.exists:
      current_data = current_doc.to_dict() or {}
      all_image_urls = current_data.get("all_image_urls", [])

      # If all_image_urls doesn't exist, initialize it with the current image_url
      if not all_image_urls and current_data.get("image_url"):
        all_image_urls = [current_data["image_url"]]

      # Append the new image URL to all_image_urls
      all_image_urls.append(generated_image.url)

      # Update both fields
      doc_ref.update({
        "image_url": generated_image.url,
        "all_image_urls": all_image_urls
      })
    else:
      # Document doesn't exist, just set both fields
      doc_ref.set({
        "image_url": generated_image.url,
        "all_image_urls": [generated_image.url]
      })


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
    joke = _populate_joke_images(joke, image_quality)
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
    joke.tags = populated_pun.tags
    joke.for_kids = populated_pun.for_kids
    joke.for_adults = populated_pun.for_adults
    joke.seasonal = populated_pun.seasonal

  # Add generation metadata
  if joke.generation_metadata:
    joke.generation_metadata.add_generation(generation_metadata)
  else:
    joke.generation_metadata = generation_metadata

  return joke


def _populate_joke_images(
  joke: models.PunnyJoke,
  image_quality: str,
) -> models.PunnyJoke:
  """Populate a joke with new images using the image generation service."""

  # Check if joke has all required fields
  if not joke.setup_text:
    raise JokePopulationError('Joke is missing setup text')
  if not joke.punchline_text:
    raise JokePopulationError('Joke is missing punchline text')
  if not joke.setup_image_description:
    raise JokePopulationError('Joke is missing setup image description')
  if not joke.punchline_image_description:
    raise JokePopulationError('Joke is missing punchline image description')

  # Prepare pun data for image generation
  pun_data = [(joke.setup_text, joke.setup_image_description),
              (joke.punchline_text, joke.punchline_image_description)]

  # Generate images
  images = image_generation.generate_pun_images(pun_data, image_quality)

  # Update joke with new image URLs
  if len(images) == 2:
    joke.set_setup_image(images[0])
    joke.set_punchline_image(images[1])
  else:
    raise JokePopulationError(
      f'Image generation returned insufficient images: expected 2, got {len(images)}'
    )

  # Clear upscaled URLs since they are now out of date
  joke.setup_image_url_upscaled = None
  joke.punchline_image_url_upscaled = None

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
def send_daily_joke_http(req: https_fn.Request) -> https_fn.Response:
  """Send a daily joke notification to subscribers."""

  del req

  try:
    # Get current UTC time
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    notify_all_joke_schedules(utc_now)
  except Exception as e:
    return error_response(f'Failed to send daily joke notification: {str(e)}')

  return success_response({"message": "Daily joke notification sent"})


@scheduler_fn.on_schedule(
  schedule="0 * * * *",  # Every hour on the hour UTC-12
  timezone="Etc/GMT+12",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def send_daily_joke_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that sends daily joke notifications."""

  try:
    # Get the scheduled time from the event
    scheduled_time_utc = event.schedule_time

    notify_all_joke_schedules(scheduled_time_utc)

  except Exception as e:
    print(f"Error in daily joke task: {str(e)}")
    traceback.print_exc()


def notify_all_joke_schedules(scheduled_time_utc: datetime.datetime) -> None:
  """Iterate all schedules and send notifications for each.

  Args:
      scheduled_time_utc: The scheduled time from the scheduler event.
  """
  # Get all available joke schedules and notify for each
  schedule_ids = firestore.list_joke_schedules()
  logger.info(f"Found {len(schedule_ids)} joke schedules to process")
  for schedule_id in schedule_ids:
    try:
      logger.info(
        f"Sending daily joke notification for schedule: {schedule_id}")
      send_daily_joke_notification(scheduled_time_utc,
                                   schedule_name=schedule_id)
    except Exception as schedule_error:  # pylint: disable=broad-except
      logger.error(
        f"Failed sending jokes for schedule {schedule_id}: {schedule_error}")


def send_daily_joke_notification(
  now: datetime.datetime,
  schedule_name: str = "daily_jokes",
) -> None:
  """Send a daily joke notification to subscribers.
  
  At each hour of the day, we send two notifications: one for the current date, and one for the next date. The dates are at UTC-12. Clients subscribe to the topic for the hour they want to receive notifications, using either the "c" or "n" variety depending on whether their local timezone is one day ahead of UTC-12 or not.
  
  Args:
      now: The current datetime when this was executed (any timezone)
      schedule_name: The name of the joke schedule to use
  """
  logger.info(f"Sending daily joke notification for {schedule_name} at {now}")

  # Validate that the datetime has timezone info
  if now.tzinfo is None:
    raise ValueError(
      f"now must have timezone information, got naive datetime: {now}")

  # Convert to UTC, then calculate UTC-12 time
  now_utc = now.astimezone(datetime.timezone.utc)
  utc_minus_12 = now_utc - datetime.timedelta(hours=12)
  hour_utc_minus_12 = utc_minus_12.hour
  date_utc_minus_12 = utc_minus_12.date()

  send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12,
    notification_hour=hour_utc_minus_12,
    topic_suffix="c",  # Current date
  )

  send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12 + datetime.timedelta(days=1),
    notification_hour=hour_utc_minus_12,
    topic_suffix="n",  # Next date
  )

  # Check if it's 9am PST and send additional notification
  pst_timezone = zoneinfo.ZoneInfo("America/Los_Angeles")
  now_pst = now.astimezone(pst_timezone)

  if now_pst.hour == 9:
    logger.info(
      f"It's 9am PST, sending additional notification for {schedule_name}")
    send_single_joke_notification(
      schedule_name=schedule_name,
      joke_date=now_pst.date(),
    )


def send_single_joke_notification(
  schedule_name: str,
  joke_date: datetime.date,
  notification_hour: int | None = None,
  topic_suffix: str | None = None,
) -> None:
  """Send a joke notification for a given date.
  
  Args:
      schedule_name: The name of the joke schedule to use
      joke_date: The date to get the joke for
      notification_hour: The hour (0-23) in UTC-12 timezone (optional)
      topic_suffix: Either "c" (current date) or "n" (next date) (optional)
  """
  logger.info(f"Getting joke for {schedule_name} on {joke_date}")
  joke = firestore.get_daily_joke(schedule_name, joke_date)
  if not joke:
    logger.error(f"No joke found for {joke_date}")
    return
  logger.info(f"Joke found for {joke_date}: {joke}")

  if notification_hour is not None and topic_suffix is not None:
    topic_name = f"{schedule_name}_{notification_hour:02d}{topic_suffix}"
  else:
    topic_name = schedule_name
  logger.info(f"Sending joke notification to topic: {topic_name}")
  firebase_cloud_messaging.send_punny_joke_notification(topic_name, joke)


def _to_response_joke(joke: models.PunnyJoke) -> dict[str, Any]:
  """Convert a PunnyJoke to a dictionary for a function response."""
  joke_dict = joke.to_dict(include_key=True)
  if 'zzz_joke_text_embedding' in joke_dict:
    del joke_dict['zzz_joke_text_embedding']
  return joke_dict


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

    try:
      joke = joke_operations.upscale_joke(joke_id)
    except Exception as e:
      return error_response(f'Failed to upscale joke: {str(e)}')

    return success_response({"joke_data": _to_response_joke(joke)})
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error upscaling joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to upscale joke: {str(e)}')
