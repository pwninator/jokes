"""Test cloud functions."""
# pylint: disable=unused-import

import base64
import json
import pprint
import traceback
from html import escape
from io import BytesIO

import requests
from agents import agents_common, constants
from agents.endpoints import all_agents
from common import image_generation, image_operations, joke_operations
from firebase_functions import https_fn, options
from functions.function_utils import get_param, get_int_param
from functions.prompts import joke_operation_prompts
from PIL import Image
from services import cloud_storage, firestore, image_client, image_editor


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Test endpoint that compares original images with outpainted versions.

  Args:
      req: The HTTP request. Requires 'image_url' parameter.

  Returns:
      HTTP response with HTML page showing comparison images.
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

  # return_val = run_outpaint_test(
  #   get_param(req, "image_url"),
  #   prompt=get_param(
  #     req,
  #     "prompt",
  #     "Extend the image",
  #   ),
  # )
  return_val = run_book_page_test(joke_id=get_param(req, "joke_id"))

  return https_fn.Response(return_val, status=200, mimetype='text/html')


def run_outpaint_test(image_url: str, prompt: str) -> str:
  """Run a test to compare original image with outpainted version.
  
  Args:
    image_url: The URL of the image to test.
    prompt: The prompt to use for outpainting.
    exterior_guide_pixels: The number of pixels to use for the exterior guide.

  Returns:
    HTML string showing original and outpainted images.
  """
  # Convert image URL to GCS URI
  gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(image_url)

  # Hard-coded outpainting margins
  top = 75
  bottom = 75
  left = 51
  right = 75

  # Outpaint image
  outpaint_client = image_client.get_client(
    label='outpaint_test',
    model=image_client.ImageModel.DUMMY_OUTPAINTER,
    file_name_base='outpaint_test',
  )
  outpainted = outpaint_client.outpaint_image(
    top=top,
    bottom=bottom,
    left=left,
    right=right,
    prompt=prompt,
    gcs_uri=gcs_uri,
    save_to_firestore=False,
  )
  if not outpainted.gcs_uri:
    raise ValueError('Outpainting did not return a GCS URI')
  outpainted_url = cloud_storage.get_final_image_url(outpainted.gcs_uri)

  def img_tag(url: str, alt: str) -> str:
    if url:
      return f'<img src="{escape(url)}" alt="{escape(alt)}" />'
    return '<div class="error-message">No image URL</div>'

  return_val = f"""
<html>
<head>
  <title>Outpaint Test</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      background-color: #f5f5f5;
    }}
    h1 {{
      text-align: center;
      color: #333;
    }}
    .comparison-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      max-width: 1800px;
      margin: 0 auto;
    }}
    .image-panel {{
      text-align: center;
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .image-panel h3 {{
      margin-top: 0;
      color: #444;
      font-size: 1.1em;
    }}
    .image-panel img {{
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      border: 2px solid #ddd;
    }}
    .error-message {{
      color: #d32f2f;
      padding: 10px;
      background-color: #ffebee;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
  <h1>Outpaint Test</h1>
  <div class="comparison-grid">
    <div class="image-panel">
      <h3>Original</h3>
      {img_tag(image_url, "Original Image")}
    </div>
    <div class="image-panel">
      <h3>Outpainted</h3>
      {img_tag(outpainted_url, "Outpainted Image")}
    </div>
  </div>
</body>
</html>
"""
  return return_val


def run_book_page_test(joke_id: str) -> str:
  """Run a test to compare original images with book page versions."""
  original_joke = firestore.get_punny_joke(joke_id)
  if not original_joke:
    return https_fn.Response(
      json.dumps({
        "error": f"Joke not found: {joke_id}",
        "success": False
      }),
      status=404,
      mimetype='application/json',
    )

  original_setup_url = original_joke.setup_image_url
  original_punchline_url = original_joke.punchline_image_url

  book_page_setup_url, book_page_punchline_url = image_operations.create_book_pages(
    joke_id,
    overwrite=True,
  )

  def render_image_section(title: str, left_label: str, left_url: str,
                           right_label: str, right_url: str) -> str:
    """Render a section comparing two related images."""

    def img_tag(url: str, alt: str) -> str:
      if url:
        return f'<img src="{escape(url)}" alt="{escape(alt)}" />'
      return '<div class="error-message">No image URL</div>'

    return f"""
  <section class="image-section">
    <h2>{escape(title)}</h2>
    <div class="comparison-grid">
      <div class="image-panel">
        <h3>{escape(left_label)}</h3>
        {img_tag(left_url, f"{title} - {left_label}")}
      </div>
      <div class="image-panel">
        <h3>{escape(right_label)}</h3>
        {img_tag(right_url, f"{title} - {right_label}")}
      </div>
    </div>
  </section>
"""

  return_val = f"""
<html>
<head>
  <title>Book Page Comparison - Joke {escape(joke_id)}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      background-color: #f5f5f5;
    }}
    h1 {{
      text-align: center;
      color: #333;
    }}
    .image-section {{
      margin-bottom: 40px;
    }}
    .image-section h2 {{
      text-align: center;
      color: #444;
      font-size: 1.5em;
      margin-bottom: 20px;
    }}
    .comparison-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      max-width: 1800px;
      margin: 0 auto;
    }}
    .image-panel {{
      text-align: center;
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .image-panel h3 {{
      margin-top: 0;
      color: #444;
      font-size: 1.1em;
    }}
    .image-panel img {{
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      border: 2px solid #ddd;
    }}
    .error-message {{
      color: #d32f2f;
      padding: 10px;
      background-color: #ffebee;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
  <h1>Book Page Comparison - Joke {escape(joke_id)}</h1>
  {render_image_section("Original Images", "Punchline", original_punchline_url, "Setup", original_setup_url)}
  {render_image_section("Book Page Images", "Punchline Book Page", book_page_punchline_url, "Setup Book Page", book_page_setup_url)}
</body>
</html>
"""
  return return_val
