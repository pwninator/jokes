"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
from io import BytesIO

from PIL import Image
from common import config
from services import cloud_storage, firestore, image_editor


def create_ad_assets(
  joke_id: str,
  image_editor_instance: image_editor.ImageEditor
  | None = None,
) -> str:
  """Create a 2048x1024 landscape ad image for a joke and store its URL.

  The resulting image places the setup (1024x1024) on the left and the
  punchline (1024x1024) on the right, then uploads as PNG and stores the
  final CDN URL in the joke's `metadata/metadata` subdocument under the
  field `ad_creative_landscape`.

  Args:
      joke_id: Firestore joke document ID
      image_editor_instance: Optional ImageEditor for dependency injection

  Returns:
      The final image URL.

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
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}
    existing_url = metadata_data.get('ad_creative_landscape')
    if existing_url:
      return existing_url

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.setup_image_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.punchline_image_url)

  setup_bytes = cloud_storage.download_bytes_from_gcs(setup_gcs_uri)
  punchline_bytes = cloud_storage.download_bytes_from_gcs(punchline_gcs_uri)

  setup_img = Image.open(BytesIO(setup_bytes))
  punchline_img = Image.open(BytesIO(punchline_bytes))

  base = editor.create_blank_image(2048, 1024)
  editor.paste_image(base, setup_img, 0, 0)
  editor.paste_image(base, punchline_img, 1024, 0)

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  image_bytes = buffer.getvalue()

  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
  filename = f"{joke_id}_ad_landscape_{timestamp}.png"
  gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{filename}"

  cloud_storage.upload_bytes_to_gcs(image_bytes, gcs_uri, "image/png")

  final_url = cloud_storage.get_final_image_url(gcs_uri, width=2048)

  metadata_ref.set(
    {'ad_creative_landscape': final_url},
    merge=True,
  )

  return final_url
