"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
from functools import partial
from io import BytesIO
from typing import Callable

from common import config
from PIL import Image
from services import cloud_storage, firestore, image_editor

_AD_BACKGROUND_PORTRAIT_DRAWING_URI = "gs://images.quillsstorybook.com/joke_assets/background_drawing_1024_1280.png"
_AD_BACKGROUND_LANDSCAPE_DESK_URI = "gs://images.quillsstorybook.com/joke_assets/background_desk_1024_1280.png"
_AD_BACKGROUND_LANDSCAPE_CORKBOARD_URI = "gs://images.quillsstorybook.com/joke_assets/background_corkboard_1024_1280.png"


def create_ad_assets(
  joke_id: str,
  image_editor_instance: image_editor.ImageEditor
  | None = None,
  overwrite: bool = False,
) -> list[str]:
  """Create ad creative images for a joke and store their URLs.

  Generates one or more composed images (currently a 2048x1024 landscape) and
  stores each URL under the joke's `metadata/metadata` document using the field
  name pattern `ad_creative_{key}` where `key` matches the composer identifier.

  Args:
      joke_id: Firestore joke document ID
      image_editor_instance: Optional ImageEditor for dependency injection
      overwrite: Whether to overwrite existing assets

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

  composers: dict[str, Callable[
    [image_editor.ImageEditor, Image.Image, Image.Image],
    tuple[bytes, int]]] = {
      'landscape':
      _compose_landscape_ad_image,
      'portrait_drawing':
      partial(_compose_portrait_drawing_ad_image,
              background_uri=_AD_BACKGROUND_PORTRAIT_DRAWING_URI),
      'portrait_desk':
      partial(_compose_portrait_drawing_ad_image,
              background_uri=_AD_BACKGROUND_LANDSCAPE_DESK_URI),
      'portrait_corkboard':
      partial(_compose_portrait_drawing_ad_image,
              background_uri=_AD_BACKGROUND_LANDSCAPE_CORKBOARD_URI),
    }

  if not overwrite:
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
    if (not overwrite) and isinstance(existing_url, str) and existing_url:
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
  base = editor.paste_image(base, setup_image, 0, 0)
  base = editor.paste_image(base, punchline_image, 1024, 0)

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  return buffer.getvalue(), base.width


def _compose_portrait_drawing_ad_image(
  editor: image_editor.ImageEditor,
  setup_image: Image.Image,
  punchline_image: Image.Image,
  background_uri: str,
) -> tuple[bytes, int]:
  """Create a 1024x1280 portrait PNG with background and post-it style shadows."""
  # Load the portrait background image from GCS
  bg_bytes = cloud_storage.download_bytes_from_gcs(background_uri)
  base = Image.open(BytesIO(bg_bytes))

  # Transform setup image: scale 50%, rotate -4 degrees
  setup_scaled = editor.scale_image(setup_image, 0.6)
  setup_rotated = editor.rotate_image(setup_scaled, -4)
  # Paste near top-left
  base = editor.paste_image(base, setup_rotated, 40, 40, add_shadow=True)

  # Transform punchline image: scale 50%, rotate +3 degrees
  punchline_scaled = editor.scale_image(punchline_image, 0.6)
  punchline_rotated = editor.rotate_image(punchline_scaled, 3)
  # Paste roughly bottom-right (diagonally opposed)
  base = editor.paste_image(base, punchline_rotated, 342, 598, add_shadow=True)

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  return buffer.getvalue(), base.width
