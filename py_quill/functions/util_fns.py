"""Utility cloud functions for Firestore migrations."""

import json
import traceback

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param

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
  """Run the jokes fields migration."""
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

    results = run_popularity_score_migration(dry_run=dry_run,
                                             max_jokes=max_jokes)
    return https_fn.Response(
      json.dumps({
        "success": True,
        "results": results
      }),
      status=200,
      mimetype='application/json',
    )
  except Exception as e:  # pylint: disable=broad-except
    logger.error(f"Joke fields migration failed: {e}")
    logger.error(traceback.format_exc())
    return https_fn.Response(
      json.dumps({
        "success": False,
        "error": str(e),
        "message": "Failed to run jokes fields migration"
      }),
      status=500,
      mimetype='application/json',
    )


def run_popularity_score_migration(dry_run: bool, max_jokes: int) -> dict:
  """Populates `popularity_score` for all jokes.

  The popularity_score is calculated as:
    `num_saves + (num_shares * 5)`

  Args:
    dry_run: If True, the migration will only log the changes that would be made.
    max_jokes: The maximum number of jokes to process. If 0, all jokes will be processed.

  Returns:
    A dictionary containing the results of the migration.
  """
  logger.info("Starting popularity score migration...")
  jokes_collection = db().collection('jokes')
  jokes_stream = jokes_collection.stream()

  updated_count = 0
  unchanged_count = 0
  processed_count = 0

  for joke_doc in jokes_stream:
    if max_jokes and processed_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    processed_count += 1
    joke_data = joke_doc.to_dict() or {}
    num_saves = joke_data.get('num_saves', 0)
    num_shares = joke_data.get('num_shares', 0)

    popularity_score = num_saves + (num_shares * 5)

    if joke_data.get('popularity_score') == popularity_score:
      logger.info(
        f"Joke {joke_doc.id} already has the correct popularity score.")
      unchanged_count += 1
      continue

    logger.info(
      f"Joke {joke_doc.id} will be updated with popularity_score: {popularity_score}. Dry run: {dry_run}"
    )
    if not dry_run:
      joke_doc.reference.update({'popularity_score': popularity_score})
      updated_count += 1
    else:
      unchanged_count += 1

  return {
    'total_jokes_processed': processed_count,
    'updated_jokes': updated_count,
    'unchanged_jokes': unchanged_count,
  }
