"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
import math
import zipfile
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from typing import Callable

from common import config, models
from firebase_functions import logger
from PIL import Image
from services import cloud_storage, firestore, image_client, image_editor

_AD_BACKGROUND_SQUARE_DRAWING_URI = "gs://images.quillsstorybook.com/joke_assets/background_drawing_1280_1280.png"
_AD_BACKGROUND_SQUARE_DESK_URI = "gs://images.quillsstorybook.com/joke_assets/background_desk_1280_1280.png"
_AD_BACKGROUND_SQUARE_CORKBOARD_URI = "gs://images.quillsstorybook.com/joke_assets/background_corkboard_1280_1280.png"

_BOOK_PAGE_BASE_SIZE = 1800
_BOOK_PAGE_BLEED_PX = 38
_BOOK_PAGE_FINAL_WIDTH = _BOOK_PAGE_BASE_SIZE + _BOOK_PAGE_BLEED_PX
_BOOK_PAGE_FINAL_HEIGHT = _BOOK_PAGE_BASE_SIZE + (_BOOK_PAGE_BLEED_PX * 2)

_BOOK_OUTPAINT_MODEL = image_client.ImageModel.DUMMY_OUTPAINTER
_BOOK_UPSCALE_MODEL = image_client.ImageModel.IMAGEN_4_UPSCALE


