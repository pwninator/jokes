"""Cloud functions for joke image operations."""

from __future__ import annotations

import json

from firebase_functions import https_fn, logger, options
from functions.function_utils import get_param
from common import image_operations


def _json_response(payload: dict[str, object], *,
                   status: int) -> https_fn.Response:
  """Return a JSON HTTP response."""
  return https_fn.Response(
    json.dumps(payload),
    status=status,
    mimetype='application/json',
  )


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def create_ad_assets(req: https_fn.Request) -> https_fn.Response:
  """HTTP endpoint to generate a landscape ad creative for a joke."""
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method not in ['GET', 'POST']:
    return _json_response(
      {
        "success": False,
        "error": f"Method not allowed: {req.method}",
      },
      status=405,
    )

  joke_id = get_param(req, 'joke_id')
  if not joke_id:
    return _json_response(
      {
        "success": False,
        "error": "joke_id is required",
      },
      status=400,
    )

  try:
    final_url = image_operations.create_ad_assets(joke_id)
  except ValueError as err:
    return _json_response(
      {
        "success": False,
        "error": str(err),
      },
      status=400,
    )
  except Exception as err:  # pylint: disable=broad-except
    logger.error(f"Failed to create ad assets for {joke_id}: {err}")
    return _json_response(
      {
        "success": False,
        "error": "Failed to create ad assets",
      }, status=500)

  html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Joke Ad Creative</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: #f7f7f7;
      }}
      img {{
        max-width: 100%;
        height: auto;
        border: 4px solid #f2d5b1;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
        border-radius: 12px;
      }}
    </style>
  </head>
  <body>
    <h1>Landscape Ad Creative</h1>
    <img src="{final_url}" alt="Joke ad creative" />
  </body>
</html>"""

  return https_fn.Response(html, status=200, mimetype='text/html')
