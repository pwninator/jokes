"""Test cloud functions."""

from __future__ import annotations
from firebase_functions import https_fn, options
from common import joke_notes_sheet_operations
from services import firestore
from google.cloud.firestore import FieldFilter


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=60,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Endpoint that generates a joke notes sheet for 6 arbitrary jokes."""
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'GET':
    return https_fn.Response("Only GET requests are supported", status=405)

  # Fetch jokes that have a setup image
  jokes_ref = firestore.db().collection('jokes')
  query = jokes_ref.where(
    filter=FieldFilter("setup_image_url", ">", "")).limit(20)
  docs = query.stream()

  joke_ids = []
  for doc in docs:
    data = doc.to_dict()
    # Ensure it also has a punchline image
    if data.get('punchline_image_url'):
      joke_ids.append(doc.id)
    if len(joke_ids) >= 6:
      break

  if not joke_ids:
    return https_fn.Response("No valid jokes found", status=404)

  # Generate PDF
  pdf_bytes = joke_notes_sheet_operations.create_joke_notes_sheet(
    joke_ids,
    quality=30,
  )
  return https_fn.Response(pdf_bytes, status=200, mimetype='application/pdf')
