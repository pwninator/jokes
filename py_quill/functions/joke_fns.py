"""Joke cloud functions."""

import functools
import json
import traceback
from typing import Any

from agents import agents_common, constants
from agents.endpoints import all_agents
from common import config, image_generation, joke_operations, models, utils
from firebase_functions import https_fn, logger, options
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_float_param,
                                      get_int_param, get_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, html_response,
                                      success_response)
from google.cloud.firestore import FieldFilter
from google.cloud.firestore_bundle import FirestoreBundle
from google.cloud.firestore_v1.field_path import FieldPath
from services import cloud_storage, firestore, search

BUNDLE_SECRET_HEADER = "X-Bundle-Secret"


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def get_joke_bundle(req: https_fn.Request) -> https_fn.Response:
  """Build a Firestore bundle and store it in Cloud Storage."""
  if response := handle_cors_preflight(req):
    return response

  if response := handle_health_check(req):
    return response

  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  bundle_secret = req.headers.get(BUNDLE_SECRET_HEADER)
  if bundle_secret:
    try:
      expected_secret = config.get_joke_bundle_secret()
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(f"Failed to load joke bundle secret: {str(exc)}")
      logger.error(traceback.format_exc())
      return error_response('Failed to verify bundle secret',
                            req=req,
                            status=500)
    if bundle_secret != expected_secret:
      return error_response('Unauthorized', req=req, status=403)
  elif not utils.is_emulator():
    try:
      get_user_id(req, require_admin=True)
    except AuthError:
      return error_response('Unauthorized', req=req, status=403)

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

    return success_response({'bundle_url': bundle_url}, req=req)
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed to build Firestore bundle: {str(exc)}")
    logger.error(traceback.format_exc())
    return error_response(f'Failed to build bundle: {exc}',
                          req=req,
                          status=500)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def joke_manual_tag(req: https_fn.Request) -> https_fn.Response:
  """Search for jokes and update their seasonal tag."""
  if response := handle_cors_preflight(req):
    return response

  if response := handle_health_check(req):
    return response

  if req.method != 'GET':
    return error_response("Only GET requests are supported",
                          req=req,
                          status=405)

  try:
    dry_run = get_bool_param(req, 'dry_run', True)
    max_jokes = get_int_param(req, 'max_jokes', 50)
    query = get_param(req, 'query')
    if not query:
      return error_response("query parameter is required", req=req, status=400)
    seasonal = get_param(req, 'seasonal')
    if not seasonal or not isinstance(seasonal, str) or not seasonal.strip():
      return error_response("seasonal parameter is required",
                            req=req,
                            status=400)
    seasonal = seasonal.strip()
    threshold = get_float_param(req, 'threshold', 0.4)

    html_content = _run_manual_season_tag(
      query=query,
      seasonal=seasonal,
      threshold=threshold,
      dry_run=dry_run,
      max_jokes=max_jokes,
    )
    return html_response(html_content, req=req)

  except Exception as e:  # pylint: disable=broad-except
    logger.error(f"Manual seasonal tag failed: {e}")
    logger.error(traceback.format_exc())
    return error_response(f'Failed to run manual season tag: {str(e)}',
                          req=req,
                          status=500)


