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

    results = run_jokes_test_migration(dry_run=dry_run, max_jokes=max_jokes)
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


def run_jokes_test_migration(dry_run: bool, max_jokes: int) -> dict:
  """Copies all documents from 'jokes' to 'jokes_test' collection.

  Skips documents that already exist in the target collection.
  Removes the 'zzz_joke_text_embedding' and 'generation_metadata' fields from the copied documents.

  Args:
    dry_run: If True, the migration will only log the changes that would be made.
    max_jokes: The maximum number of jokes to process. If 0, all jokes will be processed.

  Returns:
    A dictionary containing the results of the migration.
  """
  logger.info("Starting jokes_test migration...")
  jokes_collection = db().collection('jokes')
  jokes_test_collection = db().collection('jokes_test')
  jokes_stream = jokes_collection.stream()

  migrated_count = 0
  skipped_count = 0
  processed_count = 0

  for joke_doc in jokes_stream:
    if max_jokes and processed_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    processed_count += 1
    joke_data = joke_doc.to_dict() or {}
    joke_id = joke_doc.id

    # Check if the document already exists in the new collection
    if jokes_test_collection.document(joke_id).get().exists:
      logger.info(f"Joke {joke_id} already exists in jokes_test. Skipping.")
      skipped_count += 1
      continue

    # Remove the zzz_joke_text_embedding and generation_metadata fields
    if 'zzz_joke_text_embedding' in joke_data:
      del joke_data['zzz_joke_text_embedding']
    if 'generation_metadata' in joke_data:
      del joke_data['generation_metadata']

    logger.info(
      f"Joke {joke_id} will be migrated to jokes_test. Dry run: {dry_run}")
    if not dry_run:
      jokes_test_collection.document(joke_id).set(joke_data)
      migrated_count += 1
    else:
      # In dry run, we don't actually migrate, so we consider it skipped
      skipped_count += 1

  return {
    'total_jokes_processed': processed_count,
    'migrated_jokes': migrated_count,
    'skipped_jokes': skipped_count,
  }
