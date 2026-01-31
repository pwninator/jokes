"""Utility cloud functions for Firestore migrations."""

import json
import traceback
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
  - MailerLite subscriber id backfill: Initialize mailerlite_subscriber_id to null for users missing the field.
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

    html_response = run_mailerlite_subscriber_id_backfill(
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


def run_mailerlite_subscriber_id_backfill(*, dry_run: bool, limit: int,
                                          start_after: str) -> str:
  """Backfill mailerlite_subscriber_id for users missing the field."""
  logger.info(
    "Starting mailerlite_subscriber_id backfill",
    extra={
      "json_fields": {
        "dry_run": dry_run,
        "limit": limit,
        "start_after": start_after,
      }
    },
  )

  query = firestore.db().collection('users').order_by('__name__')
  if start_after:
    query = query.start_after({'__name__': start_after})
  if limit and limit > 0:
    query = query.limit(int(limit))

  stats = {
    'users_processed': 0,
    'users_missing_field': 0,
    'users_updated': 0,
    'users_skipped_existing': 0,
    'errors': [],
    'last_user_id': None
  }

  for user_doc in query.stream():
    stats['users_processed'] += 1
    stats['last_user_id'] = user_doc.id

    if not user_doc.exists:
      continue

    user_data = user_doc.to_dict() or {}
    if not isinstance(user_data, dict):
      user_data = {}

    if 'mailerlite_subscriber_id' in user_data:
      stats['users_skipped_existing'] += 1
      continue

    stats['users_missing_field'] += 1

    if dry_run:
      stats['users_updated'] += 1
      continue

    try:
      user_doc.reference.update({'mailerlite_subscriber_id': None})
      stats['users_updated'] += 1
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        "Failed to backfill mailerlite_subscriber_id",
        extra={
          "json_fields": {
            "user_id": user_doc.id,
            "error": str(exc),
          }
        },
      )
      stats['errors'].append(f"User {user_doc.id}: {str(exc)}")

  return _build_html_report(dry_run=dry_run, stats=stats)


def _build_html_report(
  *,
  dry_run: bool,
  stats: dict,
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>MailerLite Subscriber Id Backfill Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"

  html += "<h3>Stats</h3>"
  html += "<ul>"
  html += f"<li>Users Processed: {stats['users_processed']}</li>"
  html += f"<li>Users Missing Field: {stats['users_missing_field']}</li>"
  html += f"<li>Users Updated (or would update): {stats['users_updated']}</li>"
  html += f"<li>Users Skipped (already set): {stats['users_skipped_existing']}</li>"
  if stats['last_user_id']:
    html += f"<li>Last User ID: {stats['last_user_id']}</li>"
  html += "</ul>"

  if stats['errors']:
    html += f"<h3 style='color:red'>Errors ({len(stats['errors'])})</h3>"
    html += "<ul>"
    for e in stats['errors']:
      html += f"<li>{e}</li>"
    html += "</ul>"

  html += "</body></html>"
  return html
