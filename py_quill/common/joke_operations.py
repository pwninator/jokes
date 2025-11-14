"""Operations for jokes."""

from __future__ import annotations

from typing import Literal

from common import models
from firebase_functions import logger
from google.cloud.firestore_v1.vector import Vector
from services import cloud_storage, firestore, image_client

_IMAGE_UPSCALE_FACTOR = "x2"


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
