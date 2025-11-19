"""Operations for jokes."""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, Literal, Tuple

from common import image_generation, models
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.vector import Vector
from PIL import Image
from services import cloud_storage, firestore, image_client, image_editor
from services.firestore import OPERATION, SAVED_VALUE

_IMAGE_UPSCALE_FACTOR = "x2"
_HIGH_QUALITY_UPSCALE_FACTOR = "x2"

_MIME_TYPE_CONFIG: dict[str, Tuple[str, str]] = {
  "image/png": ("PNG", "png"),
  "image/jpeg": ("JPEG", "jpg"),
}


class JokeOperationsError(Exception):
  """Base exception for joke operation failures."""


class JokePopulationError(JokeOperationsError):
  """Exception raised for errors in joke population."""


class SafetyCheckError(JokeOperationsError):
  """Raised when content safety checks fail."""


def create_joke(
  *,
  setup_text: str,
  punchline_text: str,
  admin_owned: bool,
  user_id: str,
) -> models.PunnyJoke:
  """Create a new punny joke with default metadata and persist it."""
  setup_text = setup_text.strip()
  punchline_text = punchline_text.strip()
  if not setup_text:
    raise ValueError('Setup text is required')
  if not punchline_text:
    raise ValueError('Punchline text is required')

  owner_user_id = "ADMIN" if admin_owned else user_id

  (
    setup_scene_idea,
    punchline_scene_idea,
    generation_metadata,
  ) = _generate_scene_ideas(setup_text, punchline_text)

  payload = {
    "setup_text": setup_text,
    "punchline_text": punchline_text,
    "setup_scene_idea": setup_scene_idea,
    "punchline_scene_idea": punchline_scene_idea,
    "owner_user_id": owner_user_id,
    "state": models.JokeState.DRAFT,
    "random_id": random.randint(0, 2**31 - 1),
    "generation_metadata": generation_metadata,
  }

  logger.info("Creating joke for owner %s", owner_user_id)
  joke = models.PunnyJoke(**payload)

  saved_joke = firestore.upsert_punny_joke(
    joke,
    operation_log_entry={
      OPERATION: "CREATE",
      "setup_text": SAVED_VALUE,
      "punchline_text": SAVED_VALUE,
      "setup_scene_idea": SAVED_VALUE,
      "punchline_scene_idea": SAVED_VALUE,
    },
  )
  if not saved_joke:
    raise ValueError('Failed to save joke - may already exist')

  return saved_joke


def _generate_scene_ideas(
  setup_text: str,
  punchline_text: str,
) -> Tuple[str, str, models.GenerationMetadata]:
  """Generate scene ideas and run content safety in parallel."""
  with ThreadPoolExecutor(max_workers=2) as executor:
    scene_future = executor.submit(
      joke_operation_prompts.generate_joke_scene_ideas,
      setup_text,
      punchline_text,
    )
    safety_future = executor.submit(
      joke_operation_prompts.run_safety_check,
      f"Setup: {setup_text}\nPunchline: {punchline_text}",
    )

    (
      setup_scene_idea,
      punchline_scene_idea,
      ideas_is_safe,
      idea_generation_metadata,
    ) = scene_future.result()
    safety_is_safe, safety_generation_metadata = safety_future.result()

  if not safety_is_safe or not ideas_is_safe:
    raise SafetyCheckError('Joke content failed safety review')

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(idea_generation_metadata)
  generation_metadata.add_generation(safety_generation_metadata)

  return setup_scene_idea, punchline_scene_idea, generation_metadata


def modify_image_descriptions(
  joke: models.PunnyJoke,
  setup_suggestion: str,
  punchline_suggestion: str,
) -> models.PunnyJoke:
  """Update a joke's image descriptions using the provided suggestions.

  This is a placeholder implementation that will be fleshed out later.
  """
  _ = (setup_suggestion, punchline_suggestion)
  saved_joke = firestore.upsert_punny_joke(joke)
  if not saved_joke:
    raise ValueError('Failed to save joke while updating image descriptions')
  return saved_joke


def generate_joke_images(joke: models.PunnyJoke,
                         image_quality: str) -> models.PunnyJoke:
  """Populate a joke with new images using the image generation service."""
  if not joke.setup_text:
    raise JokePopulationError('Joke is missing setup text')
  if not joke.punchline_text:
    raise JokePopulationError('Joke is missing punchline text')
  if not joke.setup_image_description:
    raise JokePopulationError('Joke is missing setup image description')
  if not joke.punchline_image_description:
    raise JokePopulationError('Joke is missing punchline image description')

  pun_data = [(joke.setup_text, joke.setup_image_description),
              (joke.punchline_text, joke.punchline_image_description)]

  images = image_generation.generate_pun_images(pun_data, image_quality)

  if len(images) == 2:
    joke.set_setup_image(images[0])
    joke.set_punchline_image(images[1])
  else:
    raise JokePopulationError(
      f'Image generation returned insufficient images: expected 2, got {len(images)}'
    )

  joke.setup_image_url_upscaled = None
  joke.punchline_image_url_upscaled = None

  return joke


