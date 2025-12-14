"""Imagen service client."""

from __future__ import annotations

import base64
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Generic, Literal, TypeVar, override

from common import config, models
from firebase_functions import logger
from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from PIL import Image
from services import cloud_storage, firestore, image_editor

_T = TypeVar("_T")

# Lazily initialized clients by model name
_CLIENTS_BY_MODEL: dict[ImageModel, Any] = {}


class Error(Exception):
  """Base class for exceptions in this module."""


class ImageUpscaleTooLargeError(Error):
  """Exception raised when the upscaled image is too large."""


class ImageProvider(Enum):
  """Image providers."""

  IMAGEN = "imagen"
  OPENAI_IMAGES = "openai_images"
  OPENAI_RESPONSES = "openai_responses"
  GEMINI = "gemini"
  DUMMY_OUTPAINTER = "dummy_outpainter"


OPEN_AI_RESPONSES_CHAT_MODEL_NAME = "gpt-4.1-mini"

OTHER_TOKEN_COSTS = {
  "gpt-4.1-mini": {
    "input_tokens": 0.40 / 1_000_000,
    "output_tokens": 1.60 / 1_000_000,
  }
}


class ImageModel(Enum):
  """Image models."""

  def __init__(
    self,
    model_name: str,
    token_costs: dict[str, float],
    provider: ImageProvider,
    kwargs: dict[str, Any] | None = None,
    name_for_logging: str | None = None,
  ):
    self.model_name = model_name
    self.model_name_for_logging = name_for_logging or model_name
    self.token_costs = token_costs
    self.provider = provider
    self.kwargs = kwargs or {}

  # https://cloud.google.com/vertex-ai/generative-ai/pricing#imagen-models
  IMAGEN_4_0_ULTRA = (
    "imagen-4.0-ultra-generate-001",
    {
      "images": 0.06
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_4_0_STANDARD = (
    "imagen-4.0-generate-001",
    {
      "images": 0.04
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_4_0_FAST = (
    "imagen-4.0-fast-generate-001",
    {
      "images": 0.02
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_4_UPSCALE = (
    "imagen-4.0-upscale-preview",
    {
      "upscale_images": 0.06,
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_3_CAPABILITY = (
    "imagen-3.0-capability-001",
    {
      "images": 0.04,
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_1 = (
    "imagegeneration@002",
    {
      "upscale_images": 0.003,
      "images": 0.02
    },
    ImageProvider.IMAGEN,
  )

  # https://platform.openai.com/docs/models/gpt-image-1
  OPENAI_GPT_IMAGE_1_LOW = (
    "gpt-image-1",
    {
      "input_tokens": 10.00 / 1_000_000,
      "output_tokens": 40.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "low"
    },
  )
  OPENAI_GPT_IMAGE_1_MEDIUM = (
    "gpt-image-1",
    {
      "input_tokens": 10.00 / 1_000_000,
      "output_tokens": 40.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "medium"
    },
  )
  OPENAI_GPT_IMAGE_1_HIGH = (
    "gpt-image-1",
    {
      "input_tokens": 10.00 / 1_000_000,
      "output_tokens": 40.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "high"
    },
  )
  # https://platform.openai.com/docs/models/gpt-image-1-mini
  OPENAI_GPT_IMAGE_1_MINI_LOW = (
    "gpt-image-1-mini",
    {
      "input_tokens": 2.50 / 1_000_000,
      "output_tokens": 8.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "low"
    },
  )
  OPENAI_GPT_IMAGE_1_MINI_MEDIUM = (
    "gpt-image-1-mini",
    {
      "input_tokens": 2.50 / 1_000_000,
      "output_tokens": 8.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "medium"
    },
  )
  OPENAI_GPT_IMAGE_1_MINI_HIGH = (
    "gpt-image-1-mini",
    {
      "input_tokens": 2.50 / 1_000_000,
      "output_tokens": 8.00 / 1_000_000,
    },
    ImageProvider.OPENAI_IMAGES,
    {
      "quality": "high"
    },
  )

  # https://platform.openai.com/docs/pricing
  # https://platform.openai.com/docs/models/gpt-image-1
  OPENAI_RESPONSES_API_LOW = (
    "image_generation",
    {
      "images": 0.011,
    } | OTHER_TOKEN_COSTS[OPEN_AI_RESPONSES_CHAT_MODEL_NAME],
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "low"
    },
    "chatgpt_image_low",
  )
  OPENAI_RESPONSES_API_MEDIUM = (
    "image_generation",
    {
      "images": 0.042,
    } | OTHER_TOKEN_COSTS[OPEN_AI_RESPONSES_CHAT_MODEL_NAME],
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "medium"
    },
    "chatgpt_image_medium",
  )
  OPENAI_RESPONSES_API_HIGH = (
    "image_generation",
    {
      "images": 0.167,
    } | OTHER_TOKEN_COSTS[OPEN_AI_RESPONSES_CHAT_MODEL_NAME],
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "high"
    },
    "chatgpt_image_high",
  )

  # https://ai.google.dev/gemini-api/docs/image-generation#pricing
  # https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-image
  # https://ai.google.dev/gemini-api/docs/pricing
  GEMINI_NANO_BANANA = (
    "gemini-2.5-flash-image",
    {
      "input_tokens": 0.30 / 1_000_000,
      "output_text_tokens": 2.50 / 1_000_000,
      # $0.039 per image
      "output_image_tokens": 30.00 / 1_000_000,
    },
    ImageProvider.GEMINI,
    {
      "thinking": False,
      "vertexai": True,
    },
  )
  GEMINI_NANO_BANANA_PRO = (
    "gemini-3-pro-image-preview",
    {
      "input_tokens": 2.00 / 1_000_000,
      "output_text_tokens": 12.00 / 1_000_000,
      # $0.134 per image
      "output_image_tokens": 120.00 / 1_000_000,
    },
    ImageProvider.GEMINI,
    {
      "thinking": True,
      "vertexai": False,
    },
  )

  # Dummy outpainter that just adds black margins around the image
  DUMMY_OUTPAINTER = (
    "dummy_outpainter",
    {
      "images": 0.00,
    },
    ImageProvider.DUMMY_OUTPAINTER,
  )


def _get_upscaled_gcs_uri(gcs_uri: str, upscale_factor: str) -> str:
  """Constructs a GCS URI for the upscaled image."""
  base, ext = os.path.splitext(gcs_uri)
  return f"{base}_upscale_{upscale_factor}{ext}"


def get_client(
  label: str,
  model: ImageModel,
  file_name_base: str,
  **kwargs: Any,
) -> type[ImageClient]:
  """Get the appropriate image client for the given model."""
  match model.provider:
    case ImageProvider.IMAGEN:
      return ImagenClient(label=label,
                          model=model,
                          file_name_base=file_name_base,
                          **kwargs)
    case ImageProvider.OPENAI_IMAGES:
      return OpenAiImageClient(label=label,
                               model=model,
                               file_name_base=file_name_base,
                               **kwargs)
    case ImageProvider.OPENAI_RESPONSES:
      return OpenAiResponsesClient(label=label,
                                   model=model,
                                   file_name_base=file_name_base,
                                   **kwargs)
    case ImageProvider.GEMINI:
      return GeminiImageClient(label=label,
                               model=model,
                               file_name_base=file_name_base,
                               **kwargs)
    case ImageProvider.DUMMY_OUTPAINTER:
      return DummyOutpainterClient(label=label,
                                   model=model,
                                   file_name_base=file_name_base,
                                   **kwargs)
    case _:
      raise ValueError(f"Unknown image provider: {model.provider}")


@dataclass(kw_only=True)
class _ImageGenerationResult:
  """Result of an image generation."""
  image: Image.Image
  model_thought: str | None = None
  usage_dict: dict[str, int] = field(default_factory=dict)
  custom_temp_data: dict[str, Any] = field(default_factory=dict)


class ImageClient(ABC, Generic[_T]):
  """Abstract base class for image clients."""

  label: str
  model: ImageModel
  file_name_base: str
  extension: str

  def __init__(
    self,
    label: str,
    model: ImageModel,
    file_name_base: str,
    extension: str,
  ):
    self.label = label
    self.model = model
    self.file_name_base = file_name_base
    self.extension = extension

  @property
  def model_client(self) -> _T:
    """Get the model client."""
    if self.model not in _CLIENTS_BY_MODEL:
      _CLIENTS_BY_MODEL[self.model] = self._create_model_client()
    return _CLIENTS_BY_MODEL[self.model]

  def generate_image(
    self,
    prompt: str,
    reference_images: list[Any] | None = None,
    save_to_firestore: bool = True,
    user_uid: str | None = None,
    extra_log_data: dict[str, Any] | None = None,
    auto_enhance: bool = False,
  ) -> models.Image:
    """Generate an image from a prompt."""
    reference_images_str = "\n".join([f"{img}" for img in reference_images])
    logger.info(
      f"""Generating image with {self.__class__.__name__} ({self.model.model_name})
Prompt:
{prompt}

Reference images:
{reference_images_str}

Auto enhance: {auto_enhance}
User UID: {user_uid}
""")

    start_time = time.perf_counter()

    generation_result = self._generate_image_internal(
      prompt,
      reference_images,
      user_uid,
      extra_log_data,
    )

    output_gcs_uri = cloud_storage.get_image_gcs_uri(self.file_name_base,
                                                     self.extension)

    image = generation_result.image
    if auto_enhance:
      image = image_editor.ImageEditor().enhance_image(generation_result.image)

    # Upload image bytes to GCS
    logger.info(f"Uploading image to GCS: {output_gcs_uri}")
    image_bytes_io = BytesIO()
    image.save(image_bytes_io, format="PNG")
    image_bytes = image_bytes_io.getvalue()
    final_gcs_uri = cloud_storage.upload_bytes_to_gcs(
      image_bytes,
      output_gcs_uri,
      content_type="image/png",
    )

    image_model = models.Image(
      url=cloud_storage.get_final_image_url(final_gcs_uri),
      gcs_uri=final_gcs_uri,
      original_prompt=prompt,
      final_prompt=prompt,
      error=None,
      owner_user_id=user_uid,
      generation_metadata=models.GenerationMetadata(),
      model_thought=generation_result.model_thought,
      custom_temp_data=generation_result.custom_temp_data,
    )
    image_model.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=self.model.model_name_for_logging,
        token_costs=self.model.token_costs,
        usage_dict=generation_result.usage_dict,
        generation_time_sec=time.perf_counter() - start_time,
      ))

    if save_to_firestore:
      logger.info("Saving image to Firestore")
      image_model = firestore.create_image(image_model)

    return image_model

  def upscale_image_flexible(
    self,
    mime_type: Literal["image/png", "image/jpeg"],
    compression_quality: int | None,
    image: models.Image | None = None,
    gcs_uri: str | None = None,
    save_to_firestore: bool = True,
  ) -> models.Image:
    """Upscale an image at 4x, falling back to 2x if it fails."""
    try:
      return self.upscale_image(
        upscale_factor="x4",
        mime_type=mime_type,
        compression_quality=compression_quality,
        image=image,
        gcs_uri=gcs_uri,
        save_to_firestore=save_to_firestore,
      )
    except ImageUpscaleTooLargeError:
      logger.warn("Failed to upscale image at 4x, falling back to 2x")
      return self.upscale_image(
        upscale_factor="x2",
        mime_type=mime_type,
        compression_quality=compression_quality,
        image=image,
        gcs_uri=gcs_uri,
        save_to_firestore=save_to_firestore,
      )

  def upscale_image(
    self,
    upscale_factor: Literal["x2", "x4"],
    mime_type: Literal["image/png", "image/jpeg"],
    compression_quality: int | None,
    image: models.Image | None = None,
    gcs_uri: str | None = None,
    save_to_firestore: bool = True,
  ) -> models.Image:
    """Upscale an image."""
    logger.info(
      f"Upscaling image with {self.__class__.__name__} ({self.model.model_name})"
    )
    if not (image or gcs_uri) or (image and gcs_uri):
      raise ValueError("Exactly one of 'image' or 'gcs_uri' must be provided.")

    source_gcs_uri = image.gcs_uri if image else gcs_uri
    if not source_gcs_uri:
      raise ValueError("The provided image must have a gcs_uri.")

    start_time = time.perf_counter()
    upscaled_gcs_uri = self._upscale_image_internal(
      source_gcs_uri,
      upscale_factor=upscale_factor,
      mime_type=mime_type,
      compression_quality=compression_quality,
    )

    generation_metadata = _build_generation_metadata(
      label=self.label,
      model_name=self.model.model_name,
      usage_dict={"upscale_images": 1},
      token_costs=self.model.token_costs,
      generation_time_sec=time.perf_counter() - start_time,
    )

    # Calculate width based on upscale factor (assuming base width of 1024)
    width = 1024 * (2 if upscale_factor == "x2" else 4)
    url_upscaled = cloud_storage.get_final_image_url(
      upscaled_gcs_uri,
      width=width,
    )
    if image:
      image.gcs_uri_upscaled = upscaled_gcs_uri
      image.url_upscaled = url_upscaled
      if not image.generation_metadata:
        image.generation_metadata = models.GenerationMetadata()
      image.generation_metadata.add_generation(generation_metadata)
      if save_to_firestore:
        logger.info(f"Updating image {image.key} with upscaled version.")
        firestore.update_image(image)
      return image
    else:
      new_image = models.Image(
        gcs_uri=source_gcs_uri,
        url=cloud_storage.get_final_image_url(source_gcs_uri),
        gcs_uri_upscaled=upscaled_gcs_uri,
        url_upscaled=url_upscaled,
        generation_metadata=models.GenerationMetadata(),
      )
      new_image.generation_metadata.add_generation(generation_metadata)
      if save_to_firestore:
        logger.info("Creating new image with upscaled version.")
        firestore.create_image(new_image)
      return new_image

  def outpaint_image(
    self,
    top: int = 0,
    bottom: int = 0,
    left: int = 0,
    right: int = 0,
    prompt: str = "",
    image: models.Image | None = None,
    pil_image: Image.Image | None = None,
    gcs_uri: str | None = None,
    save_to_firestore: bool = True,
  ) -> models.Image:
    """Outpaint an image by expanding it in specified directions within the canvas.

    Args:
      top: Pixels to expand at the top edge.
      bottom: Pixels to expand at the bottom edge.
      left: Pixels to expand at the left edge.
      right: Pixels to expand at the right edge.
      prompt: Optional prompt describing what to generate in expanded areas.
      image: Image model to outpaint.
      pil_image: Alternative to image parameter - PIL Image to outpaint.
      gcs_uri: Alternative to image parameter - GCS URI of image to outpaint.
      save_to_firestore: Whether to save result to Firestore.

    Returns:
      A new Image model representing the outpainted image.
    """
    logger.info(
      f"Outpainting image with {self.__class__.__name__} ({self.model.model_name})"
    )
    if not (image or gcs_uri) or (image and gcs_uri):
      raise ValueError("Exactly one of 'image' or 'gcs_uri' must be provided.")

    if top <= 0 and bottom <= 0 and left <= 0 and right <= 0:
      raise ValueError(
        "At least one of 'top', 'bottom', 'left', or 'right' must be greater than 0."
      )

    source_gcs_uri = image.gcs_uri if image else gcs_uri
    if not source_gcs_uri:
      raise ValueError("The provided image must have a gcs_uri.")

    # Use provided PIL image if available, otherwise load from GCS
    if pil_image is None:
      image_bytes = cloud_storage.download_bytes_from_gcs(source_gcs_uri)
      pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
    else:
      # Ensure the PIL image is in RGB mode
      pil_image = pil_image.convert("RGB")

    # Construct output GCS URI
    gcs_uri_base, ext = os.path.splitext(source_gcs_uri)
    if not ext:
      ext = ".png"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    gcs_uri_base = f"{gcs_uri_base}_{timestamp}"
    output_gcs_uri = f"{gcs_uri_base}_outpaint{ext}"

    start_time = time.perf_counter()
    outpainted_gcs_uri, usage_dict = self._outpaint_image_internal(
      pil_image,
      output_gcs_uri,
      top=top,
      bottom=bottom,
      left=left,
      right=right,
      prompt=prompt,
    )

    generation_metadata = _build_generation_metadata(
      label=self.label,
      model_name=self.model.model_name,
      usage_dict=usage_dict,
      token_costs=self.model.token_costs,
      generation_time_sec=time.perf_counter() - start_time,
    )

    final_url = cloud_storage.get_final_image_url(outpainted_gcs_uri)

    base_prompt = prompt or (
      (image.final_prompt or image.original_prompt) if image else "")
    owner_user_id = image.owner_user_id if image else None

    new_image = models.Image(
      url=final_url,
      gcs_uri=outpainted_gcs_uri,
      original_prompt=base_prompt,
      final_prompt=base_prompt,
      error=None,
      owner_user_id=owner_user_id,
      generation_metadata=models.GenerationMetadata(),
    )
    new_image.generation_metadata.add_generation(generation_metadata)

    if save_to_firestore:
      logger.info("Creating new image with outpainted version.")
      firestore.create_image(new_image)

    return new_image

  @abstractmethod
  def _create_model_client(self) -> _T:
    """Create the model."""
    raise NotImplementedError

  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> _ImageGenerationResult:
    """Generate an image from a prompt.

    Args:
      prompt: The text prompt for the image.
      reference_images: A list of reference images. The format of the items
        in this list is specific to the client implementation.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      Image generation result.
    """
    raise NotImplementedError

  def _upscale_image_internal(
    self,
    gcs_uri: str,
    upscale_factor: Literal["x2", "x4"],
    mime_type: Literal["image/png", "image/jpeg"],
    compression_quality: int | None,
  ) -> str:
    """Upscale an image.

    Args:
      gcs_uri: The GCS URI of the image to upscale.
      upscale_factor: The upscale factor ("x2" or "x4").
      mime_type: The MIME type of the image.
      compression_quality: The compression quality of the image.

    Returns:
      The GCS URI of the upscaled image.
    """
    raise NotImplementedError

  def _outpaint_image_internal(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:
    """Outpaint an image.

    Args:
      input_image: The PIL Image to outpaint.
      output_gcs_uri: The GCS URI where the outpainted image should be saved.
      top: Pixels to expand at the top.
      bottom: Pixels to expand at the bottom.
      left: Pixels to expand at the left.
      right: Pixels to expand at the right.
      prompt: Prompt describing what to generate in expanded areas.

    Returns:
      A tuple of (gcs_uri, usage_dict) where:
        - gcs_uri: The GCS URI of the outpainted image.
        - usage_dict: Dictionary of token/usage counts (e.g., {"images": 1}).
    """
    raise NotImplementedError

  def _outpaint_image_using_generate_image(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:
    """Outpaint an image using generate_image.

    This implementation performs outpainting by:

    1. **Validating aspect ratio**:
       The requested `top`, `bottom`, `left`, and `right` margins must
       preserve the original image's aspect ratio. If the resulting canvas
       would have a different aspect ratio, a ValueError is raised.

    2. **Building a larger reference canvas**:
       A new canvas is created via `get_upscale_image_and_mask`, which
       places the original image in the middle and fills the requested
       margins with black. The mask output is ignored for Gemini; only
       the reference image is used.

    3. **Creating a zoomed-out reference image**:
       The larger reference canvas is downscaled back to the original
       image size. The resulting image looks like the original content
       shrunk into the center of a black frame, which Gemini uses as a
       reference.

    4. **Prompting Gemini to fill margins**:
       `generate_image` is called with the downscaled reference image
       and a prompt telling the model to produce an image identical to
       the reference, except that it should seamlessly extend the
       background into the black margins. Firestore saving and
       auto-enhancement are disabled for this intermediate image.

    5. **Upscaling to the final canvas size**:
       The generated image is downloaded and resized to the full
       outpainted canvas dimensions, then written to `output_gcs_uri`.

    The net effect is a "zoom-out" style outpaint: the original content
    remains visually consistent, while Gemini invents plausible content
    for the newly exposed margins around it.
    """
    # 1. Validate that requested margins maintain aspect ratio
    original_width, original_height = input_image.size

    # Calculate initial target dimensions
    target_width = original_width + left + right
    target_height = original_height + top + bottom

    original_aspect = original_width / original_height
    target_aspect = target_width / target_height

    # Tolerance for aspect ratio comparison
    if abs(target_aspect - original_aspect) > 1e-3:
      raise ValueError(
        f"Requested outpainting margins would change aspect ratio from "
        f"{original_aspect:.6f} to {target_aspect:.6f}. "
        f"Margins must preserve the original image aspect ratio.")

    # 2. Create ref_image (canvas)
    # We use the utility but ignore the mask as requested
    ref_image, _ = get_outpaint_image_and_mask(
      input_image,
      top=top,
      bottom=bottom,
      left=left,
      right=right,
    )

    # 3. Scale down to input size
    # This creates the input for Gemini which looks like the original image
    # but shrunk into the center of a black frame.
    # We use LANCZOS for high quality downscaling.
    ref_image_downscaled = ref_image.resize(
      input_image.size,
      Image.Resampling.LANCZOS,
    )

    # 4. Generate
    prompt = prompt if prompt else (
      """The reference image has black margins around an interior drawing on textured paper. Your task is to "outpaint" the interior drawing into the black margins. Generate a new image where the interior drawing is the same, and the black margin is replaced by a seamless extension of the interior drawing. The final image should NOT have any black margins."""
    )

    # We use the public generate_image to leverage existing logic,
    # but disable firestore saving and auto-enhance for this intermediate step.
    generated_image_model = self.generate_image(
      prompt=prompt,
      reference_images=[ref_image_downscaled],
      save_to_firestore=False,
      auto_enhance=False,
    )

    if not generated_image_model.gcs_uri:
      raise ValueError("Generated outpaint image has no GCS URI")

    # Extract usage dict from generation metadata
    # The generation metadata should have at least one generation with token_counts
    if not generated_image_model.generation_metadata or not generated_image_model.generation_metadata.generations:
      raise ValueError("Generated outpaint image has no generation metadata")

    # Get token counts from the most recent generation
    latest_generation = generated_image_model.generation_metadata.generations[
      -1]
    usage_dict = latest_generation.token_counts.copy()

    # 5. Scale result back to the full outpaint dimensions
    # Download the result
    generated_bytes = cloud_storage.download_bytes_from_gcs(
      generated_image_model.gcs_uri)
    generated_pil = Image.open(BytesIO(generated_bytes))

    # The generated image should be input_image.size (since we passed that as ref),
    # but Gemini might output something else. We force resize to the target canvas size.
    final_width, final_height = ref_image.size
    final_image = generated_pil.resize(
      (final_width, final_height),
      Image.Resampling.LANCZOS,
    )

    # Upload result
    final_bytes_io = BytesIO()
    final_image.save(final_bytes_io, format="PNG")
    final_bytes = final_bytes_io.getvalue()

    print(f"Uploading outpainted image to GCS: {output_gcs_uri}")
    cloud_storage.upload_bytes_to_gcs(
      final_bytes,
      output_gcs_uri,
      content_type="image/png",
    )

    return output_gcs_uri, usage_dict


class ImagenClient(ImageClient[genai.Client]):
  """Imagen client implementation."""

  def __init__(
    self,
    label: str,
    model: ImageModel,
    file_name_base: str,
    **kwargs: Any,
  ):
    super().__init__(
      label=label,
      model=model,
      file_name_base=file_name_base,
      extension="png",
      **kwargs,
    )

  @override
  def _create_model_client(self) -> genai.Client:
    return genai.Client(
      vertexai=True,
      project=config.PROJECT_ID,
      location=config.PROJECT_LOCATION,
    )

  @override
  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> _ImageGenerationResult:
    if reference_images:
      raise NotImplementedError("Reference images not supported for Imagen")

    response = self.model_client.models.generate_images(
      model=self.model.model_name,
      prompt=prompt,
      config=genai_types.GenerateImagesConfig(
        number_of_images=1,
        language=genai_types.ImagePromptLanguage.en,
        aspect_ratio="1:1",
        safety_filter_level=genai_types.SafetyFilterLevel.BLOCK_ONLY_HIGH,
        person_generation=genai_types.PersonGeneration.ALLOW_ADULT,
      ),
    )

    # There should only be one image, since we only asked for one
    response_image = response.generated_images[0].image
    image_bytes = response_image.image_bytes

    return _ImageGenerationResult(
      image=Image.open(BytesIO(image_bytes)),
      usage_dict={"images": 1},
    )

  @override
  def _upscale_image_internal(
    self,
    gcs_uri: str,
    upscale_factor: Literal["x2", "x4"],
    mime_type: Literal["image/png", "image/jpeg"],
    compression_quality: int | None,
  ) -> str:
    """Upscales an image using the Imagen model."""

    print(
      f"Upscaling image with Imagen ({self.model.model_name}): upscale_factor={upscale_factor}, mime_type={mime_type}, compression_quality={compression_quality}"
    )
    output_gcs_uri = _get_upscaled_gcs_uri(gcs_uri, upscale_factor)

    image_to_upscale = genai_types.Image.from_file(location=gcs_uri)
    response = self.model_client.models.upscale_image(
      model=self.model.model_name,
      image=image_to_upscale,
      upscale_factor=upscale_factor,
      config=genai_types.UpscaleImageConfig(
        output_gcs_uri=output_gcs_uri,
        output_mime_type=mime_type,
        output_compression_quality=compression_quality,
      ),
    )
    upscaled_image = response.generated_images[0].image

    if not upscaled_image:
      raise ValueError("No upscaled image returned from Imagen")

    final_gcs_uri = upscaled_image.gcs_uri
    if not final_gcs_uri:
      raise ValueError(
        f"No GCS URI returned for upscaled image (label={self.label})")

    return final_gcs_uri

  @override
  def _outpaint_image_internal(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:
    """Outpaint an image using Imagen."""
    # Clamp requested margins to sensible bounds (not strictly required, but safe).
    top = max(0, top)
    bottom = max(0, bottom)
    left = max(0, left)
    right = max(0, right)

    ref_image, mask_image = get_outpaint_image_and_mask(
      input_image,
      top=top,
      bottom=bottom,
      left=left,
      right=right,
    )

    # Construct GenAI image references fully in memory using bytes.
    ref_buffer = BytesIO()
    ref_image.save(ref_buffer, format="PNG")
    ref_bytes = ref_buffer.getvalue()

    raw_ref = genai_types.RawReferenceImage(
      reference_image=genai_types.Image(
        image_bytes=ref_bytes,
        mime_type="image/png",
      ),
      reference_id=0,
    )

    mask_buffer = BytesIO()
    mask_image.save(mask_buffer, format="PNG")
    outpaint_mask_bytes = mask_buffer.getvalue()

    mask_ref = genai_types.MaskReferenceImage(
      reference_id=1,
      reference_image=genai_types.Image(
        image_bytes=outpaint_mask_bytes,
        mime_type="image/png",
      ),
      config=genai_types.MaskReferenceConfig(
        mask_mode="MASK_MODE_USER_PROVIDED",
        mask_dilation=0.03,
      ),
    )

    print(
      f"Outpainting image with Google GenAI API ({self.model.model_name}) to {output_gcs_uri}"
    )
    response = self.model_client.models.edit_image(
      model=self.model.model_name,
      prompt=prompt or "",
      reference_images=[raw_ref, mask_ref],
      config=genai_types.EditImageConfig(
        edit_mode=genai_types.EditMode.EDIT_MODE_OUTPAINT,
        number_of_images=1,
        output_mime_type="image/png",
        output_gcs_uri=output_gcs_uri,
      ),
    )
    logger.info(f"Outpainting response: {response}")

    if not response.generated_images:
      raise ValueError("No outpainted image returned from Imagen 3")

    generated = response.generated_images[0]
    if not getattr(generated, "image", None) or not getattr(
        generated.image, "gcs_uri", None):
      raise ValueError(
        "No image gcs_uri returned from Imagen 3 outpaint operation")

    return generated.image.gcs_uri, {"images": 1}


class OpenAiImageClient(ImageClient[OpenAI]):
  """OpenAI client implementation for the Images API."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

  @override
  def _create_model_client(self) -> OpenAI:
    return OpenAI(api_key=config.get_openai_api_key())

  @override
  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> _ImageGenerationResult:

    quality = self.model.kwargs["quality"]
    common_args = {
      "model": self.model.model_name,
      "prompt": prompt,
      "output_format": "png",
      "quality": quality,
      "size": "1024x1024",
      "background": "opaque",
    }

    if reference_images:
      reference_image_bytes = []
      for i, img in enumerate(_get_reference_images(reference_images)):
        image_bytes = BytesIO()
        img.save(image_bytes, format="PNG")
        reference_image_bytes.append(
          (f"reference_image_{i}.png", image_bytes, "image/png"))

      print(
        f"Generating image with OpenAI ({self.model.model_name} - {quality}) with reference images"
      )
      result = self.model_client.images.edit(
        **common_args,
        image=reference_image_bytes,
      )

    else:
      print(
        f"Generating image with OpenAI ({self.model.model_name} - {quality})")
      result = self.model_client.images.generate(**common_args)

    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    return _ImageGenerationResult(
      image=Image.open(BytesIO(image_bytes)),
      usage_dict={
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
      },
    )

  @override
  def _outpaint_image_internal(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:
    return self._outpaint_image_using_generate_image(
      input_image,
      output_gcs_uri,
      top,
      bottom,
      left,
      right,
      prompt,
    )


class OpenAiResponsesClient(ImageClient[OpenAI]):
  """OpenAI client implementation for the Responses API."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

  @override
  def _create_model_client(self) -> OpenAI:
    return OpenAI(api_key=config.get_openai_api_key())

  @override
  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> _ImageGenerationResult:

    request_inputs = []
    quality = self.model.kwargs["quality"]

    # Reference images must be generation IDs from previous calls.
    if reference_images:
      for image_id in reference_images:
        if not isinstance(image_id, str):
          raise ValueError(
            f"OpenAI Responses reference image must be a string, got {type(image_id)}"
          )
        request_inputs.append({
          "type": "image_generation_call",
          "id": image_id,
        })
      print(
        f"Generating image with OpenAI Responses API ({self.model.model_name} - {quality}) with reference images"
      )
    else:
      print(
        f"Generating image with OpenAI Responses API ({self.model.model_name} - {quality})"
      )

    request_inputs.append({
      "role":
      "user",
      "content": [{
        "type":
        "input_text",
        "text":
        f"Generate a square image with 1:1 aspect ratio: {prompt}"
      }],
    })

    response = self.model_client.responses.create(
      model=OPEN_AI_RESPONSES_CHAT_MODEL_NAME,
      input=request_inputs,
      tools=[{
        "type": self.model.model_name,
        "output_format": "png",
        "quality": quality,
        "size": "1024x1024",
        "background": "opaque",
      }],
    )

    image_generation_calls = [
      output for output in response.output
      if output.type == "image_generation_call"
    ]

    if not image_generation_calls:
      raise ValueError("No image data returned from OpenAI")

    image_generation_call = image_generation_calls[0]
    image_base64 = image_generation_call.result
    image_bytes = base64.b64decode(image_base64)

    return _ImageGenerationResult(
      image=Image.open(BytesIO(image_bytes)),
      usage_dict={
        # Tokens for the chat
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        # Tokens for the image generation
        "images": 1,
      },
      custom_temp_data={
        "image_generation_call_id": image_generation_call.id,
      },
    )


class GeminiImageClient(ImageClient[genai.Client]):
  """Gemini client implementation using Google's GenAI API."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

  @override
  def _create_model_client(self) -> genai.Client:
    if self.model.kwargs["vertexai"]:
      return genai.Client(
        vertexai=True,
        project=config.PROJECT_ID,
        location=config.PROJECT_LOCATION,
      )
    else:
      return genai.Client(api_key=config.get_gemini_api_key())

  @override
  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> _ImageGenerationResult:

    contents = []

    for img in _get_reference_images(reference_images):
      contents.append(img)

    contents.append(prompt)

    thinking_enabled = self.model.kwargs["thinking"]
    thinking_config = genai_types.ThinkingConfig(
      include_thoughts=True,
      thinking_budget=2000,
    ) if thinking_enabled else None

    print(f"Generating image with Google GenAI API:\n{prompt}")
    response = self.model_client.models.generate_content(
      model=self.model.model_name,
      contents=contents,
      config=genai_types.GenerateContentConfig(
        image_config=genai_types.ImageConfig(
          aspect_ratio="1:1",
          image_size="2K",
        ),
        thinking_config=thinking_config,
      ),
    )
    print(f"Gemini response:\n{response}")

    image_bytes = None
    thought_lines = []
    for part in response.candidates[0].content.parts:
      if part.inline_data:
        image_bytes = part.inline_data.data
      elif part.text:
        thought_lines.append(part.text)
      elif part.thought:
        thought_lines.append(part.thought)

    if not image_bytes:
      raise ValueError("No image data returned from Gemini")

    usage_metadata = response.usage_metadata
    if usage_metadata:
      input_tokens = usage_metadata.prompt_token_count or 0
      output_text_tokens = usage_metadata.thoughts_token_count or 0
      output_image_tokens = sum(
        detail.token_count
        for detail in usage_metadata.candidates_tokens_details or []
        if detail.modality == genai_types.Modality.IMAGE)
      logger.info(
        f"Gemini image generation ({self.model.model_name}) usage metadata: {usage_metadata}"
      )
    else:
      # Set to defaults
      input_tokens = 1500
      output_text_tokens = 200
      output_image_tokens = 1120
      logger.error(
        f"Gemini image generation ({self.model.model_name}) usage metadata not found, using defaults: {input_tokens}, {output_text_tokens}, {output_image_tokens}"
      )

    return _ImageGenerationResult(
      image=Image.open(BytesIO(image_bytes)),
      model_thought="\n".join(thought_lines),
      usage_dict={
        "input_tokens": input_tokens,
        "output_text_tokens": output_text_tokens,
        "output_image_tokens": output_image_tokens,
      },
    )

  @override
  def _outpaint_image_internal(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:
    return self._outpaint_image_using_generate_image(
      input_image,
      output_gcs_uri,
      top,
      bottom,
      left,
      right,
      prompt,
    )


class DummyOutpainterClient(ImageClient[None]):
  """Dummy outpainter client that just adds black margins around the image."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

  @override
  def _create_model_client(self) -> None:
    return None

  @override
  def _outpaint_image_internal(
    self,
    input_image: Image.Image,
    output_gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> tuple[str, dict[str, int]]:

    ref_image, _ = get_outpaint_image_and_mask(
      input_image,
      top=top,
      bottom=bottom,
      left=left,
      right=right,
    )

    # Upload result
    final_bytes_io = BytesIO()
    ref_image.save(final_bytes_io, format="PNG")
    final_bytes = final_bytes_io.getvalue()

    print(f"Uploading outpainted image to GCS: {output_gcs_uri}")
    cloud_storage.upload_bytes_to_gcs(
      final_bytes,
      output_gcs_uri,
      content_type="image/png",
    )

    return output_gcs_uri, {"images": 1}


def _build_generation_metadata(
  label: str,
  model_name: str,
  usage_dict: dict[str, int],
  token_costs: dict[str, float],
  generation_time_sec: float,
) -> models.SingleGenerationMetadata:
  """Build the metadata for the image generation."""

  for token_type in usage_dict:
    if token_type not in token_costs:
      raise ValueError(
        f"Unknown token type: {token_type} for model {model_name}: {usage_dict}"
      )

  cost = sum(token_costs[token_type] * count
             for token_type, count in usage_dict.items())

  return models.SingleGenerationMetadata(
    label=label,
    model_name=model_name,
    token_counts=usage_dict,
    generation_time_sec=generation_time_sec,
    cost=cost,
    retry_count=0,
  )


def _get_reference_images(
    reference_images: list[Any] | None) -> list[Image.Image]:
  """Get the reference images from the list of images or GCS URIs."""
  images: list[Image.Image] = []
  if not reference_images:
    return images

  for image_data in reference_images:
    if isinstance(image_data, bytes):
      img = Image.open(BytesIO(image_data))
    elif isinstance(image_data, Image.Image):
      img = image_data
    elif isinstance(image_data, str):
      img = cloud_storage.download_image_from_gcs(image_data)
    elif isinstance(image_data, models.Image):
      img = cloud_storage.download_image_from_gcs(image_data.gcs_uri)
    else:
      raise ValueError(f"Invalid reference image type: {type(image_data)}")
    images.append(img)

  return images


@dataclass(frozen=True)
class UpscaleDimensions:
  """Container for canvas and paste coordinates for outpainting/upscaling."""

  new_canvas_width: int
  """Width of the new canvas in pixels."""
  new_canvas_height: int
  """Height of the new canvas in pixels."""
  image_x: int
  """X coordinate of the original image on the new canvas."""
  image_y: int
  """Y coordinate of the original image on the new canvas."""
  mask_width: int
  """Width of the mask in pixels."""
  mask_height: int
  """Height of the mask in pixels."""
  mask_x: int
  """X coordinate of the mask on the new canvas."""
  mask_y: int
  """Y coordinate of the mask on the new canvas."""


UPSCALE_MARGIN_FRACTION = 0.01
"""Fraction of the original dimension used as margin for outpainting/upscaling."""


def get_upscale_dimensions(
  original_width: int,
  original_height: int,
  top: int,
  bottom: int,
  left: int,
  right: int,
) -> UpscaleDimensions:
  """Compute canvas size and paste coordinates for outpainting/upscaling.

  Args:
    original_width: Width of the original image in pixels.
    original_height: Height of the original image in pixels.
    top: Pixels to expand at the top.
    bottom: Pixels to expand at the bottom.
    left: Pixels to expand at the left.
    right: Pixels to expand at the right.

  Returns:
    An UpscaleDimensions instance describing the canvas and paste positions.
  """
  new_canvas_width = original_width + left + right
  new_canvas_height = original_height + top + bottom

  # The original image is placed insight any left/top expansions.
  image_x = left
  image_y = top

  # Add a ~1% margin on the outpainting sides so transitions can be redrawn.
  margin_left = int(round(original_width *
                          UPSCALE_MARGIN_FRACTION)) if left > 0 else 0
  margin_right = int(round(original_width *
                           UPSCALE_MARGIN_FRACTION)) if right > 0 else 0
  margin_top = int(round(original_height *
                         UPSCALE_MARGIN_FRACTION)) if top > 0 else 0
  margin_bottom = int(round(original_height *
                            UPSCALE_MARGIN_FRACTION)) if bottom > 0 else 0

  mask_width = max(1, original_width - margin_left - margin_right)
  mask_height = max(1, original_height - margin_top - margin_bottom)

  mask_x = left + margin_left
  mask_y = top + margin_top

  return UpscaleDimensions(
    new_canvas_width=new_canvas_width,
    new_canvas_height=new_canvas_height,
    image_x=image_x,
    image_y=image_y,
    mask_x=mask_x,
    mask_y=mask_y,
    mask_width=mask_width,
    mask_height=mask_height,
  )


def get_outpaint_image_and_mask(
  original_image: Image.Image,
  top: int,
  bottom: int,
  left: int,
  right: int,
) -> tuple[Image.Image, Image.Image]:
  """Create the reference and mask images for outpainting.

  Args:
    original_image: Original image to be placed on the canvas.
    top: Pixels to expand at the top.
    bottom: Pixels to expand at the bottom.
    left: Pixels to expand at the left.
    right: Pixels to expand at the right.

  Returns:
    A tuple of (reference_image, mask_image).
  """
  original_width, original_height = original_image.size
  dims = get_upscale_dimensions(
    original_width=original_width,
    original_height=original_height,
    top=top,
    bottom=bottom,
    left=left,
    right=right,
  )

  # Build reference image: original content pasted into a larger canvas.
  ref_image = Image.new(
    "RGB",
    (dims.new_canvas_width, dims.new_canvas_height),
    color="black",
  )
  ref_image.paste(original_image, (dims.image_x, dims.image_y))

  # Build mask image: black where original content exists, white elsewhere.
  mask_image = Image.new(
    "RGB",
    (dims.new_canvas_width, dims.new_canvas_height),
    color="white",
  )
  black_patch = Image.new(
    "RGB",
    (dims.mask_width, dims.mask_height),
    color="black",
  )
  mask_image.paste(black_patch, (dims.mask_x, dims.mask_y))

  return ref_image, mask_image
