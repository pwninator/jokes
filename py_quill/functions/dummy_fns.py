"""Test cloud functions."""

from __future__ import annotations

import random

import base64
from firebase_functions import https_fn, options
from common import image_operations
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

  # Generate image
  image_bytes = image_operations.create_joke_notes_sheet(joke_ids)
  b64_image = base64.b64encode(image_bytes).decode('utf-8')

  html = f"""<html>
<head><title>Joke Notes Sheet</title></head>
<body>
  <h1>Joke Notes Sheet ({len(joke_ids)} jokes)</h1>
  <img src="data:image/jpeg;base64,{b64_image}" style="max-width: 100%; border: 1px solid #ccc;">
</body>
</html>"""
  return https_fn.Response(html, status=200, mimetype='text/html')
