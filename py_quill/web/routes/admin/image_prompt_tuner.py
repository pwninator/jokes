"""Admin route for tuning image prompts."""

from __future__ import annotations

import flask
from agents import constants
from common import image_generation
from functions import auth_helpers, joke_creation_fns
from web.routes import web_bp

_PROMPT_PREAMBLE = image_generation._IMAGE_GENERATION_PROMPT_PREAMBLE.strip()


def _build_prompt_templates() -> tuple[str, str]:
  style_guidance = image_generation._STYLE_REFERENCE_GUIDANCE.format(
    num_style_refs=len(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS))
  setup_prompt = (f"{_PROMPT_PREAMBLE}\n\n"
                  f"{style_guidance}\n\n"
                  "SETUP_IMAGE_DESCRIPTION_HERE")
  punchline_prompt = (f"{_PROMPT_PREAMBLE}\n\n"
                      f"{image_generation._PRIOR_PANEL_GUIDANCE}\n\n"
                      "PUNCHLINE_IMAGE_DESCRIPTION_HERE")
  return setup_prompt, punchline_prompt


def _build_quality_options(selected_quality: str) -> list[dict[str, str]]:
  return [{
    "value": key,
    "selected": "selected" if key == selected_quality else "",
  } for key in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys()]


@web_bp.route('/admin/image-prompt-tuner', methods=['GET'])
@auth_helpers.require_admin
def admin_image_prompt_tuner():
  """Render the image prompt tuner (generation happens client-side)."""
  setup_template, punchline_template = _build_prompt_templates()
  available_reference_images = constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS

  return flask.render_template(
    'admin/image_prompt_tuner.html',
    site_name='Snickerdoodle',
    joke_image_op=joke_creation_fns.JokeCreationOp.JOKE_IMAGE.value,
    setup_prompt=setup_template,
    punchline_prompt=punchline_template,
    error_message=None,
    reference_images=available_reference_images,
    selected_setup_reference_images=available_reference_images[:],
    selected_punchline_reference_images=[],
    include_setup_image_reference=True,
    quality_options=_build_quality_options("medium_mini"),
  )
