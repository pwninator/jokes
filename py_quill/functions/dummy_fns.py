"""Test cloud functions."""

from __future__ import annotations

from agents import constants
from common import image_generation, utils
from firebase_functions import https_fn, options
from functions.function_utils import get_param

_PROMPT_PREAMBLE = image_generation._IMAGE_GENERATION_PROMPT_PREAMBLE.strip()
_SETUP_PROMPT_TEMPLATE = (
  f"{_PROMPT_PREAMBLE}\n\n"
  f"{image_generation._STYLE_REFERENCE_GUIDANCE.format(num_style_refs=len(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS))}\n\n"
  "SETUP_IMAGE_DESCRIPTION_HERE")
_PUNCHLINE_PROMPT_TEMPLATE = (f"{_PROMPT_PREAMBLE}\n\n"
                              f"{image_generation._PRIOR_PANEL_GUIDANCE}\n\n"
                              "PUNCHLINE_IMAGE_DESCRIPTION_HERE")


def _select_image_client(image_quality: str):
  if utils.is_emulator():
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY["low"]
  if image_quality in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY[image_quality]
  raise ValueError(f"Invalid image quality: {image_quality}")


def _get_list_param(req: https_fn.Request, param_name: str) -> list[str]:
  if req.is_json:
    json_data = req.get_json()
    data = json_data.get('data', {}) if isinstance(json_data, dict) else {}
    value = data.get(param_name, [])
    if isinstance(value, list):
      return [str(item) for item in value if str(item)]
    if value:
      return [str(value)]
    return []

  if hasattr(req, "form"):
    form = req.form
    getlist = getattr(form, "getlist", None)
    if callable(getlist):
      return [str(item) for item in getlist(param_name) if str(item)]
    if isinstance(form, dict):
      value = form.get(param_name, [])
      if isinstance(value, list):
        return [str(item) for item in value if str(item)]
      if value:
        return [str(value)]

  if hasattr(req, "args"):
    value = req.args.get(param_name)
    if value:
      return [str(value)]
  return []


def _is_checkbox_checked(req: https_fn.Request,
                         param_name: str,
                         default: bool = False) -> bool:
  value = get_param(req, param_name, None)
  if value is None:
    return default
  if isinstance(value, bool):
    return value
  return str(value).strip().lower() in {"true", "1", "on", "yes"}


def _filter_reference_images(selected_urls: list[str],
                             allowed_urls: list[str]) -> list[str]:
  allowed = set(allowed_urls)
  return [url for url in selected_urls if url in allowed]


def _render_reference_checkboxes(
  *,
  name: str,
  image_urls: list[str],
  selected_urls: list[str],
) -> str:
  if not image_urls:
    return ""
  items_html = "".join(
    f'<label style="display:flex; flex-direction:column; align-items:center; margin-right: 8px;">'
    f'<img src="{url}" width="100">'
    f'<input type="checkbox" name="{name}" value="{url}" {"checked" if url in selected_urls else ""}>'
    f'</label>' for url in image_urls)
  return f'<div style="display:flex; flex-wrap:wrap;">{items_html}</div>'


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Endpoint to generate setup/punchline images from raw prompts."""
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  image_url_html = ""

  # Default values for form pre-filling
  default_setup_prompt = _SETUP_PROMPT_TEMPLATE
  default_punchline_prompt = _PUNCHLINE_PROMPT_TEMPLATE
  default_quality = "medium_mini"
  available_reference_images = constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS
  selected_setup_reference_images = available_reference_images[:]
  selected_punchline_reference_images: list[str] = []
  include_setup_image_reference = True

  if req.method == 'POST':
    setup_prompt = get_param(req, 'setup_image_prompt')
    punchline_prompt = get_param(req, 'punchline_image_prompt')
    quality = get_param(req, 'image_quality', 'medium_mini')
    selected_setup_reference_images = _filter_reference_images(
      _get_list_param(req, 'setup_reference_images'),
      available_reference_images,
    )
    selected_punchline_reference_images = _filter_reference_images(
      _get_list_param(req, 'punchline_reference_images'),
      available_reference_images,
    )
    include_setup_image_reference = _is_checkbox_checked(
      req,
      'include_setup_image',
      default=False,
    )

    # Update defaults to keep user input
    default_setup_prompt = setup_prompt or ""
    default_punchline_prompt = punchline_prompt or ""
    default_quality = quality or "medium_mini"

    setup_prompt = (setup_prompt or "").strip()
    punchline_prompt = (punchline_prompt or "").strip()

    if setup_prompt and punchline_prompt:
      try:
        client = _select_image_client(quality)
        setup_image = client.generate_image(
          setup_prompt,
          selected_setup_reference_images or None,
          save_to_firestore=False,
        )
        if not setup_image or not setup_image.url:
          raise ValueError(f"Generated setup image has no URL: {setup_image}")

        previous_image_reference = None
        if setup_image.custom_temp_data.get("image_generation_call_id"):
          previous_image_reference = setup_image.custom_temp_data[
            "image_generation_call_id"]
        elif setup_image.gcs_uri:
          previous_image_reference = setup_image.gcs_uri

        punchline_reference_images = selected_punchline_reference_images[:]
        if include_setup_image_reference and previous_image_reference:
          punchline_reference_images.append(previous_image_reference)

        punchline_image = client.generate_image(
          punchline_prompt,
          punchline_reference_images or None,
          save_to_firestore=False,
        )

        if not punchline_image or not punchline_image.url:
          raise ValueError(
            f"Generated punchline image has no URL: {punchline_image}")

        image_url_html = (
          f'<h2>Generated Images:</h2>'
          f'<h3>Setup</h3>'
          f'<img src="{setup_image.url}" style="max-width: 500px;"><br><br>'
          f'<h3>Punchline</h3>'
          f'<img src="{punchline_image.url}" style="max-width: 500px;"><br><br>'
        )
      except Exception as e:
        image_url_html = f'<p style="color:red;">Error: {str(e)}</p>'

  setup_reference_images_html = _render_reference_checkboxes(
    name="setup_reference_images",
    image_urls=available_reference_images,
    selected_urls=selected_setup_reference_images,
  )
  punchline_reference_images_html = _render_reference_checkboxes(
    name="punchline_reference_images",
    image_urls=available_reference_images,
    selected_urls=selected_punchline_reference_images,
  )
  setup_checkbox_attr = "checked" if include_setup_image_reference else ""

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
  <h1>Generate Pun Images</h1>
  {image_url_html}
  <form method="POST">
    <label>Setup Image Prompt:</label><br>
    <div style="display:flex; gap:16px; align-items:flex-start;">
      <textarea name="setup_image_prompt" rows="20" cols="120" required>{default_setup_prompt}</textarea>
      {setup_reference_images_html}
    </div><br><br>
    <label>Punchline Image Prompt:</label><br>
    <div style="display:flex; gap:16px; align-items:flex-start;">
      <textarea name="punchline_image_prompt" rows="20" cols="120" required>{default_punchline_prompt}</textarea>
      <div>
        {punchline_reference_images_html}
        <label style="display:block; margin-top:8px;">
          <input type="checkbox" name="include_setup_image" value="true" {setup_checkbox_attr}>
          Setup Image
        </label>
      </div>
    </div><br><br>
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