def _run_manual_season_tag(
  query: str,
  seasonal: str,
  threshold: float,
  dry_run: bool,
  max_jokes: int,
) -> str:
  """
    Sets the 'seasonal' field for jokes matching a search query.

    Args:
        query: The search query for jokes.
        seasonal: The seasonal value to set on matching jokes.
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

  def _img_cell(image_url: str | None) -> str:
    """Render a 100x100 image cell, scaling via CDN width param when possible."""
    if not image_url:
      return ""
    formatted = utils.format_image_url(image_url, width=100)
    # Force a compact thumbnail size in the HTML output regardless of aspect ratio.
    return (f'<img src="{formatted}" width="100" height="100" loading="lazy" '
            f'style="object-fit: cover;" alt="joke image" />')

  def _render_table(rows: list[dict[str, object]], *,
                    include_old_seasonal: bool):
    """Render a simple HTML table for result rows."""
    if not rows:
      return ""

    header_cols = [
      ("distance", "Distance"),
      ("id", "Joke ID"),
      ("setup_image_html", "Setup Image"),
      ("punchline_image_html", "Punchline Image"),
      ("setup", "Setup"),
      ("punchline", "Punchline"),
    ]
    if include_old_seasonal:
      header_cols.append(("old_seasonal", "Old Seasonal"))

    html_table = '<table border="1" cellpadding="6" cellspacing="0">'
    html_table += "<thead><tr>"
    for _, header in header_cols:
      html_table += f"<th>{header}</th>"
    html_table += "</tr></thead><tbody>"

    for row in rows:
      html_table += "<tr>"
      for key, _ in header_cols:
        value = row.get(key, "")
        if value is None:
          value = ""
        html_table += f"<td>{value}</td>"
      html_table += "</tr>"

    html_table += "</tbody></table>"
    return html_table

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

    if joke.seasonal != seasonal:
      updated_jokes.append({
        "id":
        joke_id,
        "setup_image_html":
        _img_cell(getattr(joke, "setup_image_url", None)),
        "punchline_image_html":
        _img_cell(getattr(joke, "punchline_image_url", None)),
        "setup":
        joke.setup_text,
        "punchline":
        joke.punchline_text,
        "old_seasonal":
        joke.seasonal,
        "distance":
        result.vector_distance,
      })
      if not dry_run:
        firestore.update_punny_joke(joke_id, {"seasonal": seasonal})
      updated_count += 1
    else:
      skipped_jokes.append({
        "id":
        joke_id,
        "setup_image_html":
        _img_cell(getattr(joke, "setup_image_url", None)),
        "punchline_image_html":
        _img_cell(getattr(joke, "punchline_image_url", None)),
        "setup":
        joke.setup_text,
        "punchline":
        joke.punchline_text,
      })

  # Generate HTML response
  html = "<html><body>"
  html += "<h1>Manual Season Tag Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"
  if updated_jokes:
    # Round distances for display.
    for joke in updated_jokes:
      if "distance" in joke and joke["distance"] is not None:
        joke["distance"] = round(float(joke["distance"]), 4)
    html += _render_table(updated_jokes, include_old_seasonal=True)
  else:
    html += "<p>No jokes were updated.</p>"

  html += f"<h2>Skipped Jokes (already {seasonal}) ({len(skipped_jokes)})</h2>"
  if skipped_jokes:
    html += _render_table(skipped_jokes, include_old_seasonal=False)
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
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    # Get the search query and max results from request body or args
    search_query = get_param(req, 'search_query')
    category_id = get_param(req, 'category')

    if bool(search_query) == bool(category_id):
      return error_response(
        'Exactly one of search_query or category is required',
        req=req,
        status=400)

    return_jokes = get_bool_param(req, 'return_jokes', False)
    exclude_in_book = get_bool_param(req, 'exclude_in_book', False)
    jokes = []

    if category_id:
      category = firestore.get_joke_category(category_id)
      if not category:
        return error_response(f'Category not found: {category_id}',
                              req=req,
                              status=404)

      # If filtering by book, we need the full joke documents to check book_id
      if exclude_in_book:
        joke_ids = [joke.key for joke in category.jokes if joke.key]
        full_jokes = firestore.get_punny_jokes(joke_ids)
        # Re-map full jokes by ID for easy lookup
        full_jokes_map = {j.key: j for j in full_jokes if j.key}
      else:
        full_jokes_map = {}

      for joke in category.jokes:
        if exclude_in_book:
          # Check the full joke document for book_id
          full_joke = full_jokes_map.get(joke.key)
          if full_joke and full_joke.book_id:
            continue
          # If full joke is missing but it's in cache, we assume it's valid/safe or just include it.
          # If full_joke is None, it might have been deleted.

        item = {
          "joke_id": joke.key,
          "vector_distance": 0.0,
        }
        if return_jokes:
          item["setup_text"] = joke.setup_text
          item["punchline_text"] = joke.punchline_text
          item["setup_image_url"] = joke.setup_image_url
          item["punchline_image_url"] = joke.punchline_image_url
        jokes.append(item)
    else:
      label = get_param(req, 'label', "unknown")
      max_results = get_param(req, 'max_results', 10)
      if not isinstance(max_results, int):
        try:
          max_results = int(max_results)
        except (ValueError, TypeError):
          return error_response(
            f'Max results must be an integer: {max_results}',
            req=req,
            status=400)

      match_mode = get_param(req, 'match_mode', "TIGHT").strip().upper()
      if match_mode == "TIGHT":
        distance_threshold = config.JOKE_SEARCH_TIGHT_THRESHOLD
      elif match_mode == "LOOSE":
        distance_threshold = config.JOKE_SEARCH_LOOSE_THRESHOLD
      else:
        return error_response(f'Invalid match_mode: {match_mode}',
                              req=req,
                              status=400)

      # Filter: public_only (default True) => public_timestamp <= now in LA
      public_only = get_bool_param(req, 'public_only', True)
      field_filters = []
      if public_only:
        field_filters.extend([
          ("state", "in",
           [models.JokeState.PUBLISHED.value, models.JokeState.DAILY.value]),
          ("is_public", "==", True),
        ])

      if exclude_in_book:
        field_filters.append(("book_id", "==", None))

      # Search for jokes
      search_results = search.search_jokes(
        query=search_query,
        label=label,
        limit=max_results,
        field_filters=field_filters,
        distance_threshold=distance_threshold,
        return_jokes=return_jokes,
      )

      # Return jokes with id and vector distance
      for result in search_results:
        item = {
          "joke_id": result.joke_id,
          "vector_distance": result.vector_distance
        }
        if return_jokes:
          item["setup_text"] = result.setup_text
          item["punchline_text"] = result.punchline_text
          item["setup_image_url"] = result.setup_image_url
          item["punchline_image_url"] = result.punchline_image_url
        jokes.append(item)

    return success_response({"jokes": jokes}, req=req)

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error searching jokes: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to search jokes: {str(e)}',
                          req=req,
                          status=500)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def modify_joke_image(req: https_fn.Request) -> https_fn.Response:
  """Modify a joke's images using instructions."""

  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    # Get the joke ID and instructions from request body or args
    joke_id = get_param(req, 'joke_id')
    setup_instruction = get_param(req, 'setup_instruction')
    punchline_instruction = get_param(req, 'punchline_instruction')

    if not joke_id:
      return error_response('Joke ID is required', req=req, status=400)

    if not setup_instruction and not punchline_instruction:
      return error_response(
        'At least one instruction (setup_instruction or punchline_instruction) is required',
        req=req,
        status=400)

    # Load the joke from firestore
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      return error_response(f'Joke not found: {joke_id}', req=req, status=404)

    if setup_instruction:
      error = _modify_and_set_image(
        image_url=joke.setup_image_url,
        instruction=setup_instruction,
        image_setter=functools.partial(joke.set_setup_image,
                                       update_text=False),
        error_message='Joke has no setup image to modify')
      if error:
        return error_response(error, req=req, status=400)

    if punchline_instruction:
      error = _modify_and_set_image(
        image_url=joke.punchline_image_url,
        instruction=punchline_instruction,
        image_setter=functools.partial(joke.set_punchline_image,
                                       update_text=False),
        error_message='Joke has no punchline image to modify')
      if error:
        return error_response(error, req=req, status=400)

    # Save the updated joke back to firestore
    saved_joke = firestore.upsert_punny_joke(joke)
    if not saved_joke:
      return error_response('Failed to save modified joke',
                            req=req,
                            status=500)

    return success_response(
      {"joke_data": joke_operations.to_response_joke(saved_joke)}, req=req)

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error modifying joke image: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to modify joke image: {str(e)}',
                          req=req,
                          status=500)


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


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def critique_jokes(req: https_fn.Request) -> https_fn.Response:
  """Critique a list of jokes using the joke critic agent."""

  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    try:
      user_id = get_user_id(req, allow_unauthenticated=True)
    except AuthError:
      return error_response("Unauthenticated request", req=req, status=401)
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
          return error_response(f'Invalid JSON format for jokes: {str(e)}',
                                req=req,
                                status=400)
      else:
        jokes = []

    if not instructions:
      return error_response('Instructions are required', req=req, status=400)

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
      return error_response('Failed to critique jokes - no results from agent',
                            req=req,
                            status=500)

    return success_response({"critique_data": critique_data}, req=req)

  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error critiquing jokes: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to critique jokes: {str(e)}',
                          req=req,
                          status=500)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def upscale_joke(req: https_fn.Request) -> https_fn.Response:
  """Upscale a joke's images."""
  try:
    if response := handle_cors_preflight(req):
      return response

    if response := handle_health_check(req):
      return response

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}',
                            req=req,
                            status=405)

    joke_id = get_param(req, 'joke_id')
    if not joke_id:
      return error_response('joke_id is required', req=req, status=400)

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
      return error_response(f'Failed to upscale joke: {str(e)}',
                            req=req,
                            status=500)

    return success_response(
      {"joke_data": joke_operations.to_response_joke(joke)}, req=req)
  except Exception as e:
    stacktrace = traceback.format_exc()
    print(f"Error upscaling joke: {e}\nStacktrace:\n{stacktrace}")
    return error_response(f'Failed to upscale joke: {str(e)}',
                          req=req,
                          status=500)
