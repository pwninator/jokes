"""Utility cloud functions for Firestore migrations."""

import json
import traceback
from typing import Any

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param, get_param
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
  """Run Firestore migrations.

  Currently supported:
  - Joke Book ID Sync: Syncs book_id on joke documents based on joke_books.
  """
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
    limit = get_int_param(req, 'limit', 0)
    start_after = get_param(req, 'start_after', "")

    html_response = run_joke_book_id_sync(
      dry_run=dry_run,
      limit=limit,
      start_after=str(start_after or ""),
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


def run_joke_book_id_sync(*, dry_run: bool, limit: int,
                          start_after: str) -> str:
  """Sync `book_id` on joke documents based on `joke_books` collection.

  Iterates through all joke books. For each joke in a book, ensures the
  joke document has the correct `book_id`.

  If a joke is found in multiple books, it will be updated to the last book processed,
  and logged as a discrepancy.
  """
  logger.info(
    "Starting joke book ID sync",
    extra={
      "json_fields": {
        "dry_run": dry_run,
        "limit": limit,
        "start_after": start_after,
      }
    },
  )

  # Query all joke books
  query = db().collection('joke_books').order_by('__name__')
  if start_after:
    query = query.start_after({'__name__': start_after})
  if limit and limit > 0:
    query = query.limit(int(limit))

  stats = {
    'books_processed': 0,
    'jokes_processed': 0,
    'jokes_updated': 0,
    'jokes_skipped_correct': 0,
    'jokes_missing': 0,
    'discrepancies': [], # List of strings describing issues
    'errors': [],
    'last_book_id': None
  }

  client = db()

  for book_doc in query.stream():
    stats['books_processed'] += 1
    stats['last_book_id'] = book_doc.id

    book_data = book_doc.to_dict() or {}
    joke_ids = book_data.get('jokes', [])

    if not joke_ids:
      continue

    # Process jokes in batches (chunks of 30)
    chunk_size = 30
    for i in range(0, len(joke_ids), chunk_size):
      chunk = joke_ids[i:i + chunk_size]

      try:
        joke_refs = [client.collection('jokes').document(jid) for jid in chunk]
        snapshots = client.get_all(joke_refs)

        batch = client.batch()
        batch_has_writes = False

        for joke_snap in snapshots:
          stats['jokes_processed'] += 1

          if not joke_snap.exists:
             stats['jokes_missing'] += 1
             stats['discrepancies'].append(f"Book {book_doc.id} references missing joke {joke_snap.id}")
             continue

          joke_data = joke_snap.to_dict() or {}
          current_book_id = joke_data.get('book_id')

          if current_book_id == book_doc.id:
             stats['jokes_skipped_correct'] += 1
             continue

          if current_book_id and current_book_id != book_doc.id:
             stats['discrepancies'].append(f"Joke {joke_snap.id} has book_id={current_book_id}, but is in book {book_doc.id}. Overwriting.")

          if not dry_run:
             batch.update(joke_snap.reference, {'book_id': book_doc.id})
             batch_has_writes = True
             stats['jokes_updated'] += 1
          else:
             stats['jokes_updated'] += 1 # Count as updated for dry run stats (would update)

        if batch_has_writes and not dry_run:
            batch.commit()

      except Exception as e:
        stats['errors'].append(f"Error processing chunk in book {book_doc.id}: {str(e)}")

  return _build_html_report(dry_run=dry_run, stats=stats)


def _build_html_report(
  *,
  dry_run: bool,
  stats: dict,
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Joke Book ID Sync Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"

  html += "<h3>Stats</h3>"
  html += "<ul>"
  html += f"<li>Books Processed: {stats['books_processed']}</li>"
  html += f"<li>Jokes Processed: {stats['jokes_processed']}</li>"
  html += f"<li>Jokes Updated (or would update): {stats['jokes_updated']}</li>"
  html += f"<li>Jokes Already Correct: {stats['jokes_skipped_correct']}</li>"
  html += f"<li>Missing Joke Docs: {stats['jokes_missing']}</li>"
  if stats['last_book_id']:
      html += f"<li>Last Book ID: {stats['last_book_id']}</li>"
  html += "</ul>"

  if stats['discrepancies']:
    html += f"<h3>Discrepancies ({len(stats['discrepancies'])})</h3>"
    html += "<ul>"
    for d in stats['discrepancies']:
      html += f"<li>{d}</li>"
    html += "</ul>"

  if stats['errors']:
    html += f"<h3 style='color:red'>Errors ({len(stats['errors'])})</h3>"
    html += "<ul>"
    for e in stats['errors']:
      html += f"<li>{e}</li>"
    html += "</ul>"

  html += "</body></html>"
  return html
