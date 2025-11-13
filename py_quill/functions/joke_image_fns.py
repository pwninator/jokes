"""Cloud functions for joke image operations."""

from __future__ import annotations

import json

from common import image_operations
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_param
from services import cloud_storage, firestore

_DEFAULT_TOP_JOKES_LIMIT = 5


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
  """HTTP endpoint to generate landscape ad creatives for jokes."""
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

  raw_ids = get_param(req, 'joke_ids')
  if raw_ids:
    joke_ids = [
      joke_id.strip() for joke_id in str(raw_ids).split(',')
      if joke_id.strip()
    ]
  else:
    joke_ids = []

  # Allow optional num_jokes parameter to override default limit
  num_jokes_limit = _DEFAULT_TOP_JOKES_LIMIT
  raw_num = get_param(req, 'num_jokes')
  if raw_num:
    try:
      num_jokes_limit = int(raw_num)
    except (ValueError, TypeError):
      pass  # Use default if not a valid integer

  if not joke_ids:
    top_jokes = firestore.get_top_jokes(
      'popularity_score_recent',
      num_jokes_limit,
    )
    joke_ids = [joke.key for joke in top_jokes if getattr(joke, 'key', None)]
    if not joke_ids:
      return _json_response(
        {
          "success": False,
          "error": "No jokes available to create ad assets",
        },
        status=404,
      )

  rendered_creatives: list[tuple[str, list[str]]] = []
  for joke_id in joke_ids:
    try:
      final_urls = image_operations.create_ad_assets(
        joke_id,
        overwrite=True,
      )
      rendered_creatives.append((joke_id, final_urls))
    except ValueError as err:
      return _json_response(
        {
          "success": False,
          "error": f"{joke_id}: {err}",
        },
        status=400,
      )
    except Exception as err:  # pylint: disable=broad-except
      logger.error(f"Failed to create ad assets for {joke_id}: {err}")
      return _json_response(
        {
          "success": False,
          "error": f"{joke_id}: Failed to create ad assets",
        },
        status=500,
      )

  creatives_html_parts: list[str] = []
  for joke_id, urls in rendered_creatives:
    for url in urls:
      # Modify URL to use PNG format
      png_url = cloud_storage.set_cdn_url_params(url, image_format='png')
      creatives_html_parts.append(f"""    <section class="creative">
      <h2>{joke_id}</h2>
      <img src="{png_url}" alt="Joke {joke_id} ad creative" />
    </section>""")
  creatives_html = "\n".join(creatives_html_parts)

  html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Joke Ad Creatives</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        background: #f7f7f7;
        margin: 0;
        padding: 24px;
      }}
      .creatives {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 24px;
      }}
      .creative {{
        background: #ffffff;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1);
        text-align: center;
      }}
      img {{
        max-width: 100%;
        height: auto;
        border-radius: 12px;
        border: 4px solid #f2d5b1;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.10);
      }}
    </style>
  </head>
  <body>
    <h1>Landscape Ad Creatives</h1>
    <section class="creatives">
{creatives_html}
    </section>
  </body>
</html>"""

  return https_fn.Response(html, status=200, mimetype='text/html')
