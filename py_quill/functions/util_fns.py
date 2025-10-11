"""Utility cloud functions for Firestore migrations."""

import json
import traceback

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import (get_bool_param, get_float_param,
                                      get_int_param, get_param)
from services import firestore as firestore_service
from services import search

_db = None  # pylint: disable=invalid-name


def db() -> firestore.client:
  """Get the firestore client."""
  global _db  # pylint: disable=global-statement
  if _db is None:
    _db = firestore.client()
  return _db


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def run_firestore_migration(req: https_fn.Request) -> https_fn.Response:
  """Run a Firestore migration."""
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
    threshold = get_float_param(req, 'threshold', 0.5)

    html_response = run_seasonal_migration(
      query=query,
      threshold=threshold,
      dry_run=dry_run,
      max_jokes=max_jokes,
    )
    return https_fn.Response(html_response, status=200, mimetype='text/html')

  except Exception as e:  # pylint: disable=broad-except
    logger.error(f"Firestore migration failed: {e}")
    logger.error(traceback.format_exc())
    return https_fn.Response(
      json.dumps({
        "success": False,
        "error": str(e),
        "message": "Failed to run Firestore migration"
      }),
      status=500,
      mimetype='application/json',
    )


def run_seasonal_migration(
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
        dry_run: If True, the migration will only log the changes that would be made.
        max_jokes: The maximum number of jokes to modify. If 0, all jokes will be processed.

    Returns:
        An HTML page listing the jokes that were updated.
    """
  logger.info("Starting seasonal migration...")

  search_results = search.search_jokes(
    query=query,
    label="seasonal_migration",
    limit=1000,  # A reasonable upper limit on search results to check
    distance_threshold=threshold,
  )

  updated_jokes = []
  skipped_jokes = []
  updated_count = 0

  for result in search_results:
    if max_jokes and updated_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    joke_id = result.joke.key
    if not joke_id:
      continue

    joke = firestore_service.get_punny_joke(joke_id)
    if not joke:
      logger.warning(f"Could not retrieve joke with id: {joke_id}")
      continue

    if joke.seasonal != "Halloween":
      updated_jokes.append({
        "id": joke_id,
        "setup": joke.setup_text,
        "punchline": joke.punchline_text,
        "old_seasonal": joke.seasonal,
      })
      if not dry_run:
        firestore_service.update_punny_joke(joke_id, {"seasonal": "Halloween"})
      updated_count += 1
    else:
      skipped_jokes.append({
        "id": joke_id,
        "setup": joke.setup_text,
        "punchline": joke.punchline_text,
      })

  # Generate HTML response
  html = "<html><body>"
  html += "<h1>Seasonal Migration Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"
  if updated_jokes:
    html += "<ul>"
    for joke in updated_jokes:
      html += f"<li><b>{joke['id']}</b>: {joke['setup']} / {joke['punchline']} (Old seasonal: {joke['old_seasonal']})</li>"
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
