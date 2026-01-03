"""Utility cloud functions for Firestore migrations."""

import json
import traceback

from common import joke_operations, models
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param, get_param
from services import firestore


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def run_firestore_migration(req: https_fn.Request) -> https_fn.Response:
  """Run Firestore migrations.

  Currently supported:
  - Joke metadata backfill: Generate tags/seasonal metadata for jokes missing tags.
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

    html_response = run_joke_metadata_backfill(
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


def run_joke_metadata_backfill(*, dry_run: bool, limit: int,
                               start_after: str) -> str:
  """Generate metadata for jokes missing tags."""
  logger.info(
    "Starting joke metadata backfill",
    extra={
      "json_fields": {
        "dry_run": dry_run,
        "limit": limit,
        "start_after": start_after,
      }
    },
  )

  query = firestore.db().collection('jokes').order_by('__name__')
  if start_after:
    query = query.start_after({'__name__': start_after})
  if limit and limit > 0:
    query = query.limit(int(limit))

  stats = {
    'jokes_processed': 0,
    'jokes_missing_tags': 0,
    'jokes_updated': 0,
    'jokes_skipped_has_tags': 0,
    'errors': [],
    'last_joke_id': None
  }

  for joke_doc in query.stream():
    stats['jokes_processed'] += 1
    stats['last_joke_id'] = joke_doc.id

    if not joke_doc.exists:
      continue

    joke_data = joke_doc.to_dict() or {}
    joke = models.PunnyJoke.from_firestore_dict(joke_data, key=joke_doc.id)

    if joke.tags:
      stats['jokes_skipped_has_tags'] += 1
      continue

    stats['jokes_missing_tags'] += 1

    if dry_run:
      stats['jokes_updated'] += 1
      continue

    try:
      joke = joke_operations.generate_joke_metadata(joke)
      firestore.upsert_punny_joke(joke, operation="BACKFILL_METADATA")
      stats['jokes_updated'] += 1
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        "Failed to backfill joke metadata",
        extra={"json_fields": {
          "joke_id": joke_doc.id,
          "error": str(exc),
        }},
      )
      stats['errors'].append(f"Joke {joke_doc.id}: {str(exc)}")

  return _build_html_report(dry_run=dry_run, stats=stats)


def _build_html_report(
  *,
  dry_run: bool,
  stats: dict,
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Joke Metadata Backfill Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"

  html += "<h3>Stats</h3>"
  html += "<ul>"
  html += f"<li>Jokes Processed: {stats['jokes_processed']}</li>"
  html += f"<li>Jokes Missing Tags: {stats['jokes_missing_tags']}</li>"
  html += f"<li>Jokes Updated (or would update): {stats['jokes_updated']}</li>"
  html += f"<li>Jokes Skipped (already tagged): {stats['jokes_skipped_has_tags']}</li>"
  if stats['last_joke_id']:
    html += f"<li>Last Joke ID: {stats['last_joke_id']}</li>"
  html += "</ul>"

  if stats['errors']:
    html += f"<h3 style='color:red'>Errors ({len(stats['errors'])})</h3>"
    html += "<ul>"
    for e in stats['errors']:
      html += f"<li>{e}</li>"
    html += "</ul>"

  html += "</body></html>"
  return html
