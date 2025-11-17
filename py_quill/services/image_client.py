"""Imagen service client."""

from __future__ import annotations

import base64
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
from services import cloud_storage, firestore

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


class ImageModel(Enum):
  """Image models."""

  def __init__(
    self,
    model_name: str,
    token_costs: dict[str, float],
    provider: ImageProvider,
    kwargs: dict[str, Any] | None = None,
  ):
    self.model_name = model_name
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
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "low"
    },
  )
  OPENAI_RESPONSES_API_MEDIUM = (
    "image_generation",
    {
      "images": 0.042,
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "medium"
    },
  )
  OPENAI_RESPONSES_API_HIGH = (
    "image_generation",
    {
      "images": 0.167,
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "high"
    },
  )

  # https://ai.google.dev/gemini-api/docs/image-generation#pricing
  # https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-image
  GEMINI_NANO_BANANA = (
    "gemini-2.5-flash-image",
    {
      "images": 0.0387,  # 1290 tokens * $30 / 1M tokens
    },
    ImageProvider.GEMINI,
  )


OTHER_TOKEN_COSTS = {
  "gpt-4.1-mini": {
    "input_tokens": 0.40 / 1_000_000,
    "output_tokens": 1.60 / 1_000_000,
  }
}


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
    case _:
      raise ValueError(f"Unknown image provider: {model.provider}")


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
  ) -> models.Image:
    """Generate an image from a prompt."""
    logger.info(
      f"Generating image with {self.__class__.__name__} ({self.model.model_name})"
    )
    image = self._generate_image_internal(
      prompt,
      reference_images,
      user_uid,
      extra_log_data,
    )

    if not image.is_success:
      raise ValueError(f"Image generation failed: {image}")

    if save_to_firestore:
      logger.info("Saving image to Firestore")
      image = firestore.create_image(image)

    return image

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

    start_time = time.perf_counter()
    outpainted_gcs_uri = self._outpaint_image_internal(
      source_gcs_uri,
      top=top,
      bottom=bottom,
      left=left,
      right=right,
      prompt=prompt,
    )

    generation_metadata = _build_generation_metadata(
      label=self.label,
      model_name=self.model.model_name,
      usage_dict={"images": 1},
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

  @abstractmethod
  def _generate_image_internal(
    self,
    prompt: str,
    reference_images: list[Any] | None,
    user_uid: str | None,
    extra_log_data: dict[str, Any] | None,
  ) -> models.Image:
    """Generate an image from a prompt.

    Args:
      prompt: The text prompt for the image.
      reference_images: A list of reference images. The format of the items
        in this list is specific to the client implementation.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      The generated image.
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
    gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> str:
    """Outpaint an image.

    Args:
      gcs_uri: The GCS URI of the image to outpaint.
      top: Pixels to expand at the top.
      bottom: Pixels to expand at the bottom.
      left: Pixels to expand at the left.
      right: Pixels to expand at the right.
      prompt: Prompt describing what to generate in expanded areas.

    Returns:
      The GCS URI of the outpainted image.
    """
    raise NotImplementedError


class ImagenClient(ImageClient[genai.Client]):
  """Imagen client implementation."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

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
  ) -> models.Image:
    """Generates an image using the Imagen model.

    Args:
      prompt: The text prompt for the image.
      reference_images: Not supported for this client.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      The generated image.
    """
    if reference_images:
      raise NotImplementedError("Reference images not supported for Imagen")

    start_time = time.perf_counter()
    output_gcs_uri = cloud_storage.get_image_gcs_uri(self.file_name_base,
                                                     self.extension)

    response = self.model_client.models.generate_images(
      model=self.model.model_name,
      prompt=prompt,
      config=genai_types.GenerateImagesConfig(
        number_of_images=1,
        language=genai_types.ImagePromptLanguage.en,
        aspect_ratio="1:1",
        output_gcs_uri=output_gcs_uri,
        safety_filter_level=genai_types.SafetyFilterLevel.BLOCK_ONLY_HIGH,
        person_generation=genai_types.PersonGeneration.ALLOW_ADULT,
      ),
    )

    # There should only be one image, since we only asked for one
    image = response.generated_images[0].image

    final_gcs_uri = image.gcs_uri
    if not final_gcs_uri:
      raise ValueError(f"No GCS URI returned for image (label={self.label})")

    image_model = models.Image(
      url=cloud_storage.get_final_image_url(final_gcs_uri),
      gcs_uri=final_gcs_uri,
      original_prompt=prompt,
      final_prompt=prompt,
      error=None,
      owner_user_id=user_uid,
      generation_metadata=models.GenerationMetadata(),
    )
    image_model.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=self.model.model_name,
        usage_dict={
          "images": 1,
        },
        token_costs=self.model.token_costs,
        generation_time_sec=time.perf_counter() - start_time,
      ))

    return image_model

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
    gcs_uri: str,
    top: int,
    bottom: int,
    left: int,
    right: int,
    prompt: str,
  ) -> str:
    """Outpaint an image using Imagen 3 via the GenAI SDK."""
    # Clamp requested margins to sensible bounds (not strictly required, but safe).
    top = max(0, top)
    bottom = max(0, bottom)
    left = max(0, left)
    right = max(0, right)

    image_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)
    pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")

    ref_image, mask_image = get_upscale_image_and_mask(
      pil_image,
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

    # Save raw_ref and mask_ref for debugging
    gcs_uri_base, ext = os.path.splitext(gcs_uri)
    if not ext:
      ext = ".png"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    gcs_uri_base = f"{gcs_uri_base}_{timestamp}"

    outpaint_gcs_uri = f"{gcs_uri_base}_outpaint{ext}"
    print(
      f"Outpainting image with Google GenAI API ({self.model.model_name}) to {outpaint_gcs_uri}"
    )
    response = self.model_client.models.edit_image(
      model=self.model.model_name,
      prompt=prompt or "",
      reference_images=[raw_ref, mask_ref],
      config=genai_types.EditImageConfig(
        edit_mode=genai_types.EditMode.EDIT_MODE_OUTPAINT,
        number_of_images=1,
        output_mime_type="image/png",
        output_gcs_uri=outpaint_gcs_uri,
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

    return generated.image.gcs_uri


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
  ) -> models.Image:
    """Generates an image using the OpenAI Images API.

    Args:
      prompt: The text prompt for the image.
      reference_images: A list of bytes, where each item is the content of a
        reference image.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      The generated image.
    """
    start_time = time.perf_counter()

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
      for i, img in enumerate(reference_images):
        if isinstance(img, str):
          image_bytes = cloud_storage.download_bytes_from_gcs(img)
        elif isinstance(img, Image.Image):
          image_bytes = img.tobytes()
        elif isinstance(img, bytes):
          image_bytes = img
        else:
          raise ValueError(
            f"OpenAI reference image must be bytes, got {type(img)}")

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

    output_gcs_uri = cloud_storage.get_image_gcs_uri(self.file_name_base,
                                                     self.extension)

    # Upload image bytes to GCS
    print("Uploading image to GCS")
    final_gcs_uri = cloud_storage.upload_bytes_to_gcs(image_bytes,
                                                      output_gcs_uri,
                                                      content_type="image/png")

    image_model = models.Image(
      url=cloud_storage.get_final_image_url(final_gcs_uri),
      gcs_uri=final_gcs_uri,
      original_prompt=prompt,
      final_prompt=prompt,
      error=None,
      owner_user_id=user_uid,
      generation_metadata=models.GenerationMetadata(),
    )
    image_model.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=self.model.model_name,
        token_costs=self.model.token_costs,
        usage_dict={
          "input_tokens": result.usage.input_tokens,
          "output_tokens": result.usage.output_tokens,
        },
        generation_time_sec=time.perf_counter() - start_time,
      ))

    return image_model


