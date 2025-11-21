"""Utility cloud functions for Firestore migrations."""

import json
import random
import traceback

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param
from google.cloud.firestore import DELETE_FIELD

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
  """Run the joke book migration."""
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

    html_response = run_joke_book_migration(dry_run=dry_run)
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


def run_joke_book_migration(dry_run: bool) -> str:
  """
    Update a specific joke book's jokes array.

    Args:
        dry_run: If True, the migration will only log the changes that would be made.

    Returns:
        An HTML page listing the migration results.
    """
  logger.info("Starting joke book migration...")

  book_id = "20251115_064522__bbcourirwogb9x6wuqwa"
  book_ref = db().collection('joke_books').document(book_id)
  book_doc = book_ref.get()

  if not book_doc.exists:
    return _build_html_report(
      dry_run=dry_run,
      success=False,
      error=f"Joke book {book_id} not found",
    )

  book_data = book_doc.to_dict() or {}
  original_jokes = book_data.get('jokes', [])

  if not isinstance(original_jokes, list):
    return _build_html_report(
      dry_run=dry_run,
      success=False,
      error=f"Jokes field is not a list: {type(original_jokes)}",
    )

  # Step 1: Convert to set (removes duplicates)
  jokes_set = set(original_jokes)

  # Step 2: Add jokes
  jokes_to_add = [
    "hip_hop__what_is_a_rabbit_s_favourite_s",
    "shell_fies__what_kind_of_photos_do_turtles",
  ]
  for joke_id in jokes_to_add:
    jokes_set.add(joke_id)

  # Step 3: Remove joke
  joke_to_remove = "you_might_step_in_a_poodle__why_should_you_be_careful_when"
  jokes_set.discard(joke_to_remove)

  # Step 4 & 5: Convert back to list, put monkey joke first, randomize rest
  jokes_list = list(jokes_set)
  monkey_joke = "a_monkey__what_kind_of_key_opens_a_banan"

  # Remove monkey joke from list if present
  if monkey_joke in jokes_list:
    jokes_list.remove(monkey_joke)

  # Randomize remaining jokes
  random.shuffle(jokes_list)

  # Put monkey joke first
  updated_jokes = [monkey_joke] + jokes_list

  if dry_run:
    # In dry run, simulate clearing metadata for all jokes
    cleared_jokes = updated_jokes.copy()
    return _build_html_report(
      dry_run=dry_run,
      success=True,
      book_id=book_id,
      original_jokes=original_jokes,
      updated_jokes=updated_jokes,
      added_jokes=jokes_to_add,
      removed_joke=joke_to_remove,
      cleared_jokes=cleared_jokes,
    )

  # Update Firestore
  try:
    book_ref.update({'jokes': updated_jokes})
    logger.info(f"Successfully updated joke book {book_id}")

    # Clear book page image URLs for all jokes in the updated list
    cleared_jokes: list[str] = []
    failed_jokes: list[dict[str, str]] = []

    for joke_id in updated_jokes:
      try:
        metadata_ref = (db().collection('jokes').document(joke_id).collection(
          'metadata').document('metadata'))
        metadata_ref.update({
          'book_page_setup_image_url': DELETE_FIELD,
          'book_page_punchline_image_url': DELETE_FIELD,
        })
        cleared_jokes.append(joke_id)
        logger.info(f"Cleared book page URLs for joke {joke_id}")
      except Exception as err:  # pylint: disable=broad-except
        logger.error(
          f"Failed to clear book page URLs for joke {joke_id}: {err}")
        failed_jokes.append({
          "joke_id": joke_id,
          "error": str(err),
        })

    return _build_html_report(
      dry_run=dry_run,
      success=True,
      book_id=book_id,
      original_jokes=original_jokes,
      updated_jokes=updated_jokes,
      added_jokes=jokes_to_add,
      removed_joke=joke_to_remove,
      cleared_jokes=cleared_jokes,
      failed_jokes=failed_jokes,
    )
  except Exception as err:  # pylint: disable=broad-except
    logger.error(f"Failed to update joke book {book_id}: {err}")
    return _build_html_report(
      dry_run=dry_run,
      success=False,
      error=f"Failed to update Firestore: {err}",
    )


def _build_html_report(
  *,
  dry_run: bool,
  success: bool,
  book_id: str | None = None,
  original_jokes: list[str] | None = None,
  updated_jokes: list[str] | None = None,
  added_jokes: list[str] | None = None,
  removed_joke: str | None = None,
  cleared_jokes: list[str] | None = None,
  failed_jokes: list[dict[str, str]] | None = None,
  error: str | None = None,
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Joke Book Migration Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Status: {'Success' if success else 'Failed'}</h2>"

  if error:
    html += f"<p style='color: red;'><b>Error:</b> {error}</p>"

  if book_id:
    html += f"<h2>Book ID: {book_id}</h2>"

  if original_jokes is not None:
    html += f"<h2>Original Jokes ({len(original_jokes)})</h2>"
    html += "<ul>"
    for joke in original_jokes:
      html += f"<li>{joke}</li>"
    html += "</ul>"

  if updated_jokes is not None:
    html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"
    html += "<ul>"
    for joke in updated_jokes:
      html += f"<li>{joke}</li>"
    html += "</ul>"

  if added_jokes:
    html += f"<h2>Added Jokes ({len(added_jokes)})</h2>"
    html += "<ul>"
    for joke in added_jokes:
      html += f"<li>{joke}</li>"
    html += "</ul>"

  if removed_joke:
    html += "<h2>Removed Joke</h2>"
    html += f"<p>{removed_joke}</p>"

  if cleared_jokes is not None:
    html += f"<h2>Cleared Book Page URLs ({len(cleared_jokes)})</h2>"
    html += "<p>Book page image URLs cleared for the following jokes:</p>"
    html += "<ul>"
    for joke in cleared_jokes:
      html += f"<li>{joke}</li>"
    html += "</ul>"

  if failed_jokes:
    html += f"<h2>Failed to Clear URLs ({len(failed_jokes)})</h2>"
    html += "<ul>"
    for failed in failed_jokes:
      html += (f"<li><b>{failed.get('joke_id')}</b>: "
               f"{failed.get('error')}</li>")
    html += "</ul>"

  html += "</body></html>"
  return html
