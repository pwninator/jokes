"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
from io import BytesIO
from typing import Callable

from PIL import Image
from common import config
from services import cloud_storage, firestore, image_editor


def create_ad_assets(
  joke_id: str,
  image_editor_instance: image_editor.ImageEditor
  | None = None,
) -> list[str]:
  """Create ad creative images for a joke and store their URLs.

  Generates one or more composed images (currently a 2048x1024 landscape) and
  stores each URL under the joke's `metadata/metadata` document using the field
  name pattern `ad_creative_{key}` where `key` matches the composer identifier.

  Args:
      joke_id: Firestore joke document ID
      image_editor_instance: Optional ImageEditor for dependency injection

  Returns:
      List of final image URLs in the order defined by the composers map.

  Raises:
      ValueError: If the joke is not found or is missing required image URLs.
  """
  editor = image_editor_instance or image_editor.ImageEditor()

  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')
  if not getattr(joke, 'setup_image_url', None) or not getattr(
      joke, 'punchline_image_url', None):
    raise ValueError(f'Joke {joke_id} missing required image URLs')

  metadata_ref = (firestore.db().collection('jokes').document(
    joke_id).collection('metadata').document('metadata'))
  metadata_snapshot = metadata_ref.get()
  metadata_data: dict[str, object] = {}
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}

  composers: dict[
    str, Callable[[image_editor.ImageEditor, Image.Image, Image.Image],
                  tuple[bytes, int]]] = {
                    'landscape': _compose_landscape_ad_image,
                  }

  existing_urls: list[str] = []
  all_existing = True
  for key in composers:
    field_name = f'ad_creative_{key}'
    value = metadata_data.get(field_name)
    if isinstance(value, str) and value:
      existing_urls.append(value)
    else:
      all_existing = False
      break
  if all_existing and existing_urls:
    return existing_urls

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.setup_image_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.punchline_image_url)

  setup_bytes = cloud_storage.download_bytes_from_gcs(setup_gcs_uri)
  punchline_bytes = cloud_storage.download_bytes_from_gcs(punchline_gcs_uri)

  setup_img = Image.open(BytesIO(setup_bytes))
  punchline_img = Image.open(BytesIO(punchline_bytes))

  final_urls: list[str] = []
  metadata_updates: dict[str, str] = {}
  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

  for key, compose_fn in composers.items():
    field_name = f'ad_creative_{key}'
    existing_url = metadata_data.get(field_name)
    if isinstance(existing_url, str) and existing_url:
      final_urls.append(existing_url)
      continue

    image_bytes, composed_width = compose_fn(editor, setup_img, punchline_img)
    filename = f"{joke_id}_ad_{key}_{timestamp}.png"
    gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{filename}"

    cloud_storage.upload_bytes_to_gcs(image_bytes, gcs_uri, "image/png")
    final_url = cloud_storage.get_final_image_url(gcs_uri,
                                                  width=composed_width)
    final_urls.append(final_url)
    metadata_updates[field_name] = final_url

  if metadata_updates:
    metadata_ref.set(
      metadata_updates,
      merge=True,
    )

  return final_urls


def _compose_landscape_ad_image(
  editor: image_editor.ImageEditor,
  setup_image: Image.Image,
  punchline_image: Image.Image,
) -> tuple[bytes, int]:
  """Create a 2048x1024 landscape PNG of the setup/punchline images."""
  base = editor.create_blank_image(2048, 1024)
  editor.paste_image(base, setup_image, 0, 0)
  editor.paste_image(base, punchline_image, 1024, 0)

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  return buffer.getvalue(), base.width