def create_blank_book_cover() -> bytes:
  """Create a blank CMYK JPEG cover image matching book page dimensions.

  The final book page images are _BOOK_PAGE_FINAL_WIDTH
  by _BOOK_PAGE_FINAL_HEIGHT pixels (after bleed cropping on the inner edge),
  so the cover uses the same size to align with the printed pages.
  """
  width = _BOOK_PAGE_FINAL_WIDTH
  height = _BOOK_PAGE_FINAL_HEIGHT
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
  page_index = 3

  # Add a blank intro page as page 002 before any joke pages.
  intro_bytes = create_blank_book_cover()
  files.append(("002_intro.jpg", intro_bytes))

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

  Setup images render on the right page and punchline images on the left page.
  To preserve the full joke artwork we first outpaint each source image by
  adding 5% margin on every side and, on edges that require bleed, enough extra
  canvas so that the final trimmed image still has 38 pixels of bleed. The
  outpainted result is then upscaled by 2x before being scaled back down to the
  exact 1838x1876 print dimensions.

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

  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.setup_image_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.punchline_image_url)
  logger.info(
    f"Processing original images: {setup_gcs_uri} and {punchline_gcs_uri}")

  setup_page_bytes = _process_book_page(
    joke_id=joke_id,
    gcs_uri=setup_gcs_uri,
    is_left_page=False,
    editor=editor,
    page_label='setup',
  )
  punchline_page_bytes = _process_book_page(
    joke_id=joke_id,
    gcs_uri=punchline_gcs_uri,
    is_left_page=True,
    editor=editor,
    page_label='punchline',
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

  setup_img = cloud_storage.download_image_from_gcs(setup_gcs_uri)
  punchline_img = cloud_storage.download_image_from_gcs(punchline_gcs_uri)

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


@dataclass(frozen=True)
class _OutpaintMargins:
  top: int
  bottom: int
  left: int
  right: int


def _process_book_page(
  *,
  joke_id: str,
  gcs_uri: str,
  is_left_page: bool,
  editor: image_editor.ImageEditor,
  page_label: str,
) -> bytes:
  """Generate a print-ready page from the original joke artwork."""
  source_image = cloud_storage.download_image_from_gcs(gcs_uri).convert('RGB')
  margins = _calculate_book_page_margins(
    width=source_image.width,
    height=source_image.height,
    is_left_page=is_left_page,
  )

  outpaint_client = image_client.get_client(
    label='book_page_generation',
    model=_BOOK_OUTPAINT_MODEL,
    file_name_base=f'{joke_id}_{page_label}_outpaint',
  )
  outpainted_image = outpaint_client.outpaint_image(
    top=margins.top,
    bottom=margins.bottom,
    left=margins.left,
    right=margins.right,
    gcs_uri=gcs_uri,
    save_to_firestore=False,
  )
  if not outpainted_image.gcs_uri:
    raise ValueError('Outpaint operation did not return a GCS URI')

  upscale_client = image_client.get_client(
    label='book_page_generation',
    model=_BOOK_UPSCALE_MODEL,
    file_name_base=f'{joke_id}_{page_label}_upscale',
  )
  upscaled_image = upscale_client.upscale_image(
    upscale_factor='x2',
    mime_type='image/png',
    compression_quality=None,
    gcs_uri=outpainted_image.gcs_uri,
    save_to_firestore=False,
  )
  upscaled_gcs_uri = upscaled_image.gcs_uri_upscaled or upscaled_image.gcs_uri
  if not upscaled_gcs_uri:
    raise ValueError('Upscale operation did not return a GCS URI')

  upscaled_image = cloud_storage.download_image_from_gcs(
    upscaled_gcs_uri).convert('RGB')
  scaled_cropped_image = _scale_and_crop_book_page(
    editor=editor,
    image=upscaled_image,
    is_left_page=is_left_page,
  )
  return _convert_to_cmyk_jpeg_bytes(scaled_cropped_image)

  # - Use the exact same scene, composition, and camera angle as the CONTENT image. The main characters, their poses and positioning, expressions, etc. MUST be identical. You may ONLY make the following changes:


_BOOK_PAGE_PROMPT_TEMPLATE = """
{intro}
* A STYLE reference image of a super cute drawing of a construction worker cat on textured paper. Use this image as reference for:
  - Art style: Super cute colored pencil drawing, with a clear main subject, and supporting/background elements that extend to the edge of the canvas.
  - Canvas/background: Off-white textured paper
  - Font: Clean "handwritten" style
  - Overall aesthetic: Super cute and silly

Generatea new version of the CONTENT image, but with the canvas/foreground/background seamlessly extended through the black bleed margins.

 Your new image must:
  - Show the exact same words as the CONTENT image.
  - Use the exact same scene, composition, and camera angle as the CONTENT image. The main characters, their poses and positioning, expressions, etc. MUST be identical. You may ONLY make the following changes:
    - Fix mistakes/errors, such as anatomical errors on the characters, objects, etc.
    - Add details to the main characters/objects to make them more polished, complete, and visually appealing, but be sure to respect the artistic style of a child-like colored pencil drawing.
    - Seamlessly replace the black margins with the canvas filled with minor foreground/background elements. Some/all of this area will be trimmed off during printing, so make sure these elements are not critical to the joke. The goal is to use this margin as bleed for printing.
    - Add/remove/change the supporting foreground/background elements to make the image make sense and be more visually appealing.
    - If the CONTENT image has a lot of empty space, add supporting foreground/background elements to fill it. Make sure these elements play a supporting role and do not conflict with the main subject.
  - All text and major elements must be OUTSIDE of the bleed area.
  - Be drawn on the same textured paper canvas as the STYLE reference image.
  - The final image must make sense. If there are any supporting elemments in the CONTENT image that get in the way of your bleed margin expansion, you may change them to make the image make sense.
{additional_requirements}

Here is the description for the CONTENT image. You must follow this description exactly:
{{image_description}}

The final generated image should be high quality, professional-looking copy of the CONTENT image, suitable for a children's picture book, and print ready with bleed margins matching all around it.
"""

_BOOK_PAGE_SETUP_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given 2 images. The first is a an illustration of the setup line of a two-liner joke, and the second image is a style reference image:

* A CONTENT image of a drawing on textured paper with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the setup of the joke.
""",
  additional_requirements="",
)

_BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given 3 images. The first two are a two-panel illustration of a two-liner joke, and the third image is a style reference image:

  * A SETUP image that visualizes the 1st panel: the setup line of the joke. Use this image ONLY as consistency reference for any recurring characters and objects.

  * A CONTENT image of a drawing on textured paper with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the punchline of the joke.
  """,
  additional_requirements="""
  - Any recurring characters or elements from the SETUP image must be consistent with the SETUP image.
""",
)


