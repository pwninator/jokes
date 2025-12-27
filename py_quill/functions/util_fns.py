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
  - Cleanup: delete `zzz_joke_text_embedding` field from `jokes` docs
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

    html_response = run_jokes_embedding_cleanup(
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


def run_jokes_embedding_cleanup(*, dry_run: bool, limit: int,
                                start_after: str) -> str:
  """Delete `zzz_joke_text_embedding` from all `jokes` documents.

  Idempotent:
  - If a doc does not contain the field, no write is performed.
  - If a doc contains the field (even if None), we issue an update that removes it.

  Args:
    dry_run: If True, do not write anything.
    limit: If > 0, process at most this many jokes.
    start_after: If non-empty, start after this joke_id (lexicographic).
  """
  logger.info(
    "Starting jokes embedding cleanup",
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
  deleted = 0
  would_delete = 0
  skipped_no_field = 0
  failed: list[dict[str, str]] = []
  last_id: str | None = None

  for doc in query.stream():
    processed += 1
    last_id = doc.id
    data = doc.to_dict() or {}

    if 'zzz_joke_text_embedding' not in data:
      skipped_no_field += 1
      continue

    would_delete += 1

    try:
      if not dry_run:
        db().collection('jokes').document(doc.id).update({
          'zzz_joke_text_embedding':
          DELETE_FIELD,
        })
        deleted += 1
    except Exception as err:  # pylint: disable=broad-except
      failed.append({"joke_id": doc.id, "error": str(err)})

  return _build_html_report(
    dry_run=dry_run,
    success=(len(failed) == 0),
    processed=processed,
    deleted=deleted,
    would_delete=would_delete,
    skipped_no_field=skipped_no_field,
    failed_items=failed,
    last_id=last_id,
  )


def _build_html_report(
  *,
  dry_run: bool,
  success: bool,
  processed: int | None = None,
  deleted: int | None = None,
  would_delete: int | None = None,
  skipped_no_field: int | None = None,
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
  if would_delete is not None:
    html += f"<h2>Would delete</h2><p>{would_delete}</p>"
  if deleted is not None:
    html += f"<h2>Deleted</h2><p>{deleted}</p>"
  if skipped_no_field is not None:
    html += f"<h2>Skipped (field not present)</h2><p>{skipped_no_field}</p>"
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
