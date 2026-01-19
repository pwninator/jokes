"""Admin route for tuning image prompts."""

from __future__ import annotations

import flask

from agents import constants
from common import image_generation
from functions import auth_helpers, joke_creation_fns
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
      response = joke_creation_fns.joke_creation_process(flask.request)
      payload = None
      try:
        payload = response.get_json()
      except Exception:  # pylint: disable=broad-except
        payload = None

      data = payload.get("data", {}) if isinstance(payload, dict) else {}
      if response.status_code == 200:
        setup_image_url = data.get("setup_image_url")
        punchline_image_url = data.get("punchline_image_url")
      else:
        error_message = data.get("error") or "Image generation failed"

  return flask.render_template(
    'admin/image_prompt_tuner.html',
    site_name='Snickerdoodle',
    joke_image_op=joke_creation_fns.JokeCreationOp.JOKE_IMAGE.value,
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
