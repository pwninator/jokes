"""Test cloud functions (manual utilities)."""

from __future__ import annotations

from common import utils
from firebase_functions import https_fn, options
from functions import function_utils
from functions.function_utils import get_param
from services import cloud_storage, gen_audio


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Manual endpoint to generate multi-speaker dialog audio via Gemini."""
  if preflight := function_utils.handle_cors_preflight(req):
    return preflight
  if health := function_utils.handle_health_check(req):
    return health

  html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Generate Multi-Speaker Audio</title>
</head>
<body>
  <h1>Dummy</h1>
</body>
</html>
"""
  return https_fn.Response(html, status=200, mimetype="text/html")
