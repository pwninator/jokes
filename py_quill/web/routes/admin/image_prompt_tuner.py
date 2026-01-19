"""Admin route for tuning image prompts."""

from __future__ import annotations

import flask

from agents import constants
from common import image_generation, utils
from functions import auth_helpers
from functions.function_utils import get_param
from web.routes import web_bp

_PROMPT_PREAMBLE = image_generation._IMAGE_GENERATION_PROMPT_PREAMBLE.strip()


def _build_prompt_templates() -> tuple[str, str]:
  style_guidance = image_generation._STYLE_REFERENCE_GUIDANCE.format(
    num_style_refs=len(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS))
  setup_prompt = (
    f"{_PROMPT_PREAMBLE}\n\n"
    f"{style_guidance}\n\n"
    "SETUP_IMAGE_DESCRIPTION_HERE")
  punchline_prompt = (
    f"{_PROMPT_PREAMBLE}\n\n"
    f"{image_generation._PRIOR_PANEL_GUIDANCE}\n\n"
    "PUNCHLINE_IMAGE_DESCRIPTION_HERE")
  return setup_prompt, punchline_prompt


def _select_image_client(image_quality: str):
  if utils.is_emulator():
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY["low"]
  if image_quality in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY[image_quality]
  raise ValueError(f"Invalid image quality: {image_quality}")


def _get_list_param(req: flask.Request, param_name: str) -> list[str]:
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


def _is_checkbox_checked(
  req: flask.Request,
  param_name: str,
  default: bool = False,
) -> bool:
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


def _build_quality_options(selected_quality: str) -> list[dict[str, str]]:
  return [{
    "value": key,
    "selected": "selected" if key == selected_quality else "",
  } for key in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys()]


@web_bp.route('/admin/image-prompt-tuner', methods=['GET', 'POST'])
@auth_helpers.require_admin
def admin_image_prompt_tuner():
  """Render and submit the image prompt tuner."""
  setup_template, punchline_template = _build_prompt_templates()
  available_reference_images = constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS

  setup_prompt = setup_template
  punchline_prompt = punchline_template
  selected_quality = "medium_mini"
  selected_setup_reference_images = available_reference_images[:]
  selected_punchline_reference_images: list[str] = []
  include_setup_image_reference = True
  setup_image_url = None
  punchline_image_url = None
  error_message = None

  if flask.request.method == 'POST':
    setup_prompt = get_param(flask.request, 'setup_image_prompt') or ""
    punchline_prompt = get_param(flask.request, 'punchline_image_prompt') or ""
    selected_quality = get_param(flask.request, 'image_quality',
                                 'medium_mini') or "medium_mini"

    selected_setup_reference_images = _filter_reference_images(
      _get_list_param(flask.request, 'setup_reference_images'),
      available_reference_images,
    )
    selected_punchline_reference_images = _filter_reference_images(
      _get_list_param(flask.request, 'punchline_reference_images'),
      available_reference_images,
    )
    include_setup_image_reference = _is_checkbox_checked(
      flask.request,
      'include_setup_image',
      default=False,
    )

    setup_prompt_clean = setup_prompt.strip()
    punchline_prompt_clean = punchline_prompt.strip()

    if setup_prompt_clean and punchline_prompt_clean:
      try:
        client = _select_image_client(selected_quality)
        setup_image = client.generate_image(
          setup_prompt_clean,
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
          punchline_prompt_clean,
          punchline_reference_images or None,
          save_to_firestore=False,
        )
        if not punchline_image or not punchline_image.url:
          raise ValueError(
            f"Generated punchline image has no URL: {punchline_image}")

        setup_image_url = setup_image.url
        punchline_image_url = punchline_image.url
      except Exception as exc:
        error_message = str(exc)

  return flask.render_template(
    'admin/image_prompt_tuner.html',
    site_name='Snickerdoodle',
    setup_prompt=setup_prompt,
    punchline_prompt=punchline_prompt,
    setup_image_url=setup_image_url,
    punchline_image_url=punchline_image_url,
    error_message=error_message,
    reference_images=available_reference_images,
    selected_setup_reference_images=selected_setup_reference_images,
    selected_punchline_reference_images=selected_punchline_reference_images,
    include_setup_image_reference=include_setup_image_reference,
    quality_options=_build_quality_options(selected_quality),
  )
