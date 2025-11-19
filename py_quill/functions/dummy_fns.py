"""Test cloud functions."""
# pylint: disable=unused-import

import json
import pprint
from html import escape

from agents import agents_common, constants
from agents.endpoints import all_agents
from common import image_generation
from firebase_functions import https_fn, options
from functions.function_utils import get_param
from functions.prompts import joke_operation_prompts
from services import cloud_storage, image_client


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Simple test endpoint that returns a success message.

  Args:
      req: The HTTP request.

  Returns:
      HTTP response with test message.
  """
  # Skip processing for health check requests
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

  setup_text = get_param(req, "setup_text")
  punchline_text = get_param(req, "punchline_text")

  (
    setup_scene_description,
    punchline_scene_description,
    _ideas_are_safe,
    generation_metadata,
  ) = joke_operation_prompts.generate_joke_scene_ideas(
    setup_text,
    punchline_text,
  )

  metadata_json = json.dumps(generation_metadata.as_dict, indent=2)

  return_val = f"""
<html>
<body>
  <h1>Joke Scene Descriptions</h1>
  <section>
    <h2>Setup</h2>
    <p><strong>Text:</strong> {escape(setup_text or '')}</p>
    <p><strong>Scene Description:</strong> {escape(setup_scene_description)}</p>
  </section>
  <section>
    <h2>Punchline</h2>
    <p><strong>Text:</strong> {escape(punchline_text or '')}</p>
    <p><strong>Scene Description:</strong> {escape(punchline_scene_description)}</p>
  </section>
  <section>
    <h2>Generation Metadata</h2>
    <pre>{escape(metadata_json)}</pre>
  </section>
</body>
</html>
"""

  return https_fn.Response(return_val, status=200, mimetype='text/html')
