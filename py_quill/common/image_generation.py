"""Library for generating images."""

import logging
from typing import Any

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
    label="pun_agent_image_tool_low",
    model=image_client.ImageModel.OPENAI_RESPONSES_API_LOW,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "medium":
  image_client.get_client(
    label="pun_agent_image_tool_medium",
    model=image_client.ImageModel.OPENAI_RESPONSES_API_MEDIUM,
    file_name_base=_IMAGE_FILE_NAME_BASE,
  ),
  "high":
  image_client.get_client(
    label="pun_agent_image_tool_high",
    model=image_client.ImageModel.OPENAI_RESPONSES_API_HIGH,
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
_IMAGE_GENERATION_PROMPT_PREAMBLE = "A whimsical and silly sketch, appearing as if drawn with colored pencils on lightly textured paper to create a naive charm. The artwork is unbearably cute, with soft, sketchy lines and a vibrant, gentle, but bright color palette where colors sometimes stray playfully outside the lines."

_IMAGE_GENERATION_WITH_REFERENCE_PROMPT_POSTAMBLE = "Generate another image using the same artistic style, color palette, background texture, and overall aesthetic as the reference images. Make sure the characters, objects, fonts, color palette, etc. are consistent."

_IMAGE_MODIFICATION_PROMPT_POSTAMBLE = "Make sure to the exact same artistic style, color palette, background texture, and overall aesthetic as the original image. Make sure the characters, objects, fonts, color palette, etc. are consistent."


def generate_pun_images(
  pun_data: list[tuple[str, str]],
  image_quality: str,
) -> list[models.Image]:
  """Generate images for a list of pun lines.
  
  Args:
    pun_data: List of tuples containing (pun_text, image_description)
    image_quality: The quality of the image to generate.

  Returns:
    List of generated Image objects
  """
  images: list[models.Image | None] = []
  previous_image_references: list[Any] = []

  for i, (pun_text, image_description) in enumerate(pun_data):
    # try:
    image = generate_pun_image(
      pun_text=pun_text,
      image_description=image_description,
      image_quality=image_quality,
      reference_images=previous_image_references,
    )

    if not image.url:
      logging.warning(
        f"Generated pun image for pun line {i} has no URL: {image}")
      images.append(None)
      continue

    if prev_id := image.custom_temp_data.get("image_generation_call_id"):
      previous_image_references.append(prev_id)
    elif image.gcs_uri:
      previous_image_references.append(image.gcs_uri)

    images.append(image)

  # except Exception as e:
  #   stack_trace = traceback.format_exc()
  #   logging.warning(
  #     f"Failed to generate image for pun line {i}: {pun_text}\n{e}\n{stack_trace}"
  #   )
  #   images.append(None)

  return images


def generate_pun_image(
  pun_text: str | None,
  image_description: str,
  image_quality: str,
  reference_images: list[Any] | None = None,
  image_client_override: image_client.ImageClient | None = None,
) -> models.Image:
  """Generate a pun image.
  Args:
    pun_text: The full text of the pun to display on the image. If None, the image will be generated without the pun text.
    image_description: Detailed description of all aspects of the image. This should include the full text of the pun (again), the style/font/color/position/etc. of the pun text, as well as the image's subject(s), foreground, background, color palette, artistic style, and all other details needed to render an accurate image.
    reference_images: Data about reference images. Format depends on the image provider.
    image_quality: The quality of the image to generate.
      - "low": Low quality, fast generation.
      - "medium": Medium quality, medium speed generation.
      - "high": High quality, slow generation.
    image_client: The image client to use to generate the image. If not provided, a client will be selected based on the image quality.
  Returns:
    The generated image.
  """

  if reference_images:
    prompt_preamble = _IMAGE_GENERATION_WITH_REFERENCE_PROMPT_POSTAMBLE
  else:
    prompt_preamble = _IMAGE_GENERATION_PROMPT_PREAMBLE

  if pun_text:
    prompt_postamble = f'The phrase "{pun_text}" is prominently displayed in a casual, whimsical hand-written script, resembling a silly pencil sketch.'
  else:
    prompt_postamble = ''

  image_description = _strip_prompt_preamble(image_description,
                                             prompt_preamble, prompt_postamble)

  prompt = f"{prompt_preamble} {image_description} {prompt_postamble}"

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
    reference_images,
    save_to_firestore=False,
  )
  image.original_prompt = image_description
  image.final_prompt = prompt

  if not image or not image.url:
    raise ValueError(
      f"Failed to generate image for pun: {pun_text if pun_text else 'no pun text'}"
    )

  return image


def _strip_prompt_preamble(
  image_description: str,
  prompt_preamble: str,
  prompt_postamble: str,
) -> str:
  """Strip the prompt preamble and postamble from the image description."""

  image_description = image_description.strip()

  if prompt_preamble:
    while image_description.startswith(prompt_preamble):
      image_description = image_description[len(prompt_preamble):].strip()

  if prompt_postamble:
    while image_description.endswith(prompt_postamble):
      image_description = image_description[:-len(prompt_postamble)].strip()

  return image_description


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
