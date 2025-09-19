"""Imagen service client."""

from __future__ import annotations

import base64
import logging
import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from io import BytesIO
from typing import Any, Generic, TypeVar, override

from common import config, models
from google import genai
from openai import OpenAI
from PIL import Image
from services import cloud_storage, firestore
from vertexai.preview.vision_models import Image as VertexImage
from vertexai.preview.vision_models import ImageGenerationModel

_T = TypeVar("_T")

# Lazily initialized clients by model name
_CLIENTS_BY_MODEL: dict[ImageModel, Any] = {}


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
    "imagen-4.0-ultra-generate-preview-06-06",
    {
      "images": 0.06
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_4_0_STANDARD = (
    "imagen-4.0-generate-preview-06-06",
    {
      "images": 0.04
    },
    ImageProvider.IMAGEN,
  )
  IMAGEN_4_0_FAST = (
    "imagen-4.0-fast-generate-preview-06-06",
    {
      "images": 0.02
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

  # https://openai.com/api/pricing
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

  # https://platform.openai.com/docs/pricing
  OPENAI_RESPONSES_API_LOW = (
    "gpt-image-1",
    {
      "images": 0.011,
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "low"
    },
  )
  OPENAI_RESPONSES_API_MEDIUM = (
    "gpt-image-1",
    {
      "images": 0.042,
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "medium"
    },
  )
  OPENAI_RESPONSES_API_HIGH = (
    "gpt-image-1",
    {
      "images": 0.167,
    },
    ImageProvider.OPENAI_RESPONSES,
    {
      "quality": "high"
    },
  )

  # https://ai.google.dev/gemini-api/docs/image-generation#pricing
  GEMINI_NANO_BANANA = (
    "gemini-2.5-flash-image-preview",
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


def _get_upscaled_gcs_uri(gcs_uri: str, new_size: int) -> str:
  """Constructs a GCS URI for the upscaled image."""
  base, ext = os.path.splitext(gcs_uri)
  return f"{base}_upscale_{new_size}{ext}"


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
    image = self._generate_image_internal(
      prompt,
      reference_images,
      user_uid,
      extra_log_data,
    )

    if not image.is_success:
      raise ValueError(f"Image generation failed: {image}")

    if save_to_firestore:
      logging.info("Saving image to Firestore")
      image = firestore.create_image(image)

    return image

  def upscale_image(
    self,
    new_size: int,
    image: models.Image | None = None,
    gcs_uri: str | None = None,
    save_to_firestore: bool = True,
  ) -> models.Image:
    """Upscale an image."""
    if not (image or gcs_uri) or (image and gcs_uri):
      raise ValueError("Exactly one of 'image' or 'gcs_uri' must be provided.")

    source_gcs_uri = image.gcs_uri if image else gcs_uri
    if not source_gcs_uri:
      raise ValueError("The provided image must have a gcs_uri.")

    start_time = time.perf_counter()
    upscaled_gcs_uri = self._upscale_image_internal(source_gcs_uri, new_size)

    generation_metadata = _build_generation_metadata(
      label=self.label,
      model_name=self.model.model_name,
      usage_dict={"upscale_images": 1},
      token_costs=self.model.token_costs,
      generation_time_sec=time.perf_counter() - start_time,
    )

    if image:
      image.gcs_uri_upscaled = upscaled_gcs_uri
      image.url_upscaled = cloud_storage.get_final_image_url(upscaled_gcs_uri,
                                                             width=new_size)
      if not image.generation_metadata:
        image.generation_metadata = models.GenerationMetadata()
      image.generation_metadata.add_generation(generation_metadata)
      if save_to_firestore:
        logging.info(f"Updating image {image.key} with upscaled version.")
        firestore.update_image(image)
      return image
    else:
      new_image = models.Image(
        gcs_uri=source_gcs_uri,
        url=cloud_storage.get_final_image_url(source_gcs_uri),
        gcs_uri_upscaled=upscaled_gcs_uri,
        url_upscaled=cloud_storage.get_final_image_url(upscaled_gcs_uri,
                                                       width=new_size),
        generation_metadata=models.GenerationMetadata(),
      )
      new_image.generation_metadata.add_generation(generation_metadata)
      if save_to_firestore:
        logging.info("Creating new image with upscaled version.")
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
    new_size: int,
  ) -> str:
    """Upscale an image.

    Args:
      gcs_uri: The GCS URI of the image to upscale.
      new_size: The new size of the image.

    Returns:
      The GCS URI of the upscaled image.
    """
    raise NotImplementedError


class ImagenClient(ImageClient[ImageGenerationModel]):
  """Imagen client implementation."""

  def __init__(self, label: str, model: ImageModel, file_name_base: str,
               **kwargs: Any):
    super().__init__(label=label,
                     model=model,
                     file_name_base=file_name_base,
                     extension="png",
                     **kwargs)

  @override
  def _create_model_client(self) -> ImageGenerationModel:
    return ImageGenerationModel.from_pretrained(self.model.model_name)

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

    print("Generating image with Imagen")
    images = self.model_client.generate_images(
      prompt=prompt,
      number_of_images=1,
      language="en",
      aspect_ratio="1:1",
      output_gcs_uri=output_gcs_uri,
      safety_filter_level="block_few",
      person_generation="allow_adult",
    )

    # There should only be one image, since we only asked for one
    image = images[0]

    final_gcs_uri = image._gcs_uri  # pylint: disable=protected-access
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

  def _upscale_image_internal(
    self,
    gcs_uri: str,
    new_size: int,
  ) -> str:
    """Upscales an image using the Imagen model."""
    if self.model != ImageModel.IMAGEN_1:
      raise ValueError(
        f"Upscaling is only supported for the {ImageModel.IMAGEN_1.model_name} model with ImagenClient."
      )

    print(f"Upscaling image with Imagen to size {new_size}")
    image_to_upscale = VertexImage.load_from_file(gcs_uri)

    output_gcs_uri = _get_upscaled_gcs_uri(gcs_uri, new_size)
    upscaled_image = self.model_client.upscale_image(
      image=image_to_upscale,
      new_size=new_size,
      output_gcs_uri=output_gcs_uri,
    )

    if not upscaled_image:
      raise ValueError("No upscaled image returned from Imagen")

    final_gcs_uri = upscaled_image._gcs_uri  # pylint: disable=protected-access
    if not final_gcs_uri:
      raise ValueError(
        f"No GCS URI returned for upscaled image (label={self.label})")

    return final_gcs_uri


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

    common_args = {
      "model": self.model.model_name,
      "prompt": prompt,
      "output_format": "png",
      "quality": self.model.kwargs["quality"],
      "size": "1024x1024",
      "background": "opaque",
    }

    if reference_images:
      for img in reference_images:
        if not isinstance(img, bytes):
          raise ValueError(
            f"OpenAI reference image must be bytes, got {type(img)}")

      reference_image_bytes = [
        (f"reference_image_{i}.png", image_bytes, "image/png")
        for i, image_bytes in enumerate(reference_images)
      ]
      print("Generating image with OpenAI with reference images")
      result = self.model_client.images.edit(
        **common_args,
        image=reference_image_bytes,
      )

    else:
      print("Generating image with OpenAI")
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
      print("Generating image with OpenAI Responses API with reference images")
    else:
      print("Generating image with OpenAI Responses API")

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

    quality = self.model.kwargs["quality"]
    response = self.model_client.responses.create(
      model=OpenAiResponsesClient.CHAT_MODEL_NAME,
      input=request_inputs,
      tools=[{
        "type": "image_generation",
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

  GEMINI_MODEL_NAME = "gemini-2.5-flash-image-preview"

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
      # Use Google AI API because the image Gemini model isn't on Vertex AI yet
      api_key=config.get_gemini_api_key(), )

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

    if reference_images:
      for image_data in reference_images:
        if isinstance(image_data, bytes):
          img = Image.open(BytesIO(image_data))
        elif isinstance(image_data, Image.Image):
          img = image_data
        else:
          raise ValueError(
            f"Gemini reference image must be a PIL Image or bytes, got {type(image_data)}"
          )
        contents.append(img)

    contents.append(prompt)

    print("Generating image with Google GenAI API")
    response = self.model_client.models.generate_content(
      model=GeminiImageClient.GEMINI_MODEL_NAME,
      contents=contents,
    )

    image_parts = [
      part.inline_data.data for part in response.candidates[0].content.parts
      if part.inline_data
    ]

    if not image_parts:
      raise ValueError("No image data returned from Gemini")

    image_bytes = image_parts[0]

    output_gcs_uri = cloud_storage.get_image_gcs_uri(
      self.file_name_base,
      self.extension,
    )

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