def upscale_joke(
  joke_id: str,
  mime_type: Literal["image/png", "image/jpeg"] = "image/png",
  *,
  compression_quality: int | None = None,
  overwrite: bool = False,
  high_quality: bool = False,
) -> models.PunnyJoke:
  """Upscales a joke's images.

  If overwrite is False, this function is idempotent. If the joke already
  has upscaled URLs, it will return immediately.

  Args:
    joke_id: The ID of the joke to upscale.
    mime_type: The MIME type of the image.
    compression_quality: The compression quality of the image.
    overwrite: Whether to force re-upscaling even if URLs already exist.
    high_quality: Whether to use high-quality upscaling and replace base images.
  """
  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')

  setup_needs_upscale = bool(joke.setup_image_url and
                             (overwrite or not joke.setup_image_url_upscaled))
  punchline_needs_upscale = bool(
    joke.punchline_image_url
    and (overwrite or not joke.punchline_image_url_upscaled))

  if not (setup_needs_upscale or punchline_needs_upscale):
    return joke

  model = (image_client.ImageModel.IMAGEN_4_UPSCALE
           if high_quality else image_client.ImageModel.IMAGEN_1)
  upscale_factor = (_HIGH_QUALITY_UPSCALE_FACTOR
                    if high_quality else _IMAGE_UPSCALE_FACTOR)
  client = image_client.get_client(
    label="upscale_joke_high" if high_quality else "upscale_joke_standard",
    model=model,
    file_name_base="upscaled_joke_image",
  )
  if joke.generation_metadata is None:
    joke.generation_metadata = models.GenerationMetadata()

  update_data: dict[str, Any] = {}

  if setup_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="setup",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  if punchline_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="punchline",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  update_data["generation_metadata"] = joke.generation_metadata.as_dict
  firestore.update_punny_joke(joke.key, update_data)

  return joke


def _process_upscale_for_image(
  *,
  joke: models.PunnyJoke,
  image_role: Literal["setup", "punchline"],
  client: image_client.ImageClient,
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscale_factor: Literal["x2", "x4"],
  replace_original: bool,
) -> dict[str, Any]:
  """Upscale a single image (setup or punchline) and return updated fields."""
  url_attr = f"{image_role}_image_url"
  upscaled_attr = f"{image_role}_image_url_upscaled"
  all_urls_attr = f"all_{image_role}_image_urls"
  set_method = getattr(joke,
                       f"set_{image_role}_image") if replace_original else None

  source_url = getattr(joke, url_attr)
  if not source_url:
    return {}

  gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(source_url)
  upscaled_image = client.upscale_image(
    upscale_factor=upscale_factor,
    mime_type=mime_type,
    compression_quality=compression_quality,
    gcs_uri=gcs_uri,
  )

  setattr(joke, upscaled_attr, upscaled_image.url_upscaled)
  joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  update_data: dict[str, Any] = {
    upscaled_attr: getattr(joke, upscaled_attr),
  }

  if replace_original and upscaled_image.gcs_uri_upscaled:
    original_dimensions = _get_image_dimensions(gcs_uri)
    downscaled_gcs_uri, downscaled_url = _create_downscaled_image(
      joke=joke,
      image_role=image_role,
      editor=image_editor.ImageEditor(),
      target_dimensions=original_dimensions,
      mime_type=mime_type,
      compression_quality=compression_quality,
      upscaled_image_gcs_uri=upscaled_image.gcs_uri_upscaled,
    )
    replacement_image = models.Image(
      url=downscaled_url,
      gcs_uri=downscaled_gcs_uri,
      url_upscaled=upscaled_image.url_upscaled,
      gcs_uri_upscaled=upscaled_image.gcs_uri_upscaled,
      generation_metadata=models.GenerationMetadata(),  # Already added above
    )
    set_method(replacement_image, update_text=False)
    update_data[url_attr] = getattr(joke, url_attr)
    update_data[all_urls_attr] = getattr(joke, all_urls_attr)

  return update_data


def _get_image_dimensions(gcs_uri: str) -> Tuple[int, int]:
  """Load image dimensions from GCS."""
  with Image.open(BytesIO(
      cloud_storage.download_bytes_from_gcs(gcs_uri))) as img:
    return img.width, img.height


