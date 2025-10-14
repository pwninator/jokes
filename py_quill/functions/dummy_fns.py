"""Test cloud functions."""

import json
import pprint

from agents import agents_common, constants
from agents.endpoints import all_agents
from common import image_generation
from firebase_functions import https_fn, options
from services import image_client


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

  # joke_categorizer_agent = all_agents.get_joke_categorizer_agent_adk_app()
  # output, final_state, agent_generation_metadata = agents_common.run_agent(
  #   adk_app=joke_categorizer_agent,
  #   inputs="Group jokes into categories.",
  #   user_id="dummy_user",
  # )

  pun_text = "A panda rolling down a hill"
  image_description = "A very chubby, roly-poly giant panda is joyfully rolling head over heels down the bright green, grassy hill under a sunny blue sky. The panda is captured mid-somersault, a happy blur of black and white fur, it's back to the ground and 4 legs pointing towards the sky, with a goofy, ecstatic expression, its eyes squeezed shut in delight and paws flailing comically. The text 'A panda rolling down a hill' is written in a bouncy font that follows the curve of the hill. The scene is energetic, silly, and adorable."
  image_quality = "low"

  models_by_version = {
    "gpt-1-mini-low": image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_LOW,
    "gpt-1-mini-medium":
    image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_MEDIUM,
    "gpt-1-mini-high": image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_HIGH,
    "gpt-1-low": image_client.ImageModel.OPENAI_GPT_IMAGE_1_LOW,
    "gpt-1-medium": image_client.ImageModel.OPENAI_GPT_IMAGE_1_MEDIUM,
    "gpt-1-high": image_client.ImageModel.OPENAI_GPT_IMAGE_1_HIGH,
    # "gemini-nano-banana": image_client.ImageModel.GEMINI_NANO_BANANA,
  }

  images_by_version = {}
  for image_version, image_model in models_by_version.items():
    img = image_generation.generate_pun_image(
      pun_text=pun_text,
      image_description=image_description,
      image_quality=image_quality,
      image_client_override=image_client.get_client(
        label="dummy_image_client",
        model=image_model,
        file_name_base="dummy_image"))
    images_by_version[image_version] = img
    print(f"Generated image for {image_version}: {img.url}")


#   return_val = f"""
# <html>
# <body>
# <p>Output: {output}</p>
# <p>Final State: {pprint.pformat(final_state, width=120, sort_dicts=False)}</p>
# <p>Agent Generation Metadata: {agent_generation_metadata}</p>
# </body>
# </html>
# """

# Build HTML table with images
  table_rows = ""
  for version, image in images_by_version.items():
    image_url = image.url if image and hasattr(image,
                                               'url') else "No image generated"
    if image_url and image_url != "No image generated":
      table_rows += f"""
      <tr>
        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">{version}</td>
        <td style="border: 1px solid #ddd; padding: 8px;">
          <img src="{image_url}" alt="{version}" style="max-width: 500px; height: auto;">
        </td>
      </tr>"""
    else:
      table_rows += f"""
      <tr>
        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">{version}</td>
        <td style="border: 1px solid #ddd; padding: 8px; color: red;">{image_url}</td>
      </tr>"""

  return_val = f"""
<!DOCTYPE html>
<html>
<head>
  <title>Generated Images</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 20px;
    }}
    th {{
      border: 1px solid #ddd;
      padding: 12px;
      text-align: left;
      background-color: #4CAF50;
      color: white;
    }}
  </style>
</head>
<body>
  <h1>Generated Pun Images</h1>
  <p><strong>Pun Text:</strong> {pun_text}</p>
  <p><strong>Image Quality:</strong> {image_quality}</p>
  <table>
    <tr>
      <th>Model Version</th>
      <th>Generated Image</th>
    </tr>
    {table_rows}
  </table>
</body>
</html>
"""

  return https_fn.Response(return_val, status=200, mimetype='text/html')
