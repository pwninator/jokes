"""Test cloud functions."""
# pylint: disable=unused-import

import base64
from io import BytesIO
import json
import pprint
from html import escape

import requests
from PIL import Image

from agents import agents_common, constants
from agents.endpoints import all_agents
from common import image_generation
from firebase_functions import https_fn, options
from functions.function_utils import get_param
from functions.prompts import joke_operation_prompts
from services import cloud_storage, image_client, image_editor


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

  image_url = get_param(
    req, "url",
    "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20250711_232323_723301.png"
  )
  input_image = Image.open(BytesIO(
    requests.get(image_url, timeout=30).content))

  editor = image_editor.ImageEditor()

  # Convert images to base64 for HTML embedding as 600x600 JPEG @ 50% quality
  def image_to_base64(img: Image.Image) -> str:
    # Ensure RGB (JPEG does not support alpha)
    if img.mode not in ('RGB', 'L'):
      img = img.convert('RGB')

    # Resize to fit within 600x600 while preserving aspect ratio
    max_size = (600, 600)
    img = img.copy()
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=50, optimize=True)
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

  original_b64 = image_to_base64(input_image)

  # Enhanced image using all default enhancement parameters
  default_enhanced = editor.enhance_image(input_image)
  default_enhanced_b64 = image_to_base64(default_enhanced)

  # For grid exploration, we fix histogram_strength to 1.0.
  strength_value = 1.0

  default_params = {
    'soft_clip_base': 0.0,
    'strong_clip_base': 3.0,
    'edge_threshold': 70,
    'mask_blur_ksize': 35,
    'saturation_boost': 1.3,
    'contrast_alpha': 1.1,
    'brightness_beta': 7.0,
    'sharpen_amount': 1.0,
  }

  grid_configs = [
    ("Soft Clip Base", 'soft_clip_base', [0.0, 0.5, 1.0]),
    ("Strong Clip Base", 'strong_clip_base', [2.0, 3.0, 4.0]),
    ("Edge Threshold", 'edge_threshold', [50, 70, 90]),
    ("Mask Blur Size", 'mask_blur_ksize', [9, 35, 51]),
    ("Saturation Boost", 'saturation_boost', [1.2, 1.3, 1.4]),
    ("Contrast Alpha", 'contrast_alpha', [1.07, 1.1, 1.15]),
    ("Brightness Beta", 'brightness_beta', [5, 7, 10]),
    ("Sharpen Amount", 'sharpen_amount', [0.5, 1.0, 1.5]),
  ]

  grid_results = []
  for title, param_key, param_values in grid_configs:
    # For each grid, generate a single row of images (one per param value)
    row_cells = []
    for param_value in param_values:
      param_kwargs = default_params.copy()
      param_kwargs[param_key] = param_value
      enhanced = editor.enhance_image(
        input_image,
        histogram_strength=strength_value,
        **param_kwargs,
      )
      row_cells.append(image_to_base64(enhanced))
    grid_results.append((title, param_key, param_values, row_cells))

  return_val = f"""
<html>
<head>
  <title>Image Enhancement Comparison</title>
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
    .grid-section {{
      margin-bottom: 40px;
    }}
    .grid-section h2 {{
      text-align: center;
      color: #444;
      margin-bottom: 12px;
    }}
    table.param-grid {{
      width: 100%;
      border-collapse: collapse;
      margin: 0 auto;
      max-width: 1920px;
    }}
    table.param-grid th,
    table.param-grid td {{
      border: 1px solid #ddd;
      padding: 8px;
      background-color: white;
      vertical-align: top;
      text-align: center;
    }}
    table.param-grid th.param-header {{
      width: 160px;
      background-color: #f0f3f7;
      font-weight: 600;
      color: #333;
    }}
    table.param-grid th.strength-header {{
      background-color: #f0f3f7;
      font-weight: 600;
      color: #333;
    }}
    table.param-grid img {{
      width: 600px;
      height: auto;
      border-radius: 6px;
      border: 1px solid #ccc;
    }}
    .original-wrapper {{
      display: flex;
      justify-content: center;
      gap: 24px;
      margin-bottom: 40px;
    }}
    .original-panel {{
      text-align: center;
    }}
    .original-panel img {{
      width: 600px;
      border-radius: 6px;
      border: 1px solid #ccc;
    }}
  </style>
</head>
<body>
  <h1>Image Enhancement Comparison</h1>
  <div class="original-wrapper">
    <div class="original-panel">
      <h2>Original</h2>
      <img src="data:image/jpeg;base64,{original_b64}" alt="Original Image" />
    </div>
    <div class="original-panel">
      <h2>Default Enhanced</h2>
      <img src="data:image/jpeg;base64,{default_enhanced_b64}" alt="Default Enhanced Image" />
    </div>
  </div>
  {''.join(
    f'''
    <section class="grid-section">
      <h2>{title}</h2>
      <table class="param-grid">
        <thead>
          <tr>
            <th class="param-header">{param_key.replace('_', ' ').title()}</th>
            {''.join(f'<th class="strength-header">{param_value}</th>' for param_value in param_values)}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th class='param-header'>strength = {strength_value:.1f}</th>
            {''.join(
              f"<td><img src='data:image/jpeg;base64,{row_cells[idx]}' alt='Enhanced ({param_key}={param_values[idx]}, strength={strength_value:.1f})' /></td>"
              for idx in range(len(param_values))
            )}
          </tr>
        </tbody>
      </table>
    </section>
    '''
    for title, param_key, param_values, row_cells in grid_results
  )}
</body>
</html>
  """

  #   setup_text = get_param(req, "setup_text")
  #   punchline_text = get_param(req, "punchline_text")

  #   (
  #     setup_scene_description,
  #     punchline_scene_description,
  #     _ideas_are_safe,
  #     generation_metadata,
  #   ) = joke_operation_prompts.generate_joke_scene_ideas(
  #     setup_text,
  #     punchline_text,
  #   )

  #   metadata_json = json.dumps(generation_metadata.as_dict, indent=2)

  #   return_val = f"""
  # <html>
  # <body>
  #   <h1>Joke Scene Descriptions</h1>
  #   <section>
  #     <h2>Setup</h2>
  #     <p><strong>Text:</strong> {escape(setup_text or '')}</p>
  #     <p><strong>Scene Description:</strong> {escape(setup_scene_description)}</p>
  #   </section>
  #   <section>
  #     <h2>Punchline</h2>
  #     <p><strong>Text:</strong> {escape(punchline_text or '')}</p>
  #     <p><strong>Scene Description:</strong> {escape(punchline_scene_description)}</p>
  #   </section>
  #   <section>
  #     <h2>Generation Metadata</h2>
  #     <pre>{escape(metadata_json)}</pre>
  #   </section>
  # </body>
  # </html>
  # """

  return https_fn.Response(return_val, status=200, mimetype='text/html')
