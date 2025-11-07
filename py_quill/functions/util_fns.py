"""Utility cloud functions for Firestore migrations."""

import json
import math
import traceback

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param
from functions.joke_trigger_fns import MIN_VIEWS_FOR_FRACTIONS
from services import firestore as firestore_service

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

    html_response = run_saved_fraction_migration(
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


def run_saved_fraction_migration(
  dry_run: bool,
  max_jokes: int,
) -> str:
  """
    Sets num_saved_users_fraction to 0 for jokes with low view counts.

    Args:
        dry_run: If True, the migration will only log the changes that would be made.
        max_jokes: The maximum number of jokes to modify. If 0, all jokes will be processed.

    Returns:
        An HTML page listing the jokes that were updated.
    """
  logger.info("Starting num_saved_users_fraction migration...")

  jokes = firestore_service.get_all_punny_jokes()

  updated_jokes: list[dict[str, object]] = []
  skipped_jokes: list[dict[str, object]] = []
  updated_count = 0

  for joke in jokes:
    if max_jokes and updated_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    joke_id = joke.key
    if not joke_id:
      continue

    num_viewed = joke.num_viewed_users or 0
    current_fraction = joke.num_saved_users_fraction or 0.0

    if num_viewed >= MIN_VIEWS_FOR_FRACTIONS:
      skipped_jokes.append({
        "id": joke_id,
        "num_viewed": num_viewed,
        "num_saved_fraction": current_fraction,
        "reason": "num_viewed_users>=threshold",
      })
      continue

    if math.isclose(current_fraction, 0.0, abs_tol=1e-9):
      skipped_jokes.append({
        "id": joke_id,
        "num_viewed": num_viewed,
        "num_saved_fraction": current_fraction,
        "reason": "already_zero",
      })
      continue

    updated_jokes.append({
      "id": joke_id,
      "num_viewed": num_viewed,
      "old_fraction": current_fraction,
    })
    if not dry_run:
      firestore_service.update_punny_joke(joke_id,
                                          {"num_saved_users_fraction": 0.0})
    updated_count += 1

  # Generate HTML response
  html = "<html><body>"
  html += "<h1>num_saved_users_fraction Migration Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Threshold: MIN_VIEWS_FOR_FRACTIONS={MIN_VIEWS_FOR_FRACTIONS}</h2>"
  html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"
  if updated_jokes:
    html += "<ul>"
    for joke in updated_jokes:
      html += (f"<li><b>{joke['id']}</b>: num_viewed={joke['num_viewed']}, "
               f"old_fraction={joke['old_fraction']}</li>")
    html += "</ul>"
  else:
    html += "<p>No jokes were updated.</p>"

  html += f"<h2>Skipped Jokes ({len(skipped_jokes)})</h2>"
  if skipped_jokes:
    html += "<ul>"
    for joke in skipped_jokes:
      html += (f"<li><b>{joke['id']}</b>: num_viewed={joke['num_viewed']}, "
               f"num_saved_fraction={joke['num_saved_fraction']}, "
               f"reason={joke['reason']}</li>")
    html += "</ul>"
  else:
    html += "<p>No jokes were skipped.</p>"

  html += "</body></html>"

  return html
