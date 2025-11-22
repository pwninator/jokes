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

  # return_val = run_create_book_pages_test(joke_id=get_param(req, 'joke_id'))
  return_val = run_page_generation_test()

  return https_fn.Response(return_val, status=200, mimetype='text/html')


def run_create_book_pages_test(joke_id: str) -> str:
  """Run a test to create book pages for a joke."""
  book_page_setup_url, book_page_punchline_url = image_operations.generate_and_populate_book_pages(
    joke_id,
    overwrite=True,
  )
  return_val = f"""
<html>
<head>
  <title>Book Page Generation Test</title>
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
      grid-template-columns: repeat(5, 1fr);
      gap: 24px;
      max-width: 4000px;
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
    .metadata-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      max-width: 1600px;
      margin: 40px auto 0;
    }}
    .metadata-panel {{
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      font-family: 'Courier New', monospace;
      text-align: left;
      overflow-x: auto;
    }}
    .metadata-panel pre {{
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
    }}
  </style>
</head>
<body>
  <h1>Book Page Generation Test</h1>
  <div class="comparison-grid">
    <div class="image-panel">
      <h3>Book Page Setup</h3>
      {img_tag(book_page_setup_url, "Book Page Setup Image")}
    </div>
    <div class="image-panel">
      <h3>Book Page Punchline</h3>
      {img_tag(book_page_punchline_url, "Book Page Punchline Image")}
    </div>
  </div>
</body>
</html>
"""
  return return_val


