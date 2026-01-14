"""Test cloud functions."""

from __future__ import annotations
from firebase_functions import https_fn, options
from common import image_generation
from agents import constants
from functions.function_utils import get_param


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Endpoint to generate an image from a description."""
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  image_url_html = ""

  # Default values for form pre-filling
  default_description = ""
  default_pun_text = ""
  default_quality = "medium_mini"

  if req.method == 'POST':
    description = get_param(req, 'image_description')
    pun_text = get_param(req, 'pun_text')
    quality = get_param(req, 'image_quality', 'medium_mini')

    # Update defaults to keep user input
    default_description = description or ""
    default_pun_text = pun_text or ""
    default_quality = quality or "medium_mini"

    if description:
      try:
        image = image_generation.generate_pun_image(
          pun_text=pun_text,
          image_description=description,
          image_quality=quality,
          style_reference_images=constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
        )
        if image and image.url:
          image_url_html = (
            f'<h2>Generated Image:</h2>'
            f'<img src="{image.url}" style="max-width: 500px;"><br><br>')
      except Exception as e:
        image_url_html = f'<p style="color:red;">Error: {str(e)}</p>'

  options_html = ""
  for q in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys():
    selected = "selected" if q == default_quality else ""
    options_html += f'<option value="{q}" {selected}>{q}</option>'

  html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Generate Pun Image</title>
</head>
<body>
  <h1>Generate Pun Image</h1>
  {image_url_html}
  <form method="POST">
    <label>Description:</label><br>
    <textarea name="image_description" rows="4" cols="50" required>{default_description}</textarea><br><br>
    <label>Pun Text:</label><br>
    <input type="text" name="pun_text" value="{default_pun_text}"><br><br>
    <label>Quality:</label><br>
    <select name="image_quality">
      {options_html}
    </select><br><br>
    <input type="submit" value="Generate">
  </form>
</body>
</html>
"""
  return https_fn.Response(html, status=200, mimetype="text/html")
