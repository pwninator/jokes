"""Operations for jokes."""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from common import image_generation, models
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.vector import Vector
from services import cloud_storage, firestore, image_client

_IMAGE_UPSCALE_FACTOR = "x2"


class JokeOperationsError(Exception):
  """Base exception for joke operation failures."""


class JokePopulationError(JokeOperationsError):
  """Exception raised for errors in joke population."""


class SafetyCheckError(JokeOperationsError):
  """Exception raised for errors in safety check."""


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

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(idea_generation_metadata)
  generation_metadata.add_generation(safety_generation_metadata)

  if not safety_is_safe or not ideas_is_safe:
    raise SafetyCheckError('Joke content failed safety review')

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

  saved_joke = firestore.upsert_punny_joke(joke)
  if not saved_joke:
    raise ValueError('Failed to save joke - may already exist')

  return saved_joke


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
  compression_quality: int | None = None,
) -> models.PunnyJoke:
  """Upscales a joke's images.

  This function is idempotent. If the joke already has upscaled URLs,
  it will return immediately.

  Args:
    joke_id: The ID of the joke to upscale.
    mime_type: The MIME type of the image.
    compression_quality: The compression quality of the image.
  """
  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')

  if joke.setup_image_url_upscaled and joke.punchline_image_url_upscaled:
    return joke

  client = image_client.get_client(
    label="upscale_joke",
    model=image_client.ImageModel.IMAGEN_1,
    file_name_base="upscaled_joke_image",
  )

  if joke.setup_image_url and not joke.setup_image_url_upscaled:
    gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
      joke.setup_image_url)
    upscaled_image = client.upscale_image(
      upscale_factor=_IMAGE_UPSCALE_FACTOR,
      mime_type=mime_type,
      compression_quality=compression_quality,
      gcs_uri=gcs_uri,
    )
    joke.setup_image_url_upscaled = upscaled_image.url_upscaled
    joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  if joke.punchline_image_url and not joke.punchline_image_url_upscaled:
    gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
      joke.punchline_image_url)
    upscaled_image = client.upscale_image(
      upscale_factor=_IMAGE_UPSCALE_FACTOR,
      mime_type=mime_type,
      compression_quality=compression_quality,
      gcs_uri=gcs_uri,
    )
    joke.punchline_image_url_upscaled = upscaled_image.url_upscaled
    joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  update_data = {
    "setup_image_url_upscaled": joke.setup_image_url_upscaled,
    "punchline_image_url_upscaled": joke.punchline_image_url_upscaled,
    "generation_metadata": joke.generation_metadata.as_dict,
  }
  firestore.update_punny_joke(joke.key, update_data)

  return joke


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
