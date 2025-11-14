"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
import zipfile
from functools import partial
from io import BytesIO
from typing import Callable

from common import config, joke_operations
from firebase_functions import logger
from PIL import Image
from services import cloud_storage, firestore, image_editor

_AD_BACKGROUND_SQUARE_DRAWING_URI = "gs://images.quillsstorybook.com/joke_assets/background_drawing_1280_1280.png"
_AD_BACKGROUND_SQUARE_DESK_URI = "gs://images.quillsstorybook.com/joke_assets/background_desk_1280_1280.png"
_AD_BACKGROUND_SQUARE_CORKBOARD_URI = "gs://images.quillsstorybook.com/joke_assets/background_corkboard_1280_1280.png"

_BOOK_PAGE_BASE_SIZE = 1800
_BOOK_PAGE_BLEED_PX = 38
_BOOK_PAGE_TARGET_SIZE = _BOOK_PAGE_BASE_SIZE + (_BOOK_PAGE_BLEED_PX * 2)


def create_blank_book_cover() -> bytes:
  """Create a blank CMYK JPEG cover image matching book page dimensions.

  The final book page images are (_BOOK_PAGE_TARGET_SIZE - _BOOK_PAGE_BLEED_PX)
  by _BOOK_PAGE_TARGET_SIZE pixels (after bleed cropping on the inner edge),
  so the cover uses the same size to align with the printed pages.
  """
  width = _BOOK_PAGE_TARGET_SIZE - _BOOK_PAGE_BLEED_PX
  height = _BOOK_PAGE_TARGET_SIZE
  # CMYK white is (0, 0, 0, 0)
  cover = Image.new('CMYK', (width, height), (0, 0, 0, 0))

  buffer = BytesIO()
  cover.save(
    buffer,
    format='JPEG',
    quality=100,
    subsampling=0,
  )
  return buffer.getvalue()


def zip_joke_page_images(joke_ids: list[str]) -> str:
  """Create and store a ZIP of book page images for the given jokes.

  The ZIP will contain sequentially numbered setup/punchline pages for each joke, using the original file names with a three-digit page prefix

  Args:
    joke_ids: Ordered list of joke document IDs.

  Returns:
    Public URL of the stored ZIP file.

  Raises:
    ValueError: If the joke list is empty, a joke is missing, or required
      metadata/images are missing.
  """
  if not joke_ids:
    raise ValueError("Joke book has no jokes")

  files: list[tuple[str, bytes]] = []
  page_index = 0

  for joke_id in joke_ids:
    joke_ref = firestore.db().collection('jokes').document(joke_id)
    joke_doc = joke_ref.get()
    if not joke_doc.exists:
      raise ValueError(f"Joke {joke_id} not found")

    metadata_ref = joke_ref.collection('metadata').document('metadata')
    metadata_doc = metadata_ref.get()
    if not metadata_doc.exists:
      raise ValueError(f"Joke {joke_id} does not have book page metadata")

    metadata = metadata_doc.to_dict() or {}
    setup_img = metadata.get('book_page_setup_image_url')
    punchline_img = metadata.get('book_page_punchline_image_url')
    if not setup_img or not punchline_img:
      raise ValueError(f"Joke {joke_id} does not have book page images")

    for image_url in (setup_img, punchline_img):
      gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(str(image_url))
      _, blob_name = cloud_storage.parse_gcs_uri(gcs_uri)
      original_filename = blob_name.rsplit('/', 1)[-1]
      image_bytes = cloud_storage.download_bytes_from_gcs(gcs_uri)

      filename = f"{page_index:03d}_{original_filename}"
      files.append((filename, image_bytes))
      page_index += 1

  # Build ZIP in memory
  zip_buffer = BytesIO()
  with zipfile.ZipFile(
      zip_buffer,
      mode='w',
      compression=zipfile.ZIP_DEFLATED,
  ) as zip_file:
    for filename, content in files:
      zip_file.writestr(filename, content)

  zip_bytes = zip_buffer.getvalue()

  # Store ZIP in temporary files bucket and return its public URL
  timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
  gcs_uri = cloud_storage.get_gcs_uri(
    'snickerdoodle_temp_files',
    f'joke_book_pages_{timestamp}',
    'zip',
  )
  cloud_storage.upload_bytes_to_gcs(
    zip_bytes,
    gcs_uri,
    'application/zip',
  )
  return cloud_storage.get_public_url(gcs_uri)


