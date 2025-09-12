"""Test cloud functions."""

import json

from agents import agents_common, constants
from common import image_generation
from firebase_functions import https_fn, options


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
    return https_fn.Response(json.dumps({
      "error": "Only GET requests are supported",
      "success": False
    }),
                             status=405,
                             mimetype='application/json')

  setup_text = req.args.get("setup_text", "Why did the cat cross the road?")
  setup_description = req.args.get("setup_description",
                                   "A super cute cat crossing the road.")
  punchline_text = req.args.get("punchline_text",
                                "Because it wanted to catch the chicken!")
  punchline_description = req.args.get(
    "punchline_description",
    "The same super cute cat chasing a chubby chicken running down the road")

  if not all(
    [setup_text, setup_description, punchline_text, punchline_description]):
    return https_fn.Response(json.dumps({
      "error":
      "Missing one or more required URL parameters: setup_text, setup_description, punchline_text, punchline_description",
      "success": False
    }),
                             status=400,
                             mimetype='application/json')

  pun_data = [
    (setup_text, setup_description),
    (punchline_text, punchline_description),
  ]

  images = image_generation.generate_pun_images(
    pun_data=pun_data,
    image_quality="gemini",
  )

  html_content = "<html><body>"
  for image in images:
    if image and image.url:
      html_content += f'<img src="{image.url}" width="512" height="512"><br>'
      html_content += f"<p>Prompt: {image.final_prompt}</p><br>"
  html_content += "</body></html>"

  return https_fn.Response(html_content, status=200, mimetype='text/html')
