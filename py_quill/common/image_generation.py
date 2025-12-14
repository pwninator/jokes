"""Library for generating images."""

from typing import Any

from agents import constants
from common import models, utils
from services import cloud_storage, image_client

_IMAGE_FILE_NAME_BASE = "pun_agent_image"

PUN_IMAGE_CLIENTS_BY_QUALITY = {
  "low_mini":
  image_client.get_client(
    label="pun_agent_image_tool_low_mini",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_LOW,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "medium_mini":
  image_client.get_client(
    label="pun_agent_image_tool_medium_mini",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_MEDIUM,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "high_mini":
  image_client.get_client(
    label="pun_agent_image_tool_high_mini",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_HIGH,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "low":
  image_client.get_client(
    label="pun_agent_image_tool_medium_mini",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_MINI_MEDIUM,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "medium":
  image_client.get_client(
    label="pun_agent_image_tool_medium",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_MEDIUM,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "high":
  image_client.get_client(
    label="pun_agent_image_tool_high",
    model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_HIGH,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "gemini":
  image_client.get_client(
    label="pun_agent_image_tool_gemini",
    model=image_client.ImageModel.GEMINI_NANO_BANANA,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
}

_MODIFY_IMAGE_CLIENT_LOW = image_client.get_client(
  label="pun_agent_image_tool_gemini_low",
  model=image_client.ImageModel.GEMINI_NANO_BANANA,
  file_name_base=_IMAGE_FILE_NAME_BASE,
)

_MODIFY_IMAGE_CLIENT_HIGH = image_client.get_client(
  label="pun_agent_image_tool_gemini_high",
  model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
  file_name_base=_IMAGE_FILE_NAME_BASE,
)

# Image prompt constants
_IMAGE_GENERATION_PROMPT_PREAMBLE = (
  "Create an unbearably cute, professional-quality children's illustration in soft colored pencil on lightly textured paper. "
  "Use organic, sketch-like outlines in darker saturated shades of the subject colors (avoid heavy black ink), with visible directional strokes and tight cross-hatching to build rich, vibrant color. "
  "Keep the palette bright, gentle, and harmonious. "
  # "Backgrounds should be fully rendered (not blank or vignette). "
  "Backgrounds should be simple, low contrast, and low detail, with loose sketch-like shading, to allow the main subject to stand out. "
  "Leave a safe margin around all edges so no important text or main content is near or crossing the edge; keep all text and focal elements comfortably inside the frame. "
  "Subjects should be chibi/cute (big heads, large expressive eyes with highlights, small bodies), tactile and hand-crafted yet polished for print."
)

_STYLE_REFERENCE_GUIDANCE = (
  "You are given {num_style_refs} style reference images to help you visualize the desired art style described above. Use them to match the artistic style, color palette, background texture, and overall aesthetic."
)

_PRIOR_PANEL_GUIDANCE = (
  "You are given 1 prior panel image (the setup panel). Create the punchline panel to complete the two-panel joke. "
  "Use the exact same art style as the setup panel. Keep characters, props, fonts, colors, proportions, outfits, camera angle, and environment consistent with the setup panel. "
  "Do not alter or obscure any text already present in the setup panel. Generate the new punchline content while preserving all visual continuity."
)

_IMAGE_MODIFICATION_PROMPT_POSTAMBLE = "Make sure to the exact same artistic style, color palette, background texture, and overall aesthetic as the original image. Make sure the characters, objects, fonts, color palette, etc. are consistent."


def generate_pun_images(
  *,
  setup_text: str,
  setup_image_description: str,
  punchline_text: str,
  punchline_image_description: str,
  image_quality: str,
) -> tuple[models.Image, models.Image]:
  """Generate setup and punchline images for a two-panel pun.
  
  Args:
    setup_text: Text for the setup panel.
    setup_image_description: Detailed description for the setup panel image.
    punchline_text: Text for the punchline panel.
    punchline_image_description: Detailed description for the punchline panel image.
    image_quality: Desired image quality preset.

  Returns:
    A tuple of two Image objects (setup first, then punchline).
  """

  # Panel 1 (setup) uses style references.
  setup_image = generate_pun_image(
    pun_text=setup_text,
    image_description=setup_image_description,
    image_quality=image_quality,
    style_reference_images=constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
  )

  if not setup_image.url:
    raise ValueError(f"Generated setup image has no URL: {setup_image}")

  previous_image_reference: Any | None = None
  if setup_image.custom_temp_data.get("image_generation_call_id"):
    previous_image_reference = setup_image.custom_temp_data[
      "image_generation_call_id"]
  elif setup_image.gcs_uri:
    previous_image_reference = setup_image.gcs_uri

  # Panel 2 (punchline) uses only the prior setup panel for continuity.
  punchline_image = generate_pun_image(
    pun_text=punchline_text,
    image_description=punchline_image_description,
    image_quality=image_quality,
    previous_image=previous_image_reference,
  )

  if not punchline_image.url:
    raise ValueError(
      f"Generated punchline image has no URL: {punchline_image}")

  return (setup_image, punchline_image)


def generate_pun_image(
  pun_text: str | None,
  image_description: str,
  image_quality: str,
  *,
  previous_image: Any | None = None,
  style_reference_images: list[Any] | None = None,
  image_client_override: image_client.ImageClient | None = None,
) -> models.Image:
  """Generate a pun image.
  Args:
    pun_text: The full text of the pun to display on the image. If None, the image will be generated without the pun text.
    image_description: Detailed description of all aspects of the image. This should include the full text of the pun (again), the style/font/color/position/etc. of the pun text, as well as the image's subject(s), foreground, background, color palette, artistic style, and all other details needed to render an accurate image.
    previous_image: The setup/prior panel image for continuity. Must not be combined with style_reference_images.
    style_reference_images: Style reference images to anchor the art style. Must not be combined with previous_image.
    image_quality: The quality of the image to generate.
      - "low": Low quality, fast generation.
      - "medium": Medium quality, medium speed generation.
      - "high": High quality, slow generation.
    image_client: The image client to use to generate the image. If not provided, a client will be selected based on the image quality.
  Returns:
    The generated image.
  """

  if previous_image and style_reference_images:
    raise ValueError(
      "previous_image and style_reference_images cannot be used together")

  prompt_parts: list[str] = [_IMAGE_GENERATION_PROMPT_PREAMBLE]
  all_reference_images: list[Any] = []

  if style_reference_images:
    prompt_parts.append(
      _STYLE_REFERENCE_GUIDANCE.format(
        num_style_refs=len(style_reference_images)))
    all_reference_images.extend(style_reference_images)

  if previous_image:
    prompt_parts.append(_PRIOR_PANEL_GUIDANCE)
    all_reference_images.append(previous_image)

  image_description = image_description.strip()
  prompt_parts.append(image_description)

  if pun_text:
    prompt_parts.append(
      f'The phrase "{pun_text}" is prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch.'
    )

  prompt = " ".join(prompt_parts)

  if image_client_override:
    client = image_client_override
  else:
    if utils.is_emulator():
      client = PUN_IMAGE_CLIENTS_BY_QUALITY["low"]
    elif image_quality in PUN_IMAGE_CLIENTS_BY_QUALITY:
      client = PUN_IMAGE_CLIENTS_BY_QUALITY[image_quality]
    else:
      raise ValueError(f"Invalid image quality: {image_quality}")

  image = client.generate_image(
    prompt,
    all_reference_images if all_reference_images else None,
    save_to_firestore=False,
  )
  image.original_prompt = image_description
  image.final_prompt = prompt

  if not image or not image.url:
    raise ValueError(
      f"Failed to generate image for pun: {pun_text if pun_text else 'no pun text'}"
    )

  return image


def modify_image(
  image: models.Image,
  instruction: str,
  client: image_client.ImageClient = _MODIFY_IMAGE_CLIENT_HIGH,
) -> models.Image:
  """Modify an image using an instruction.
  Args:
    image: The image to modify.
    instruction: The instruction for how to modify the image.
    client: The image client to use to modify the image.
  Returns:
    The modified image.
  """
  if not image.gcs_uri:
    raise ValueError("Image must have a GCS URI to be modified.")

  reference_image_bytes = cloud_storage.download_bytes_from_gcs(image.gcs_uri)

  prompt = f"{instruction} {_IMAGE_MODIFICATION_PROMPT_POSTAMBLE}"
  new_image = client.generate_image(
    prompt,
    reference_images=[reference_image_bytes],
    save_to_firestore=False,
  )
  new_image.original_prompt = instruction
  new_image.final_prompt = instruction

  if not new_image or not new_image.url:
    raise ValueError(
      f"Failed to generate image for instruction: {instruction}")

  return new_image