def _create_downscaled_image(
  *,
  joke: models.PunnyJoke,
  image_role: str,
  editor: image_editor.ImageEditor,
  target_dimensions: Tuple[int, int],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscaled_image_gcs_uri: str,
) -> Tuple[str, str]:
  """Create a downscaled image that matches the original dimensions."""
  upscaled_image = cloud_storage.download_image_from_gcs(
    upscaled_image_gcs_uri)
  target_width, target_height = target_dimensions

  if upscaled_image.width == 0 or upscaled_image.height == 0:
    raise ValueError("Upscaled image has invalid dimensions")

  scale_factor = min(
    target_width / upscaled_image.width,
    target_height / upscaled_image.height,
  )
  scaled_image = editor.scale_image(upscaled_image, scale_factor)
  if (scaled_image.width, scaled_image.height) != target_dimensions:
    scaled_image = scaled_image.resize(
      size=target_dimensions,
      resample=Image.Resampling.LANCZOS,
    )

  image_bytes = _image_to_bytes(
    scaled_image,
    mime_type=mime_type,
    compression_quality=compression_quality,
  )

  _, extension = _MIME_TYPE_CONFIG[mime_type]
  file_base = f"{joke.key or 'joke'}_{image_role}_hq"
  downscaled_gcs_uri = cloud_storage.get_image_gcs_uri(file_base, extension)
  cloud_storage.upload_bytes_to_gcs(
    content_bytes=image_bytes,
    gcs_uri=downscaled_gcs_uri,
    content_type=mime_type,
  )
  downscaled_url = cloud_storage.get_final_image_url(downscaled_gcs_uri,
                                                     width=target_width)
  return downscaled_gcs_uri, downscaled_url


def _image_to_bytes(
  image: Image.Image,
  *,
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
) -> bytes:
  """Serialize an image to bytes according to the provided MIME type."""
  format_name, _ = _MIME_TYPE_CONFIG[mime_type]
  save_kwargs: dict[str, Any] = {}

  if mime_type == "image/jpeg":
    if image.mode not in ("RGB", "L"):
      image = image.convert("RGB")
    save_kwargs["quality"] = compression_quality or 95
    save_kwargs["optimize"] = True
  elif mime_type == "image/png" and image.mode == "CMYK":
    image = image.convert("RGBA")

  buffer = BytesIO()
  image.save(buffer, format=format_name, **save_kwargs)
  return buffer.getvalue()


def sync_joke_to_search_collection(
  joke: models.PunnyJoke,
  new_embedding: Vector | None,
) -> None:
  """Syncs joke data to the joke_search collection document."""
  if not joke.key:
    return

  joke_id = joke.key
  search_doc_ref = firestore.db().collection("joke_search").document(joke_id)
  search_doc = search_doc_ref.get()
  search_data = search_doc.to_dict() if search_doc.exists else {}

  update_payload = {}

  # 1. Sync embedding
  if new_embedding:
    update_payload["text_embedding"] = new_embedding
  elif "text_embedding" not in search_data and joke.zzz_joke_text_embedding:
    update_payload["text_embedding"] = joke.zzz_joke_text_embedding

  # 2. Sync state
  if search_data.get("state") != joke.state.value:
    update_payload["state"] = joke.state.value

  # 3. Sync is_public
  if search_data.get("is_public") != joke.is_public:
    update_payload["is_public"] = joke.is_public

  # 4. Sync public_timestamp
  if search_data.get("public_timestamp") != joke.public_timestamp:
    update_payload["public_timestamp"] = joke.public_timestamp

  # 5. Sync num_saved_users_fraction
  if search_data.get(
      "num_saved_users_fraction") != joke.num_saved_users_fraction:
    update_payload["num_saved_users_fraction"] = joke.num_saved_users_fraction

  # 6. Sync num_shared_users_fraction
  if search_data.get(
      "num_shared_users_fraction") != joke.num_shared_users_fraction:
    update_payload[
      "num_shared_users_fraction"] = joke.num_shared_users_fraction

  # 7. Sync popularity_score
  if search_data.get("popularity_score") != joke.popularity_score:
    update_payload["popularity_score"] = joke.popularity_score

  if update_payload:
    logger.info(
      f"Syncing joke to joke_search collection: {joke_id} with payload keys {update_payload.keys()}"
    )
    search_doc_ref.set(update_payload, merge=True)


def to_response_joke(joke: models.PunnyJoke) -> dict[str, Any]:
  """Convert a PunnyJoke to a dictionary suitable for API responses."""
  joke_dict = joke.to_dict(include_key=True)
  joke_dict.pop('zzz_joke_text_embedding', None)
  return joke_dict