def generate_book_pages_with_nano_banana_pro(
  *,
  setup_image: Image.Image,
  punchline_image: Image.Image,
  style_reference_image: Image.Image,
  setup_image_description: str,
  punchline_image_description: str,
  output_file_name_base: str,
) -> tuple[models.Image, models.Image]:
  """Generate a book page image using Gemini Nano Banana Pro.

  Generates a 2048x2048 image that:
    - Ensures a margin around the image contents
    - Adds bleed margins
    - Redraw in the same style
  """
  client = image_client.get_client(
    label='book_page_generation',
    model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
    file_name_base=output_file_name_base,
  )
  margin_pixels = math.ceil(setup_image.width * 0.1)

  setup_image_with_margins, _ = image_client.get_upscale_image_and_mask(
    setup_image, margin_pixels, margin_pixels, margin_pixels, margin_pixels)
  generated_setup_image = client.generate_image(
    prompt=_BOOK_PAGE_SETUP_PROMPT_TEMPLATE.format(
      image_description=setup_image_description),
    reference_images=[
      setup_image_with_margins,
      style_reference_image,
    ],
  )
  final_setup_image = cloud_storage.download_image_from_gcs(
    generated_setup_image.gcs_uri)

  punchline_image_with_margins, _ = image_client.get_upscale_image_and_mask(
    punchline_image, margin_pixels, margin_pixels, margin_pixels,
    margin_pixels)
  generated_punchline_image = client.generate_image(
    prompt=_BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE.format(
      image_description=punchline_image_description),
    reference_images=[
      final_setup_image,
      punchline_image_with_margins,
      style_reference_image,
    ],
  )

  return (generated_setup_image, generated_punchline_image)


def _calculate_book_page_margins(
  *,
  width: int,
  height: int,
  is_left_page: bool,
) -> _OutpaintMargins:
  """Compute outpainting margins for book pages.

  Adds a base 5% padding on all sides of the original image, then adds
  extra margin for print bleed on the top, bottom, and outer edge so that,
  after scaling to the 1800x1800 base page size, there is effectively
  38px of bleed on those edges. The inner edge (towards the binding)
  only gets the base padding and no extra bleed.
  """
  base_horizontal = max(1, round(width * 0.05))
  base_vertical = max(1, round(height * 0.05))

  width_without_bleed = width + (base_horizontal * 2)
  height_without_bleed = height + (base_vertical * 2)

  horizontal_bleed_extra = math.ceil(
    _BOOK_PAGE_BLEED_PX * width_without_bleed / _BOOK_PAGE_BASE_SIZE)
  vertical_bleed_extra = math.ceil(_BOOK_PAGE_BLEED_PX * height_without_bleed /
                                   _BOOK_PAGE_BASE_SIZE)

  left = base_horizontal
  right = base_horizontal
  if is_left_page:
    left += horizontal_bleed_extra
  else:
    right += horizontal_bleed_extra

  top = base_vertical + vertical_bleed_extra
  bottom = base_vertical + vertical_bleed_extra

  return _OutpaintMargins(
    top=top,
    bottom=bottom,
    left=left,
    right=right,
  )


def _scale_and_crop_book_page(
  *,
  editor: image_editor.ImageEditor,
  image: Image.Image,
  is_left_page: bool,
) -> Image.Image:
  """Scale and crop the outpainted image to the final print dimensions."""
  target_width = _BOOK_PAGE_FINAL_WIDTH
  target_height = _BOOK_PAGE_FINAL_HEIGHT

  scale_factor = max(
    target_width / image.width,
    target_height / image.height,
  )
  scaled = editor.scale_image(image, scale_factor)

  left = 0
  top = 0
  right = scaled.width
  bottom = scaled.height

  excess_width = scaled.width - target_width
  if excess_width > 0:
    if is_left_page:
      right -= excess_width
    else:
      left += excess_width

  excess_height = scaled.height - target_height
  if excess_height > 0:
    top += excess_height // 2
    bottom -= excess_height - (excess_height // 2)

  left = int(left)
  top = int(top)
  right = int(right)
  bottom = int(bottom)

  cropped = scaled.crop((left, top, right, bottom))

  horizontal_trim = scaled.width - cropped.width
  vertical_trim = scaled.height - cropped.height
  max_trim = 4
  if horizontal_trim > max_trim or vertical_trim > max_trim:
    raise ValueError(
      'Unexpected crop amount: '
      f'horizontal_trim={horizontal_trim}px (max {max_trim}px), '
      f'vertical_trim={vertical_trim}px (max {max_trim}px), '
      f'left={left}, top={top}, right={right}, bottom={bottom}')

  if cropped.width != target_width or cropped.height != target_height:
    cropped = cropped.resize(
      (target_width, target_height),
      Image.Resampling.LANCZOS,
    )

  return cropped


def _convert_to_cmyk_jpeg_bytes(image: Image.Image) -> bytes:
  """Convert an RGB image to CMYK JPEG bytes suited for print."""
  cmyk_image = image.convert('CMYK')
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
  base = cloud_storage.download_image_from_gcs(background_uri)

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
