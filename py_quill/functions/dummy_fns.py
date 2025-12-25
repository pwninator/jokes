"""Test cloud functions."""

from __future__ import annotations

import random

from firebase_functions import https_fn, options
from common import joke_lead_operations
from services import mailerlite


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=30,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Simple endpoint that creates a dummy MailerLite subscriber for testing."""
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'GET':
    return https_fn.Response("Only GET requests are supported", status=405)

  random_num = random.randint(100000, 999999)
  test_email = f"{random_num}@gmail.com"
  client = mailerlite.MailerLiteClient()
  response = client.create_subscriber(
    email=test_email,
    country_code='US',
    group_id=joke_lead_operations.GROUP_SNICKERDOODLE_CLUB,
  )

  html = f"""<html>
<head><title>MailerLite Dummy Endpoint</title></head>
<body>
  <h1>MailerLite Dummy Endpoint</h1>
  <p>Created subscriber: <strong>{test_email}</strong></p>
  <pre>{response}</pre>
</body>
</html>"""
  return https_fn.Response(html, status=200, mimetype='text/html')
