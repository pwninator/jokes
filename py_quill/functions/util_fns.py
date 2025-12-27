"""Utility cloud functions for Firestore migrations."""

import json
import traceback
from typing import Any

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param, get_param
from google.cloud.firestore_v1.vector import Vector

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
  - Backfill `joke_search` docs from `jokes.zzz_joke_text_embedding`
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

    html_response = run_joke_search_backfill(
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


def run_joke_search_backfill(*, dry_run: bool, limit: int,
                             start_after: str) -> str:
  """Backfill `joke_search` docs from `jokes` docs.

  This is Phase 1-only: it does NOT change how the app searches; it only
  prepares the `joke_search` collection so Phase 2 can safely switch reads.

  Reads:
    - jokes/{joke_id}.zzz_joke_text_embedding
    - plus filter/sort fields used by search (state/is_public/public_timestamp/etc.)

  Writes:
    - joke_search/{joke_id}.text_embedding (Vector)
    - joke_search/{joke_id}.{state,is_public,public_timestamp,num_*_fraction,popularity_score}

  Args:
    dry_run: If True, do not write anything.
    limit: If > 0, process at most this many jokes.
    start_after: If non-empty, start after this joke_id (lexicographic).
  """
  logger.info(
    "Starting joke_search backfill",
    extra={
      "json_fields": {
        "dry_run": dry_run,
        "limit": limit,
        "start_after": start_after,
      }
    },
  )

  query = db().collection('jokes').order_by('__name__')
  if start_after:
    query = query.start_after({'__name__': start_after})
  if limit and limit > 0:
    query = query.limit(int(limit))

  processed = 0
  written = 0
  skipped_missing_embedding = 0
  failed: list[dict[str, str]] = []
  last_id: str | None = None

  def _maybe_add(payload: dict[str, Any], data: dict[str, Any],
                 key: str) -> None:
    value = data.get(key)
    if value is not None:
      payload[key] = value

  for doc in query.stream():
    processed += 1
    last_id = doc.id
    data = doc.to_dict() or {}

    zzz_embedding = data.get('zzz_joke_text_embedding')
    if zzz_embedding is None or isinstance(zzz_embedding, list):
      skipped_missing_embedding += 1
      continue

    embedding = zzz_embedding
    if not isinstance(embedding, Vector):
      try:
        embedding = Vector(list(embedding))
      except Exception as err:  # pylint: disable=broad-except
        failed.append({"joke_id": doc.id, "error": str(err)})
        continue

    payload: dict[str, Any] = {
      'text_embedding': embedding,
    }
    # Fields required for Phase 2 filtering
    _maybe_add(payload, data, 'state')
    _maybe_add(payload, data, 'is_public')
    _maybe_add(payload, data, 'public_timestamp')
    _maybe_add(payload, data, 'num_saved_users_fraction')
    _maybe_add(payload, data, 'num_shared_users_fraction')
    _maybe_add(payload, data, 'popularity_score')

    try:
      if not dry_run:
        db().collection('joke_search').document(doc.id).set(payload,
                                                            merge=True)
      written += 1
    except Exception as err:  # pylint: disable=broad-except
      failed.append({"joke_id": doc.id, "error": str(err)})

  return _build_html_report(
    dry_run=dry_run,
    success=(len(failed) == 0),
    processed=processed,
    written=written,
    skipped_missing_embedding=skipped_missing_embedding,
    failed_items=failed,
    last_id=last_id,
  )


def _build_html_report(
  *,
  dry_run: bool,
  success: bool,
  processed: int | None = None,
  written: int | None = None,
  skipped_missing_embedding: int | None = None,
  failed_items: list[dict[str, str]] | None = None,
  last_id: str | None = None,
  error: str | None = None,
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Firestore Migration Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Status: {'Success' if success else 'Failed'}</h2>"

  if error:
    html += f"<p style='color: red;'><b>Error:</b> {error}</p>"

  if processed is not None:
    html += f"<h2>Processed</h2><p>{processed}</p>"
  if written is not None:
    html += f"<h2>Written</h2><p>{written}</p>"
  if skipped_missing_embedding is not None:
    html += (f"<h2>Skipped (missing embedding)</h2>"
             f"<p>{skipped_missing_embedding}</p>")
  if last_id:
    html += f"<h2>Last processed joke id</h2><p>{last_id}</p>"

  if failed_items:
    html += f"<h2>Failures ({len(failed_items)})</h2>"
    html += "<ul>"
    for failed in failed_items:
      html += (f"<li><b>{failed.get('joke_id')}</b>: "
               f"{failed.get('error')}</li>")
    html += "</ul>"

  html += "</body></html>"
  return html