class OpenAiResponsesClient(ImageClient[OpenAI]):
  """OpenAI client implementation for the Responses API."""

  CHAT_MODEL_NAME = "gpt-4.1-mini"

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
  ) -> models.Image:
    """Generates an image using the OpenAI Responses API.

    Args:
      prompt: The text prompt for the image.
      reference_images: A list of strings, where each item is the ID of an
        image generation call.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      The generated image.
    """
    start_time = time.perf_counter()

    request_inputs = []
    quality = self.model.kwargs["quality"]

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
      model=OpenAiResponsesClient.CHAT_MODEL_NAME,
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

    output_gcs_uri = cloud_storage.get_image_gcs_uri(self.file_name_base,
                                                     self.extension)

    # Upload image bytes to GCS
    print(f"Uploading image to GCS: {output_gcs_uri}")
    final_gcs_uri = cloud_storage.upload_bytes_to_gcs(image_bytes,
                                                      output_gcs_uri,
                                                      content_type="image/png")

    image = models.Image(
      url=cloud_storage.get_final_image_url(final_gcs_uri),
      gcs_uri=final_gcs_uri,
      original_prompt=prompt,
      final_prompt=prompt,
      error=None,
      owner_user_id=user_uid,
      generation_metadata=models.GenerationMetadata(),
      custom_temp_data={
        "image_generation_call_id": image_generation_call.id,
      },
    )
    # Usage cost for the chat model
    image.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=OpenAiResponsesClient.CHAT_MODEL_NAME,
        token_costs=OTHER_TOKEN_COSTS[OpenAiResponsesClient.CHAT_MODEL_NAME],
        usage_dict={
          "input_tokens": response.usage.input_tokens,
          "output_tokens": response.usage.output_tokens,
        },
        generation_time_sec=time.perf_counter() - start_time,
      ))

    # Usage cost for the image generation call
    image.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=f"{self.model.model_name} ({quality})",
        token_costs=self.model.token_costs,
        usage_dict={
          "images": 1,
        },
        generation_time_sec=time.perf_counter() - start_time,
      ))

    return image


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
    return genai.Client(
      # api_key=config.get_gemini_api_key(),
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
  ) -> models.Image:
    """Generates an image using the Gemini API.

    Args:
      prompt: The text prompt for the image.
      reference_images: A list of PIL.Image.Image objects or bytes.
      user_uid: The UID of the user requesting the image.
      extra_log_data: Additional data to include in the log.

    Returns:
      The generated image.
    """
    start_time = time.perf_counter()

    contents = []

    for img in _get_reference_images(reference_images):
      contents.append(img)

    contents.append(prompt)

    output_gcs_uri = cloud_storage.get_image_gcs_uri(
      self.file_name_base,
      self.extension,
    )

    print("Generating image with Google GenAI API")
    response = self.model_client.models.generate_content(
      model=self.model.model_name,
      contents=contents,
    )

    image_parts = [
      part.inline_data.data for part in response.candidates[0].content.parts
      if part.inline_data
    ]

    if not image_parts:
      raise ValueError("No image data returned from Gemini")

    image_bytes = image_parts[0]

    # Upload image bytes to GCS
    print("Uploading image to GCS")
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
    )
    image_model.generation_metadata.add_generation(
      _build_generation_metadata(
        label=self.label,
        model_name=self.model.model_name,
        usage_dict={
          "images": 1,
        },
        token_costs=self.model.token_costs,
        generation_time_sec=time.perf_counter() - start_time,
      ))

    return image_model


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
      image_bytes = cloud_storage.download_bytes_from_gcs(image_data)
      img = Image.open(BytesIO(image_bytes))
    else:
      raise ValueError(
        f"Reference image must be a PIL Image or bytes, got {type(image_data)}"
      )
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

  # Add a ~5% margin on the outpainting sides so transitions can be redrawn.
  margin_left = int(round(original_width * 0.05)) if left > 0 else 0
  margin_right = int(round(original_width * 0.05)) if right > 0 else 0
  margin_top = int(round(original_height * 0.05)) if top > 0 else 0
  margin_bottom = int(round(original_height * 0.05)) if bottom > 0 else 0

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


def get_upscale_image_and_mask(
  original_image: Image.Image,
  top: int,
  bottom: int,
  left: int,
  right: int,
) -> tuple[Image.Image, Image.Image]:
  """Create the reference and mask images for outpainting/upscaling.

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