def create_book_pages(
  joke_id: str,
  image_editor_instance: image_editor.ImageEditor | None = None,
  overwrite: bool = False,
) -> list[str]:
  """Create book page images for a joke and store their URLs.

  Book pages are 6x6 inches at 300 DPI, or 1800x1800 pixels. However, there is
  0.125 inches (38 pixels) of bleed on the top, bottom, and outer edges. The
  inner edge (towards the binding) does NOT have bleed.

  Setup images will be on the right side of the page, and punchline images will
  be on the left side of the page. Therefore, the square joke images should be
  scaled to 1876x1876 pixels, and then have 38 pixels cropped from the inner
  edge. Crop the left side of setup images and the right side of punchline
  images.

  Args:
      joke_id: Firestore joke document ID
      image_editor_instance: Optional ImageEditor for dependency injection
      overwrite: Whether to overwrite existing assets

  Returns:
      List containing setup and punchline book page URLs, in that order.

  Raises:
      ValueError: If the joke is not found or is missing required image URLs.
  """
  logger.info(f'Creating book pages for joke {joke_id}')

  editor = image_editor_instance or image_editor.ImageEditor()

  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')
  if not joke.setup_image_url or not joke.punchline_image_url:
    raise ValueError(f'Joke {joke_id} does not have image URLs')

  metadata_ref = (firestore.db().collection('jokes').document(
    joke_id).collection('metadata').document('metadata'))
  metadata_snapshot = metadata_ref.get()
  metadata_data: dict[str, object] = {}
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}

  if not overwrite:
    existing_setup = metadata_data.get('book_page_setup_image_url')
    existing_punchline = metadata_data.get('book_page_punchline_image_url')
    if (isinstance(existing_setup, str) and existing_setup
        and isinstance(existing_punchline, str) and existing_punchline):
      return [existing_setup, existing_punchline]

  if (not joke.setup_image_url_upscaled
      or not joke.punchline_image_url_upscaled):
    joke = joke_operations.upscale_joke(joke_id)

  if (not joke.setup_image_url_upscaled
      or not joke.punchline_image_url_upscaled):
    raise ValueError(f'Joke {joke_id} does not have upscaled image URLs')

  setup_source_url = joke.setup_image_url_upscaled
  punchline_source_url = joke.punchline_image_url_upscaled
  logger.info(
    f"Using upscaled images: {setup_source_url} and {punchline_source_url}")

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    setup_source_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    punchline_source_url)
  logger.info(f"Extracted GCS URIs: {setup_gcs_uri} and {punchline_gcs_uri}")

  setup_bytes = cloud_storage.download_bytes_from_gcs(setup_gcs_uri)
  punchline_bytes = cloud_storage.download_bytes_from_gcs(punchline_gcs_uri)

  setup_img = Image.open(BytesIO(setup_bytes))
  punchline_img = Image.open(BytesIO(punchline_bytes))

  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

  setup_page_bytes = _create_book_page_image_bytes(
    editor,
    setup_img,
    crop_left=True,
  )
  punchline_page_bytes = _create_book_page_image_bytes(
    editor,
    punchline_img,
    crop_left=False,
  )

  setup_filename = f"{joke_id}_book_page_setup_{timestamp}.jpg"
  punchline_filename = f"{joke_id}_book_page_punchline_{timestamp}.jpg"

  setup_gcs_dest = f"gs://{config.IMAGE_BUCKET_NAME}/{setup_filename}"
  punchline_gcs_dest = f"gs://{config.IMAGE_BUCKET_NAME}/{punchline_filename}"

  cloud_storage.upload_bytes_to_gcs(
    setup_page_bytes,
    setup_gcs_dest,
    "image/jpeg",
  )
  cloud_storage.upload_bytes_to_gcs(
    punchline_page_bytes,
    punchline_gcs_dest,
    "image/jpeg",
  )

  setup_url = cloud_storage.get_public_url(setup_gcs_dest)
  punchline_url = cloud_storage.get_public_url(punchline_gcs_dest)

  metadata_updates = {
    'book_page_setup_image_url': setup_url,
    'book_page_punchline_image_url': punchline_url,
  }
  metadata_ref.set(
    metadata_updates,
    merge=True,
  )

  return [setup_url, punchline_url]