def run_page_generation_test() -> str:
  """Run a test to compare original image with outpainted version.
  
  Args:
    setup_url: The URL of the setup image to test.
    punchline_url: The URL of the punchline image to test.

  Returns:
    HTML string showing setup and punchline images and the generated book page image.
  """
  setup_description = "A whimsical and silly sketch, appearing as if drawn with colored pencils on lightly textured paper to create a naive charm. The artwork is unbearably cute, with soft, sketchy lines and a vibrant, gentle, but bright color palette where colors sometimes stray playfully outside the lines. A super cute, fluffy brown rabbit is down on one knee in a grassy field, proposing to his equally cute, white fluffy girlfriend rabbit. The girlfriend rabbit has her paws clasped to her chest, looking surprised and delighted. The male rabbit is holding a small, closed ring box behind his back, hiding it from view. The scene is romantic and sweet, with a few small wildflowers in the background. The text 'What did the rabbit use to propose to his girlfriend?' is displayed prominently. The only text on the image is the phrase 'What did the rabbit use to propose to his girlfriend?', prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch."

  punchline_description = "Generate another image using the same artistic style, color palette, background texture, and overall aesthetic as the reference images. Make sure the characters, objects, etc. are consistent. A close-up of the two adorable rabbits. The fluffy brown male rabbit is proudly presenting an open ring box to his girlfriend. Inside the box is a ring cleverly crafted from a bright orange carrot, with a tiny green carrot top acting as the 'gem'. The white female rabbit looks ecstatic, with wide, sparkling eyes and a huge, happy smile. The scene is funny and heartwarming. The text 'A 24-carrot ring' is displayed prominently. The only text on the image is the phrase 'A 24-carrot ring', prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch."

  setup_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/a_24_carrot_ring__what_did_the_rabbit_use_to_pro_setup_hq_20251119_221531_973121.png"

  punchline_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/a_24_carrot_ring__what_did_the_rabbit_use_to_pro_2.png"

  response = requests.get(setup_url, timeout=10)
  response.raise_for_status()
  original_setup_image = Image.open(BytesIO(response.content))
  response = requests.get(punchline_url, timeout=10)
  response.raise_for_status()
  original_punchline_image = Image.open(BytesIO(response.content))

  reference_image_url = "https://storage.googleapis.com/images.quillsstorybook.com/_joke_assets/book_page_reference_image_1024.jpg"
  response = requests.get(reference_image_url, timeout=10)
  response.raise_for_status()
  reference_image = Image.open(BytesIO(response.content))

  generation_result = image_operations.generate_book_pages_with_nano_banana_pro(
    setup_image=original_setup_image,
    punchline_image=original_punchline_image,
    setup_image_description=setup_description,
    punchline_image_description=punchline_description,
    style_reference_image=reference_image,
    output_file_name_base='book_page_generation_test',
  )
  simple_setup_image = cloud_storage.download_image_from_gcs(
    generation_result.simple_setup_image.gcs_uri)
  simple_punchline_image = cloud_storage.download_image_from_gcs(
    generation_result.simple_punchline_image.gcs_uri)
  generated_setup_image = cloud_storage.download_image_from_gcs(
    generation_result.generated_setup_image.gcs_uri)
  generated_punchline_image = cloud_storage.download_image_from_gcs(
    generation_result.generated_punchline_image.gcs_uri)
  setup_image_thought = generation_result.generated_setup_image.model_thought
  punchline_image_thought = generation_result.generated_punchline_image.model_thought

  setup_metadata_html = metadata_panel(
    generation_result.generated_setup_image,
    "Generated Setup Metadata",
  )
  punchline_metadata_html = metadata_panel(
    generation_result.generated_punchline_image,
    "Generated Punchline Metadata",
  )
  metadata_html = ('<div class="metadata-grid">\n'
                   f'{setup_metadata_html}\n'
                   f'{punchline_metadata_html}\n'
                   '</div>')

  # Add model thoughts section
  setup_thought_text = escape(
    setup_image_thought
  ) if setup_image_thought else '<em>No thought available</em>'
  punchline_thought_text = escape(
    punchline_image_thought
  ) if punchline_image_thought else '<em>No thought available</em>'
  thoughts_html = (f'<div class="metadata-grid">\n'
                   f'  <div class="metadata-panel">\n'
                   f'    <h3>Setup Model Thought</h3>\n'
                   f'    <pre>{setup_thought_text}</pre>\n'
                   f'  </div>\n'
                   f'  <div class="metadata-panel">\n'
                   f'    <h3>Punchline Model Thought</h3>\n'
                   f'    <pre>{punchline_thought_text}</pre>\n'
                   f'  </div>\n'
                   f'</div>')

  return_val = f"""
<html>
<head>
  <title>Book Page Generation Test</title>
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
      grid-template-columns: repeat(5, 1fr);
      gap: 24px;
      max-width: 4000px;
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
    .metadata-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      max-width: 1600px;
      margin: 40px auto 0;
    }}
    .metadata-panel {{
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      font-family: 'Courier New', monospace;
      text-align: left;
      overflow-x: auto;
    }}
    .metadata-panel pre {{
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
    }}
  </style>
</head>
<body>
  <h1>Book Page Generation Test</h1>
  <div class="comparison-grid">
    <div class="image-panel">
      <h3>Original Setup</h3>
      {img_tag(setup_url, "Original Setup Image")}
    </div>
    <div class="image-panel">
      <h3>Simple Setup</h3>
      {img_from_bytes(simple_setup_image, "Simple Setup Image")}
    </div>
    <div class="image-panel">
      <h3>Generated Setup</h3>
      {img_from_bytes(generated_setup_image, "Generated Setup Image")}
    </div>
  </div>
  <div class="comparison-grid">
    <div class="image-panel">
      <h3>Original Punchline</h3>
      {img_tag(punchline_url, "Original Punchline Image")}
    </div>
    <div class="image-panel">
      <h3>Simple Punchline</h3>
      {img_from_bytes(simple_punchline_image, "Simple Punchline Image")}
    </div>
    <div class="image-panel">
      <h3>Generated Punchline</h3>
      {img_from_bytes(generated_punchline_image, "Generated Punchline Image")}
    </div>
  </div>
  <div class="comparison-grid">
    <div class="image-panel">
      <h3>Style Reference</h3>
      {img_tag(reference_image_url, "Style Reference Image")}
    </div>
  </div>
  {metadata_html}
  {thoughts_html}
</body>
</html>
"""
  return return_val


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
    model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
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

  book_page_setup_image, book_page_punchline_image = image_operations.generate_and_populate_book_pages(
    joke_id,
    overwrite=True,
  )
  book_page_setup_url = cloud_storage.get_public_url(
    book_page_setup_image.gcs_uri)
  book_page_punchline_url = cloud_storage.get_public_url(
    book_page_punchline_image.gcs_uri)

  def render_image_section(title: str, left_label: str, left_url: str,
                           right_label: str, right_url: str) -> str:
    """Render a section comparing two related images."""

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


def img_tag(url: str, alt: str) -> str:
  if url:
    return f'<img src="{escape(url)}" alt="{escape(alt)}" />'
  return '<div class="error-message">No image URL</div>'


def img_from_bytes(image: Image.Image, alt: str) -> str:
  """Convert PIL Image to base64 data URI."""
  buffer = BytesIO()
  image.save(buffer, format='PNG')
  img_bytes = buffer.getvalue()
  img_base64 = base64.b64encode(img_bytes).decode('utf-8')
  return f'<img src="data:image/png;base64,{img_base64}" alt="{escape(alt)}" />'


def metadata_panel(image_obj, title: str) -> str:
  """Render generation metadata for an image."""
  metadata = getattr(image_obj, 'generation_metadata', None)
  if metadata:
    metadata_dict = metadata.as_dict
    metadata_json = escape(json.dumps(metadata_dict, indent=2, sort_keys=True))
    content = f"<pre>{metadata_json}</pre>"
  else:
    content = "<p>No metadata available.</p>"
  return (f'<div class="metadata-panel">\n'
          f'  <h3>{escape(title)}</h3>\n'
          f'  {content}\n'
          f'</div>')
