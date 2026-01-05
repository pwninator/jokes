"""Test cloud functions."""

from __future__ import annotations
from firebase_functions import https_fn, options
from common import joke_notes_sheet_operations
from services import cloud_storage, firestore
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

  gcs_uri = joke_notes_sheet_operations.get_joke_notes_sheet(
    joke_ids,
    quality=30,
  )

  public_url = cloud_storage.get_storage_googleapis_public_url(gcs_uri)
  html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Joke Notes Sheet</title>
</head>
<body>
  <h1>Joke Notes Sheet Generated</h1>
  <p><a href="{public_url}" target="_blank">Download PDF</a></p>
</body>
</html>
"""
  return https_fn.Response(html, status=200, mimetype="text/html")