def create_ad_assets(
  joke_id: str,
  image_editor_instance: image_editor.ImageEditor | None = None,
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
      'square_drawing':
      partial(_compose_square_drawing_ad_image,
              background_uri=_AD_BACKGROUND_SQUARE_DRAWING_URI),
      'square_desk':
      partial(_compose_square_drawing_ad_image,
              background_uri=_AD_BACKGROUND_SQUARE_DESK_URI),
      'square_corkboard':
      partial(_compose_square_drawing_ad_image,
              background_uri=_AD_BACKGROUND_SQUARE_CORKBOARD_URI),
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


def _create_book_page_image_bytes(
  editor: image_editor.ImageEditor,
  source_image: Image.Image,
  crop_left: bool,
) -> bytes:
  """Create a single print-ready book page image as CMYK JPEG bytes.

  The source image is assumed to be square. It is scaled uniformly so that the
  shorter side reaches 1876px, then 38px is cropped from either the left or
  right edge to provide inner binding clearance.
  """
  scale_factor = _BOOK_PAGE_TARGET_SIZE / float(source_image.width)
  scaled = editor.scale_image(source_image, scale_factor)

  width, height = scaled.width, scaled.height
  bleed = min(_BOOK_PAGE_BLEED_PX, max(1, width - 1))
  if crop_left:
    left = bleed
    right = width
  else:
    left = 0
    right = max(bleed, width - bleed)

  cropped = editor.crop_image(
    scaled,
    left=int(left),
    top=0,
    right=int(right),
    bottom=height,
  )
  cmyk_image = cropped.convert('CMYK')

  buffer = BytesIO()
  cmyk_image.save(
    buffer,
    format='JPEG',
    quality=100,
    subsampling=0,
    dpi=(300, 300),
  )
  return buffer.getvalue()


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


def _compose_square_drawing_ad_image(
  editor: image_editor.ImageEditor,
  setup_image: Image.Image,
  punchline_image: Image.Image,
  background_uri: str,
) -> tuple[bytes, int]:
  """Create a 1200x1200 square PNG with background and post-it style shadows."""
  # Load the portrait background image from GCS
  bg_bytes = cloud_storage.download_bytes_from_gcs(background_uri)
  base = Image.open(BytesIO(bg_bytes))

  # Paste punchline image first so it's below the setup image
  # Transform punchline image
  punchline_scaled = editor.scale_image(punchline_image, 0.57)
  punchline_rotated = editor.rotate_image(punchline_scaled, -2)
  # Paste roughly bottom-right (diagonally opposed)
  base = editor.paste_image(base, punchline_rotated, 470, 635, add_shadow=True)

  # Transform setup image
  setup_scaled = editor.scale_image(setup_image, 0.57)
  setup_rotated = editor.rotate_image(setup_scaled, 5)
  # Paste near top-left
  base = editor.paste_image(base, setup_rotated, 190, 35, add_shadow=True)

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  return buffer.getvalue(), base.width
