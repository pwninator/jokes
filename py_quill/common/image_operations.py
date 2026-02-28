"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
import math
import zipfile
from dataclasses import dataclass
from functools import lru_cache, partial
from io import BytesIO
from typing import Callable, cast

import requests
from agents import constants
from common import config, models
from firebase_functions import logger
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.document import DocumentReference
from PIL import Image, ImageDraw, ImageFont
from services import cloud_storage, firestore, image_client, image_editor, pdf_client

_AD_BACKGROUND_SQUARE_DRAWING_URI = "gs://images.quillsstorybook.com/joke_assets/background_drawing_1280_1280.png"
_AD_BACKGROUND_SQUARE_DESK_URI = "gs://images.quillsstorybook.com/joke_assets/background_desk_1280_1280.png"
_AD_BACKGROUND_SQUARE_CORKBOARD_URI = "gs://images.quillsstorybook.com/joke_assets/background_corkboard_1280_1280.png"

_AD_LANDSCAPE_CANVAS_WIDTH = 2048
_AD_LANDSCAPE_CANVAS_HEIGHT = 1024
_AD_SQUARE_JOKE_IMAGE_SIZE_PX = 584

_STYLE_UPDATE_CANVAS_URL = constants.STYLE_REFERENCE_CANVAS_IMAGE_URL
_STYLE_REFERENCE_IMAGE_URLS = constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS
_BOOK_PAGE_BASE_SIZE = 1800
_BOOK_PAGE_BLEED_PX = 38
_BOOK_PAGE_FINAL_WIDTH = _BOOK_PAGE_BASE_SIZE + _BOOK_PAGE_BLEED_PX
_BOOK_PAGE_FINAL_HEIGHT = _BOOK_PAGE_BASE_SIZE + (_BOOK_PAGE_BLEED_PX * 2)

# KDP seems to print better in RGB mode than CMYK.
_KDP_PRINT_COLOR_MODE = 'RGB'

_PAGE_NUMBER_FONT_URLS = (
  'https://github.com/googlefonts/nunito/raw/4be812cf4761b3ddc3b0ae894ef40ea21dcf6ff3/fonts/TTF/Nunito-Regular.ttf',
  'https://github.com/googlefonts/nunito/raw/refs/heads/main/fonts/variable/Nunito%5Bwght%5D.ttf',
)
_PAGE_NUMBER_FONT_SIZE = 60
_PAGE_NUMBER_STROKE_RATIO = 0.14
_PAGE_NUMBER_TEXT_COLOR = (33, 33, 33)
_PAGE_NUMBER_STROKE_COLOR = (255, 255, 255)

_PANEL_BLOCKER_OVERLAY_URL_PUPPY = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/_joke_assets/panel_blocker_overlay1.png"
_PANEL_BLOCKER_OVERLAY_URL_POST_IT = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/_joke_assets/panel_blocker_overlay2.png"
_PINTEREST_PANEL_SIZE_PX = 500
_PINTEREST_DIVIDER_SAMPLE_COUNT = 5
_PINTEREST_DIVIDER_TARGET_CONTRAST = 3.0

_SOCIAL_BACKGROUND_4X5_SWIPE_REVEAL_URL = (
  "https://storage.googleapis.com/images.quillsstorybook.com/_joke_assets/social/background_4x5_swipe_reveal.png"
)
_SOCIAL_BACKGROUND_4X5_SWIPE_MORE_URL = (
  "https://storage.googleapis.com/images.quillsstorybook.com/_joke_assets/social/background_4x5_swipe_more.png"
)
_SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL = (
  "https://storage.googleapis.com/images.quillsstorybook.com/_joke_assets/social/background_4x5_website_more.png"
)
_SOCIAL_4X5_CANVAS_SIZE_PX = (1024, 1280)
_SOCIAL_4X5_JOKE_IMAGE_SIZE_PX = (1024, 1024)


@dataclass(frozen=True)
class JokeBookExportFiles:
  """Public URLs for generated joke-book export files."""
  zip_url: str
  paperback_pdf_url: str


def create_blank_book_cover(*, color_mode: str) -> bytes:
  """Create a blank JPEG cover image matching book page dimensions.

  The final book page images are _BOOK_PAGE_FINAL_WIDTH
  by _BOOK_PAGE_FINAL_HEIGHT pixels (after bleed cropping on the inner edge),
  so the cover uses the same size to align with the printed pages.
  """
  width = _BOOK_PAGE_FINAL_WIDTH
  height = _BOOK_PAGE_FINAL_HEIGHT
  if color_mode == 'RGB':
    cover_color = (255, 255, 255)
  elif color_mode == 'CMYK':
    # CMYK white is (0, 0, 0, 0)
    cover_color = (0, 0, 0, 0)
  else:
    raise ValueError(
      f'Unsupported color_mode for create_blank_book_cover: {color_mode}')

  cover = Image.new(color_mode, (width, height), cover_color)

  buffer = BytesIO()
  cover.save(
    buffer,
    format='JPEG',
    quality=100,
    subsampling=0,
    dpi=(300, 300),
  )
  return buffer.getvalue()


def _enhance_kdp_export_page_bytes(
  page_bytes: bytes,
  *,
  editor: image_editor.ImageEditor,
) -> bytes:
  """Apply the default image-enhancement pass to a final KDP page image."""
  with Image.open(BytesIO(page_bytes)) as page_image:
    _ = page_image.load()
    enhanced_page = editor.enhance_image(page_image)

  try:
    if enhanced_page.mode != 'RGB':
      enhanced_page = enhanced_page.convert('RGB')

    buffer = BytesIO()
    enhanced_page.save(
      buffer,
      format='JPEG',
      quality=100,
      subsampling=0,
      dpi=(300, 300),
    )
    return buffer.getvalue()
  finally:
    enhanced_page.close()


def _build_kdp_export_pages(joke_ids: list[str]) -> list[tuple[str, bytes]]:
  """Build ordered print-ready page files for joke-book exports."""
  if not joke_ids:
    raise ValueError("Joke book has no jokes")

  files: list[tuple[str, bytes]] = []
  page_index = 3
  total_pages = len(joke_ids) * 2
  current_page_number = 1
  editor = image_editor.ImageEditor()

  # Add a blank intro page as page 002 before any joke pages.
  intro_bytes = create_blank_book_cover(color_mode=_KDP_PRINT_COLOR_MODE)
  files.append(("002_intro.jpg", intro_bytes))

  for joke_id in joke_ids:
    joke_ref = firestore.db().collection('jokes').document(joke_id)
    joke_doc = joke_ref.get()
    if not joke_doc.exists:
      raise ValueError(f"Joke {joke_id} not found")

    metadata_ref = cast(
      DocumentReference,
      joke_ref.collection('metadata').document('metadata'),
    )
    metadata_doc: DocumentSnapshot = metadata_ref.get()
    if not metadata_doc.exists:
      raise ValueError(f"Joke {joke_id} does not have book page metadata")

    metadata = cast(dict[str, object], metadata_doc.to_dict() or {})
    setup_img_url = metadata.get('book_page_setup_image_url')
    punchline_img_url = metadata.get('book_page_punchline_image_url')
    if not isinstance(setup_img_url, str) or not isinstance(
        punchline_img_url, str) or not setup_img_url or not punchline_img_url:
      raise ValueError(f"Joke {joke_id} does not have book page images")

    setup_image = cloud_storage.download_image_from_gcs(setup_img_url)
    punchline_image = cloud_storage.download_image_from_gcs(punchline_img_url)

    setup_bytes = _enhance_kdp_export_page_bytes(
      _convert_for_print_kdp(
        setup_image,
        is_punchline=False,
        page_number=current_page_number,
        total_pages=total_pages,
        color_mode=_KDP_PRINT_COLOR_MODE,
      ),
      editor=editor,
    )
    current_page_number += 1
    punchline_bytes = _enhance_kdp_export_page_bytes(
      _convert_for_print_kdp(
        punchline_image,
        is_punchline=True,
        page_number=current_page_number,
        total_pages=total_pages,
        color_mode=_KDP_PRINT_COLOR_MODE,
      ),
      editor=editor,
    )
    current_page_number += 1

    setup_file_name = f"{page_index:03d}_{joke_id}_setup.jpg"
    page_index += 1
    punchline_file_name = f"{page_index:03d}_{joke_id}_punchline.jpg"
    page_index += 1
    files.append((setup_file_name, setup_bytes))
    files.append((punchline_file_name, punchline_bytes))

  return files


def _build_zip_bytes(files: list[tuple[str, bytes]]) -> bytes:
  """Build a ZIP archive from the provided file list."""
  zip_buffer = BytesIO()
  with zipfile.ZipFile(
      zip_buffer,
      mode='w',
      compression=zipfile.ZIP_DEFLATED,
  ) as zip_file:
    for filename, content in files:
      zip_file.writestr(filename, content)
  return zip_buffer.getvalue()


def _build_joke_book_export_uris() -> tuple[str, str]:
  """Return paired GCS URIs for the ZIP and paperback PDF exports."""
  timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
  bucket_name = 'snickerdoodle_temp_files'
  base_name = f'joke_book_pages_{timestamp}'
  zip_gcs_uri = f'gs://{bucket_name}/{base_name}.zip'
  pdf_gcs_uri = f'gs://{bucket_name}/{base_name}_paperback.pdf'
  return zip_gcs_uri, pdf_gcs_uri


def export_joke_page_files_for_kdp(joke_ids: list[str]) -> JokeBookExportFiles:
  """Create and store the ZIP and paperback PDF for a joke-book export."""
  files = _build_kdp_export_pages(joke_ids)
  zip_bytes = _build_zip_bytes(files)
  pdf_bytes = pdf_client.create_pdf(
    [content for _, content in files],
    dpi=300,
    quality=100,
  )
  zip_gcs_uri, pdf_gcs_uri = _build_joke_book_export_uris()
  _ = cloud_storage.upload_bytes_to_gcs(
    zip_bytes,
    zip_gcs_uri,
    'application/zip',
  )
  _ = cloud_storage.upload_bytes_to_gcs(
    pdf_bytes,
    pdf_gcs_uri,
    'application/pdf',
  )
  return JokeBookExportFiles(
    zip_url=cloud_storage.get_public_url(zip_gcs_uri),
    paperback_pdf_url=cloud_storage.get_public_url(pdf_gcs_uri),
  )


def generate_and_populate_book_pages(
  joke_id: str,
  overwrite: bool = False,
  additional_setup_instructions: str = "",
  additional_punchline_instructions: str = "",
  base_image_source: str = "original",
  style_update: bool = False,
  include_image_description: bool = True,
) -> tuple[models.Image, models.Image]:
  """Create book page images for a joke and store their URLs.

  Book pages are 6x6 inches at 300 DPI, or 1800x1800 pixels. However, there is
  0.125 inches (38 pixels) of bleed on the top, bottom, and outer edges. The
  inner edge (towards the binding) does NOT have bleed.

  Setup images render on the right page and punchline images on the left page.
  When the base image source is the original joke image, we first outpaint each
  source image by adding margin so the final trimmed image retains the required
  bleed. When the base image source is an existing book page, we skip this
  margin step to avoid compounding print margins.

  Args:
      joke_id: Firestore joke document ID
      overwrite: Whether to overwrite existing assets
      style_update: Whether to use the simplified style-update flow

  Returns:
      The setup and punchline book page images.

  Raises:
      ValueError: If the joke is not found or is missing required image URLs.
  """
  logger.info(f'Creating book pages for joke {joke_id}')

  if base_image_source not in ('original', 'book_page'):
    raise ValueError(
      f'Invalid base_image_source: {base_image_source} (expected original or book_page)'
    )

  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')
  if not joke.setup_image_url or not joke.punchline_image_url:
    raise ValueError(f'Joke {joke_id} does not have image URLs')

  metadata_ref = cast(
    DocumentReference,
    firestore.db().collection('jokes').document(joke_id).collection(
      'metadata').document('metadata'),
  )
  metadata_snapshot: DocumentSnapshot = metadata_ref.get()
  metadata_data: dict[str, object] = {}
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}

  base_setup_url = joke.setup_image_url
  base_punchline_url = joke.punchline_image_url
  # Add print margins by default to base images
  add_print_margins = True
  if base_image_source == 'book_page':
    meta_setup = metadata_data.get('book_page_setup_image_url')
    meta_punchline = metadata_data.get('book_page_punchline_image_url')
    if isinstance(meta_setup, str) and meta_setup and isinstance(
        meta_punchline, str) and meta_punchline:
      base_setup_url = meta_setup
      base_punchline_url = meta_punchline
      # Don't add print margins to book page images because they already have them
      add_print_margins = False

  if not base_setup_url or not base_punchline_url:
    raise ValueError(
      f'Joke {joke_id} does not have image URLs for base_image_source {base_image_source}'
    )

  if not overwrite:
    existing_setup = metadata_data.get('book_page_setup_image_url')
    existing_punchline = metadata_data.get('book_page_punchline_image_url')
    if (isinstance(existing_setup, str) and existing_setup
        and isinstance(existing_punchline, str) and existing_punchline):
      return (
        models.Image(
          url=existing_setup,
          gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(existing_setup),
        ),
        models.Image(
          url=existing_punchline,
          gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(
            existing_punchline),
        ),
      )

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(base_setup_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    base_punchline_url)
  logger.info(
    f"Processing base images ({base_image_source}): {setup_gcs_uri} and {punchline_gcs_uri}"
  )

  setup_image_model = models.Image(url=base_setup_url, gcs_uri=setup_gcs_uri)
  punchline_image_model = models.Image(url=base_punchline_url,
                                       gcs_uri=punchline_gcs_uri)

  if style_update:
    generation_result = generate_book_pages_style_update(
      setup_image=setup_image_model,
      punchline_image=punchline_image_model,
      setup_text=(joke.setup_text or "").strip(),
      punchline_text=(joke.punchline_text or "").strip(),
      output_file_name_base=f'{joke_id}_book_page',
      additional_setup_instructions=additional_setup_instructions,
      additional_punchline_instructions=additional_punchline_instructions,
      include_image_description=include_image_description,
      add_print_margins=add_print_margins,
    )
  else:
    style_reference_images = [
      models.Image(
        url=image_url,
        gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(image_url))
      for image_url in _STYLE_REFERENCE_IMAGE_URLS
    ]

    generation_result = generate_book_pages_with_nano_banana_pro(
      setup_image=setup_image_model,
      punchline_image=punchline_image_model,
      style_reference_images=style_reference_images,
      setup_image_description=joke.setup_image_description or "",
      punchline_image_description=joke.punchline_image_description or "",
      output_file_name_base=f'{joke_id}_book_page',
      additional_setup_instructions=additional_setup_instructions,
      additional_punchline_instructions=additional_punchline_instructions,
      add_print_margins=add_print_margins,
    )

  generated_setup_url = generation_result.generated_setup_image.url
  generated_punchline_url = generation_result.generated_punchline_image.url
  if not generated_setup_url or not generated_punchline_url:
    raise ValueError(
      f'Generated book page images are missing URLs for {joke_id}')

  metadata_book_page_updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    existing_metadata=metadata_data,
    new_setup_page_url=generated_setup_url,
    new_punchline_page_url=generated_punchline_url,
    setup_prompt=generation_result.setup_prompt,
    punchline_prompt=generation_result.punchline_prompt,
  )

  metadata_updates = {
    'book_page_simple_setup_image_url':
    generation_result.simple_setup_image.url,
    'book_page_simple_punchline_image_url':
    generation_result.simple_punchline_image.url,
    'book_page_setup_image_model_thought':
    generation_result.generated_setup_image.model_thought,
    'book_page_punchline_image_model_thought':
    generation_result.generated_punchline_image.model_thought,
    **metadata_book_page_updates,
  }

  joke.generation_metadata.add_generation(
    generation_result.generated_setup_image.generation_metadata)
  joke.generation_metadata.add_generation(
    generation_result.generated_punchline_image.generation_metadata)
  _ = firestore.update_punny_joke(
    joke_id,
    update_data={
      'generation_metadata': joke.generation_metadata.as_dict,
    },
    update_metadata=metadata_updates,
  )

  return (
    generation_result.generated_setup_image,
    generation_result.generated_punchline_image,
  )


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

  metadata_ref = cast(
    DocumentReference,
    firestore.db().collection('jokes').document(joke_id).collection(
      'metadata').document('metadata'),
  )
  metadata_snapshot: DocumentSnapshot = metadata_ref.get()
  metadata_data: dict[str, object] = {}
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}

  composers: dict[str, Callable[
    [image_editor.ImageEditor, Image.Image, Image.Image],
    tuple[Image.Image, int]]] = {
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

  setup_url = joke.setup_image_url
  punchline_url = joke.punchline_image_url
  if not isinstance(setup_url, str) or not isinstance(punchline_url, str):
    raise ValueError(f'Joke {joke_id} missing required image URLs')

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(setup_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    punchline_url)

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

    composed_image, composed_width = compose_fn(editor, setup_img,
                                                punchline_img)
    filename = f"{joke_id}_ad_{key}_{timestamp}.png"
    gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{filename}"

    _, _ = cloud_storage.upload_image_to_gcs(
      composed_image,
      f"{joke_id}_ad_{key}",
      "png",
      gcs_uri=gcs_uri,
    )
    final_url = cloud_storage.get_final_image_url(gcs_uri,
                                                  width=composed_width)
    final_urls.append(final_url)
    metadata_updates[field_name] = final_url

  if metadata_updates:
    _ = metadata_ref.set(
      metadata_updates,
      merge=True,
    )

  return final_urls


_BOOK_PAGE_SIMPLE_PROMPT_TEMPLATE = """
You are given an image of a drawing. This image will be referred to as the CONTENT image.

Seamlessly extend the CONTENT image through the black bleed margins.

 Your new image must:
  - Show the exact same words and contents as the CONTENT image, except the canvas/image are extended through the black bleed margins. Some/all of this area will be trimmed off during printing, so make sure content in these areas are not critical to the joke. The goal is to use this margin as bleed for printing.

{additional_instructions}
"""

_BOOK_PAGE_PROMPT_TEMPLATE = """
{intro}

Generate a new, polished version of the CONTENT image that is seamlessly extended through the black bleed margins and adheres to the art style defined below.

Art style:
Create a professional-quality children's book illustration in the style of soft-core colored pencils on medium-tooth paper. The artwork must feature organic, sketch-like outlines rendered in a darker, saturated shade of the subject's fill color (e.g., deep orange lines for yellow fur, dark indigo for blue water), strictly avoiding black ink or graphite contours. Use visible directional strokes and tight cross-hatching to build up color saturation layer by layer. The look should be rich and vibrant, yet retain the individual stroke texture, ensuring the white of the paper peeks through slightly to create warmth without looking messy, patchy, or unfinished. The image must be fully rendered in full color across the entire sceneâ€”backgrounds must be detailed and finished, not monochromatic or vignette-style. Subject proportions should follow a cute, chibi style (oversized heads, large expressive eyes with highlights, small bodies), resulting in an aesthetic that feels tactile and hand-crafted, yet polished enough for high-quality printing.

 Your new image must:
  - Show the exact same words as the CONTENT image.
  - Use the exact same scene, composition, and camera angle as the CONTENT image. The main characters, their poses and positioning, expressions, etc. MUST be identical (unless otherwise specified below). You may ONLY make the following changes:
    - Seamlessly extend the image (both canvas and drawing) into the black margins. Some/all of this area will be trimmed off during printing, so make sure these elements are not critical to the joke. The goal is to use this margin as bleed for printing.
    - Adjust the artistic style of the image to be consistent with the art style described above and examplified by the STYLE reference image.
  - All text and major elements must be outside of the bleed area.
  - Be drawn on the same textured paper canvas as the reference image.
  - The final image must make sense. If there are any supporting elemments in the CONTENT image that get in the way of your bleed margin expansion, you may change them to make the image make sense.
{additional_requirements}

{{additional_instructions}}

{{image_description_block}}

Generate the final image, which should be high quality, professional-looking copy of the CONTENT image, suitable for a children's picture book, and print ready with appropriate bleed marg
"""

_BOOK_PAGE_SETUP_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given several images. The first is a an illustration of the setup line of a two-liner joke, and the rest are style reference images:

  - A CONTENT image of a drawing with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the setup of the joke.

  - STYLE reference images that help you visualize the desired art style described below. Use these images ONLY as reference for:
    - Art style: Super cute colored pencil drawing, with a clear main subject, and supporting/background elements that extend to the edge of the canvas.
    - Canvas/background: Off-white textured paper
    - Font: Clean, informal, and playful
    - Overall aesthetic: Super cute and silly
""",
  additional_requirements="",
  additional_thinking="",
)

_BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given 2 images that form a two-panel illustration of a two-liner joke:

  - A SETUP reference image that visualizes the 1st panel: the setup line of the joke. Use this image as consistency reference for:
    - Any recurring characters, objects, and scenes.
    - Art style: Super cute colored pencil drawing, with a clear main subject, and supporting/background elements that extend to the edge of the canvas.
    - Canvas: Off-white textured paper
    - Supporting elements: If you add supporting elements to the CONTENT image (e.g. sky, background, etc.), and the CONTENT image takes place in the same setting as the SETUP image, then the supporting elements must exactly match the supporting elements in the SETUP image.
    - Font: Clean "handwritten" style
    - Overall aesthetic: Super cute and silly

  - A CONTENT image of a drawing with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the punchline of the joke.
  """,
  additional_requirements="""
  - Any recurring characters or elements from the SETUP image must be consistent with the SETUP image.
""",
  additional_thinking="",
)

_STYLE_UPDATE_PROMPT_TEMPLATE = """
You are given the following reference images:
{references_block}

Generate a new image of CONTENT, converting it to the style of the listed reference images, drawn on the CANVAS paper. Specifically:

- Drastically simplify the background, reducing it to just a very light, faintly colored shading where you can barely make out the bare minimum of background scene, and possibly with a few simple colored foreground elements if needed.
- Simplify the art style of the main subject to match the simple, casual, doodle-like style of the REFERENCE1 and REFERENCE2 images. However, the character design, pose, and appearance must exactly match the CONTENT image.
- Change the font to match the casual and slightly uneven handwriting style of the text in REFERENCE1 and REFERENCE2.
{references_instructions}
{additional_instructions}
"""


@dataclass(frozen=True)
class _BookPageGenerationResult:

  simple_setup_image: models.Image
  simple_punchline_image: models.Image
  generated_setup_image: models.Image
  generated_punchline_image: models.Image
  setup_prompt: str
  punchline_prompt: str


def generate_book_pages_with_nano_banana_pro(  # pylint: disable=too-many-arguments
  *,
  setup_image: models.Image,
  punchline_image: models.Image,
  style_reference_images: list[models.Image],
  setup_image_description: str,
  punchline_image_description: str,
  output_file_name_base: str,
  additional_setup_instructions: str,
  additional_punchline_instructions: str,
  include_image_description: bool = True,
  add_print_margins: bool = True,
) -> _BookPageGenerationResult:
  """Generate a book page image using Gemini Nano Banana Pro.

  Generates a 2048x2048 image that:
    - Ensures a margin around the image contents
    - Adds bleed margins
    - Redraw in the same style
  """
  generation_client = image_client.get_client(
    label='book_page_generation',
    model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
    file_name_base=output_file_name_base,
  )

  def _format_description(description: str) -> str:
    if include_image_description and description:
      return (
        "Here is the description for the CONTENT image. You must follow this description exactly:\n"
        f"{description}")
    return ""

  simple_setup_image = _get_simple_book_page(
    setup_image,
    f"{output_file_name_base}_setup",
    add_print_margins=add_print_margins,
  )
  setup_prompt = _BOOK_PAGE_SETUP_PROMPT_TEMPLATE.format(
    image_description_block=_format_description(setup_image_description),
    additional_instructions=_format_additional_instructions(
      additional_setup_instructions),
  )
  generated_setup_image = generation_client.generate_image(
    prompt=setup_prompt,
    reference_images=[simple_setup_image, *style_reference_images],
  )

  simple_punchline_image = _get_simple_book_page(
    punchline_image,
    f"{output_file_name_base}_punchline",
    add_print_margins=add_print_margins,
  )
  punchline_prompt = _BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE.format(
    image_description_block=_format_description(punchline_image_description),
    additional_instructions=_format_additional_instructions(
      additional_punchline_instructions),
  )
  generated_punchline_image = generation_client.generate_image(
    prompt=punchline_prompt,
    reference_images=[generated_setup_image, simple_punchline_image],
  )

  return _BookPageGenerationResult(
    simple_setup_image=simple_setup_image,
    simple_punchline_image=simple_punchline_image,
    generated_setup_image=generated_setup_image,
    generated_punchline_image=generated_punchline_image,
    setup_prompt=setup_prompt,
    punchline_prompt=punchline_prompt,
  )


def _format_additional_instructions(
    additional_instructions: str | None) -> str:
  """Format additional instructions for book page generation."""
  if not additional_instructions:
    return ""
  return f"""
In addition, here are crucial instructions from the editor that you must follow:
{additional_instructions}
"""


def _build_style_update_prompt(
  joke_text: str,
  *,
  additional_instructions: str | None,
  include_setup_reference: bool,
) -> str:
  references: list[str] = [
    f'- CONTENT: An image that says "{joke_text}" with colorful foreground/background',
    "- CANVAS: A blank piece of textured paper",
    '- REFERENCE1: Image that says "Because they can\'t catch it", showing a stylized lion chasing a hamburger, with a simple, low-contrast pastel background.',
    '- REFERENCE2: Image that says "What do you call a bear with no teeth" showing a bear sitting in front of a light, low contrast forest background with loose shading of light green colored pencils.',
  ]
  references_instructions = ""
  if include_setup_reference:
    references.append(
      "- PREVIOUS_PANEL: The previously generated panel in this 2-panel set; the new image must exactly match its characters, pose, expressions, and overall style."
    )
    references_instructions = """
    - Any recurring characters, objects, or backgrounds from the PREVIOUS_PANEL image must be consistent with the PREVIOUS_PANEL image in character design and art style. Critically, the art style and level of detail of the background should exactly match the PREVIOUS_PANEL image.
    """

  instruction_chunks: list[str] = []
  if additional_instructions:
    instruction_chunks.append("Additional editor instructions:\n" +
                              additional_instructions)
  formatted_instructions = (
    "\n" + "\n".join(instruction_chunks)) if instruction_chunks else ""

  return _STYLE_UPDATE_PROMPT_TEMPLATE.format(
    references_block="\n".join(references),
    additional_instructions=formatted_instructions,
    references_instructions=references_instructions,
  )


@lru_cache(maxsize=1)
def _get_style_update_reference_images(
) -> tuple[models.Image, models.Image, models.Image]:
  canvas = models.Image(
    url=_STYLE_UPDATE_CANVAS_URL,
    gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(
      _STYLE_UPDATE_CANVAS_URL),
  )
  ref1 = models.Image(
    url=_STYLE_REFERENCE_IMAGE_URLS[0],
    gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(
      _STYLE_REFERENCE_IMAGE_URLS[0]),
  )
  ref2 = models.Image(
    url=_STYLE_REFERENCE_IMAGE_URLS[1],
    gcs_uri=cloud_storage.extract_gcs_uri_from_image_url(
      _STYLE_REFERENCE_IMAGE_URLS[1]),
  )
  return canvas, ref1, ref2


def generate_book_pages_style_update(  # pylint: disable=too-many-arguments
  *,
  setup_image: models.Image,
  punchline_image: models.Image,
  setup_text: str,
  punchline_text: str,
  output_file_name_base: str,
  additional_setup_instructions: str,
  additional_punchline_instructions: str,
  include_image_description: bool = True,
  add_print_margins: bool = True,
) -> _BookPageGenerationResult:
  """Generate book pages using simplified style-update flow."""
  del include_image_description
  generation_client = image_client.get_client(
    label='book_page_generation',
    model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
    file_name_base=output_file_name_base,
  )

  canvas_image, style_ref1, style_ref2 = _get_style_update_reference_images()

  simple_setup_image = _get_simple_book_page(
    setup_image,
    f"{output_file_name_base}_setup",
    add_print_margins=add_print_margins,
  )
  simple_punchline_image = _get_simple_book_page(
    punchline_image,
    f"{output_file_name_base}_punchline",
    add_print_margins=add_print_margins,
  )

  setup_prompt = _build_style_update_prompt(
    joke_text=setup_text,
    additional_instructions=additional_setup_instructions,
    include_setup_reference=False,
  )
  updated_setup_image = generation_client.generate_image(
    prompt=setup_prompt,
    reference_images=[
      setup_image,
      canvas_image,
      style_ref1,
      style_ref2,
    ],
  )

  punchline_prompt = _build_style_update_prompt(
    joke_text=punchline_text,
    additional_instructions=additional_punchline_instructions,
    include_setup_reference=True,
  )
  updated_punchline_image = generation_client.generate_image(
    prompt=punchline_prompt,
    reference_images=[
      updated_setup_image,
      punchline_image,
      canvas_image,
      style_ref1,
      style_ref2,
    ],
  )

  return _BookPageGenerationResult(
    simple_setup_image=simple_setup_image,
    simple_punchline_image=simple_punchline_image,
    generated_setup_image=updated_setup_image,
    generated_punchline_image=updated_punchline_image,
    setup_prompt=setup_prompt,
    punchline_prompt=punchline_prompt,
  )


def _get_simple_book_page(
  image_model: models.Image,
  output_file_name_base: str,
  add_print_margins: bool = True,
) -> models.Image:
  """Generate a 2048x2048 book page reference image.

  When add_print_margins is True, black margins are added for bleed. When it is
  False, the image is still rescaled to the target size without margins.
  """
  if not image_model.gcs_uri:
    raise ValueError(f"Image model {image_model} must have a GCS URI")

  image = cloud_storage.download_image_from_gcs(image_model.gcs_uri)

  target_size = 2048
  if add_print_margins:
    # Scale image to size without margins and add black margins around it
    outpaint_client = image_client.get_client(
      label='book_page_generation',
      model=image_client.ImageModel.DUMMY_OUTPAINTER,
      file_name_base=output_file_name_base,
    )
    margin_pixels = math.ceil(image.width * 0.1)
    max_margin = max(1, (target_size // 2) - 1)
    margin_pixels = min(margin_pixels, max_margin)
    inner_size = max(1, target_size - (margin_pixels * 2))
    upscaled_image = image.resize(
      (inner_size, inner_size),
      resample=Image.Resampling.LANCZOS,
    )
    simple_page_image = outpaint_client.outpaint_image(
      top=margin_pixels,
      bottom=margin_pixels,
      left=margin_pixels,
      right=margin_pixels,
      gcs_uri=cloud_storage.get_image_gcs_uri(output_file_name_base, "png"),
      pil_image=upscaled_image,
      save_to_firestore=False,
    )
    return simple_page_image
  if image.size == (target_size, target_size):
    # Image is already the target size, so return it as is
    return image_model

  # Scale image directly to target size, if needed
  resized_image = image.resize(
    (target_size, target_size),
    resample=Image.Resampling.LANCZOS,
  )
  gcs_uri = cloud_storage.get_image_gcs_uri(output_file_name_base, "png")
  uploaded_gcs_uri, _ = cloud_storage.upload_image_to_gcs(
    resized_image,
    output_file_name_base,
    "png",
    gcs_uri=gcs_uri,
  )
  return models.Image(
    gcs_uri=uploaded_gcs_uri,
    url=cloud_storage.get_final_image_url(uploaded_gcs_uri, width=target_size),
  )


def _convert_for_print_kdp(  # pylint: disable=too-many-arguments
  image: Image.Image,
  *,
  is_punchline: bool,
  page_number: int,
  total_pages: int,
  color_mode: str,
  image_editor_instance: image_editor.ImageEditor | None = None,
) -> bytes:
  """Convert an image to be print-ready for Kindle Direct Publishing.
  
  Conversion includes:
    1. Scale image to correct size at desired DPI.
    2. Trim the bleed area off of the inner edge.
    3. Convert to the target print color mode.
    4. Convert to JPEG.
  """
  editor = image_editor_instance or image_editor.ImageEditor()

  # Scale
  pre_trim_dimensions = _BOOK_PAGE_BASE_SIZE + (_BOOK_PAGE_BLEED_PX * 2)
  scaled_image = editor.scale_image(
    image,
    new_width=pre_trim_dimensions,
    new_height=pre_trim_dimensions,
  )

  # Remove inner bleed
  trim_left = 0
  trim_right = 0
  if is_punchline:
    trim_left = _BOOK_PAGE_BLEED_PX
  else:
    trim_right = _BOOK_PAGE_BLEED_PX

  trimmed_image = editor.trim_edges(
    image=scaled_image,
    left=trim_left,
    right=trim_right,
  )

  if page_number <= 0:
    raise ValueError('page_number must be positive')
  if total_pages <= 0:
    raise ValueError('total_pages must be positive')
  _ = _add_page_number_to_image(
    trimmed_image,
    page_number=page_number,
    total_pages=total_pages,
    is_punchline=is_punchline,
  )

  converted_image = trimmed_image.convert(color_mode)

  if abs(converted_image.width -
         _BOOK_PAGE_FINAL_WIDTH) > 2 or abs(converted_image.height -
                                            _BOOK_PAGE_FINAL_HEIGHT) > 2:
    raise ValueError(
      f"Expected image size {_BOOK_PAGE_FINAL_WIDTH}x{_BOOK_PAGE_FINAL_HEIGHT}, got {converted_image.width}x{converted_image.height}"
    )

  buffer = BytesIO()
  converted_image.save(
    buffer,
    format='JPEG',
    quality=100,
    subsampling=0,
    dpi=(300, 300),
  )
  return buffer.getvalue()


@lru_cache(maxsize=len(_PAGE_NUMBER_FONT_URLS))
def _load_page_number_font_bytes(url: str) -> bytes | None:
  """Download the Nunito font data from the given web font URL."""
  try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.content
  except requests.RequestException as exc:
    logger.error(f'Unable to download Nunito font from {url}: {exc}')
    return None


@lru_cache(maxsize=16)
def get_text_font(
    font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
  """Return a cached Nunito font instance for the requested size."""
  safe_size = max(1, font_size)
  for url in _PAGE_NUMBER_FONT_URLS:
    font_bytes = _load_page_number_font_bytes(url)
    if not font_bytes:
      continue
    try:
      font = ImageFont.truetype(BytesIO(font_bytes), safe_size)
      logger.info(f'Loaded Nunito font from {url} (size {safe_size})')
      return font
    except OSError as exc:  # pragma: no cover - unexpected font error
      logger.error(
        f'Unable to construct Nunito font from {url} (size {safe_size}): {exc}'
      )
  return ImageFont.load_default()


def _srgb_channel_to_linear(channel: float) -> float:
  if channel <= 0.04045:
    return channel / 12.92
  return ((channel + 0.055) / 1.055)**2.4


def _linear_channel_to_srgb(channel: float) -> int:
  if channel <= 0.0031308:
    srgb = channel * 12.92
  else:
    srgb = 1.055 * (channel**(1 / 2.4)) - 0.055
  srgb = min(max(srgb, 0.0), 1.0)
  return int(round(srgb * 255))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
  r = _srgb_channel_to_linear(rgb[0] / 255.0)
  g = _srgb_channel_to_linear(rgb[1] / 255.0)
  b = _srgb_channel_to_linear(rgb[2] / 255.0)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _adjust_color_to_target_luminance(
  rgb: tuple[int, int, int],
  target_luminance: float,
) -> tuple[int, int, int]:
  r = _srgb_channel_to_linear(rgb[0] / 255.0)
  g = _srgb_channel_to_linear(rgb[1] / 255.0)
  b = _srgb_channel_to_linear(rgb[2] / 255.0)
  base_luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

  if base_luminance <= 0:
    t = min(max(target_luminance, 0.0), 1.0)
    r = t
    g = t
    b = t
  elif target_luminance >= base_luminance:
    t = 0.0 if base_luminance >= 1 else (target_luminance -
                                         base_luminance) / (1 - base_luminance)
    r = r + t * (1 - r)
    g = g + t * (1 - g)
    b = b + t * (1 - b)
  else:
    scale = target_luminance / base_luminance
    r *= scale
    g *= scale
    b *= scale

  return (
    _linear_channel_to_srgb(r),
    _linear_channel_to_srgb(g),
    _linear_channel_to_srgb(b),
  )


def _pick_target_luminance(
  base_luminance: float,
  target_contrast_ratio: float,
) -> float:
  lighter = target_contrast_ratio * (base_luminance + 0.05) - 0.05
  darker = (base_luminance + 0.05) / target_contrast_ratio - 0.05
  candidates: list[float] = []
  if 0.0 <= lighter <= 1.0:
    candidates.append(lighter)
  if 0.0 <= darker <= 1.0:
    candidates.append(darker)
  if not candidates:
    if abs(lighter - base_luminance) < abs(darker - base_luminance):
      return min(max(lighter, 0.0), 1.0)
    return min(max(darker, 0.0), 1.0)
  return min(candidates, key=lambda value: abs(value - base_luminance))


def _get_joke_grid_divider_sample_offsets(panel_size: int) -> list[int]:
  if _PINTEREST_DIVIDER_SAMPLE_COUNT <= 1:
    return [panel_size // 2]
  return [
    int(round(index * (panel_size - 1) /
              (_PINTEREST_DIVIDER_SAMPLE_COUNT - 1)))
    for index in range(_PINTEREST_DIVIDER_SAMPLE_COUNT)
  ]


def _compute_joke_grid_divider_color(
  canvas: Image.Image,
  num_jokes: int,
) -> tuple[int, int, int] | None:
  if num_jokes < 2:
    return None

  canvas_rgb = canvas.convert('RGB') if canvas.mode != 'RGB' else canvas
  width, height = canvas_rgb.size
  panel_size = width // 2
  if panel_size <= 0:
    return None

  x_offsets = _get_joke_grid_divider_sample_offsets(panel_size)
  samples: list[tuple[int, int, int]] = []

  for row_index in range(1, num_jokes):
    boundary_y = row_index * panel_size
    y_top = boundary_y - 1
    y_bottom = boundary_y
    if y_top < 0 or y_bottom >= height:
      continue
    for panel_index in range(2):
      x_origin = panel_index * panel_size
      for x_offset in x_offsets:
        x = x_origin + x_offset
        if x >= width:
          continue
        top_pixel = canvas_rgb.getpixel((x, y_top))
        bottom_pixel = canvas_rgb.getpixel((x, y_bottom))
        if (isinstance(top_pixel, tuple) and len(top_pixel) >= 3
            and isinstance(bottom_pixel, tuple) and len(bottom_pixel) >= 3):
          samples.append(
            (int(top_pixel[0]), int(top_pixel[1]), int(top_pixel[2])))
          samples.append(
            (int(bottom_pixel[0]), int(bottom_pixel[1]), int(bottom_pixel[2])))

  if not samples:
    return None

  total_r = sum(color[0] for color in samples)
  total_g = sum(color[1] for color in samples)
  total_b = sum(color[2] for color in samples)
  count = len(samples)
  average = (
    int(round(total_r / count)),
    int(round(total_g / count)),
    int(round(total_b / count)),
  )
  base_luminance = _relative_luminance(average)
  target_luminance = _pick_target_luminance(
    base_luminance,
    _PINTEREST_DIVIDER_TARGET_CONTRAST,
  )
  return _adjust_color_to_target_luminance(average, target_luminance)


@lru_cache(maxsize=3)
def _get_social_background_4x5(background_url: str) -> Image.Image:
  """Fetch a 4:5 social background canvas image.

  Returns a PIL image at the background's native resolution.
  """
  return cloud_storage.download_image_from_gcs(background_url)


def _place_square_image_on_4x5_canvas(
  square_image: Image.Image,
  *,
  background_url: str,
) -> Image.Image:
  """Place a square image onto a 4:5 canvas with padding."""
  if square_image.mode != 'RGB':
    square_image = square_image.convert('RGB')
  square_image = square_image.resize(_SOCIAL_4X5_JOKE_IMAGE_SIZE_PX,
                                     Image.Resampling.LANCZOS)

  canvas = _get_social_background_4x5(background_url).resize(
    _SOCIAL_4X5_CANVAS_SIZE_PX,
    Image.Resampling.LANCZOS,
  )

  paste_x = (canvas.width - square_image.width) // 2
  paste_y = (canvas.height - square_image.height) // 2

  output = canvas.copy()
  output.paste(square_image, (paste_x, paste_y))
  return output


def create_joke_giraffe_image(jokes: list[models.PunnyJoke], ) -> Image.Image:
  """Create a tall 1024x(2048*num_jokes) image stacked by joke panels.

  Stacks the setup image on top of the punchline image for each joke,
  then repeats for subsequent jokes.

  Args:
    jokes: List of jokes to process.

  Returns:
    A single stacked PIL Image.

  Raises:
    ValueError: If the joke list is empty or any joke is missing image URLs.
  """
  if not jokes:
    raise ValueError("jokes must be a non-empty list")

  panel_size = _SOCIAL_4X5_JOKE_IMAGE_SIZE_PX[0]
  canvas_width = panel_size
  canvas_height = panel_size * 2 * len(jokes)
  canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

  for index, joke in enumerate(jokes):
    if not joke.setup_image_url or not joke.punchline_image_url:
      raise ValueError(
        f"Joke {joke.key or 'unknown'} is missing setup or punchline image URL"
      )

    setup_img = cloud_storage.download_image_from_gcs(joke.setup_image_url)
    punchline_img = cloud_storage.download_image_from_gcs(
      joke.punchline_image_url)

    if setup_img.mode != 'RGB':
      setup_img = setup_img.convert('RGB')
    if punchline_img.mode != 'RGB':
      punchline_img = punchline_img.convert('RGB')

    setup_img = setup_img.resize(
      (panel_size, panel_size),
      Image.Resampling.LANCZOS,
    )
    punchline_img = punchline_img.resize(
      (panel_size, panel_size),
      Image.Resampling.LANCZOS,
    )

    y_offset = index * panel_size * 2
    canvas.paste(setup_img, (0, y_offset))
    canvas.paste(punchline_img, (0, y_offset + panel_size))

  return canvas


def create_single_joke_images_4by5(
  jokes: list[models.PunnyJoke], ) -> list[Image.Image]:
  """Create 4:5 setup/punchline images by adding header/footer padding.

  Downloads each joke's square setup/punchline images, resizes each to
  1024x1024, and pastes them centered onto a 4:5 background canvas resized to
  1024x1280. Returns alternating setup and punchline images.

  Args:
    jokes: List of jokes to process.

  Returns:
    List of PIL Images in sequence: [joke1_setup, joke1_punchline,
    joke2_setup, joke2_punchline, ...]. Each image is 1024x1280 (4:5 ratio).

  Raises:
    ValueError: If any joke is missing setup or punchline image URL.
  """
  if not jokes:
    raise ValueError("jokes must be a non-empty list")

  result_images: list[Image.Image] = []

  last_index = len(jokes) - 1
  for index, joke in enumerate(jokes):
    if not joke.setup_image_url or not joke.punchline_image_url:
      raise ValueError(
        f"Joke {joke.key or 'unknown'} is missing setup or punchline image URL"
      )

    setup_img = cloud_storage.download_image_from_gcs(joke.setup_image_url)
    punchline_img = cloud_storage.download_image_from_gcs(
      joke.punchline_image_url)

    setup_result = _place_square_image_on_4x5_canvas(
      setup_img,
      background_url=_SOCIAL_BACKGROUND_4X5_SWIPE_REVEAL_URL,
    )
    punchline_background_url = _SOCIAL_BACKGROUND_4X5_SWIPE_MORE_URL
    if index == last_index:
      punchline_background_url = _SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL
    punchline_result = _place_square_image_on_4x5_canvas(
      punchline_img,
      background_url=punchline_background_url,
    )

    result_images.append(setup_result)
    result_images.append(punchline_result)

  return result_images


def create_joke_grid_image_3x2(
  *,
  joke_ids: list[str] | None = None,
  jokes: list[models.PunnyJoke] | None = None,
  block_last_panel: bool = True,
) -> Image.Image:
  """Create a 3x2 image for a joke grid social post. If more than 3 jokes are provided, the last 3 jokes are used."""
  num_jokes = 3
  return _create_joke_grid_image(
    joke_ids=joke_ids[-num_jokes:] if joke_ids else None,
    jokes=jokes[-num_jokes:] if jokes else None,
    block_last_panel=block_last_panel,
  )


def create_joke_grid_image_4by5(
  *,
  joke_ids: list[str] | None = None,
  jokes: list[models.PunnyJoke] | None = None,
  block_last_panel: bool = True,
) -> Image.Image:
  """Create a 4:5 image for a joke grid social post."""
  square_image = create_joke_grid_image_square(
    joke_ids=joke_ids,
    jokes=jokes,
    block_last_panel=block_last_panel,
  )
  return _place_square_image_on_4x5_canvas(
    square_image,
    background_url=_SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL,
  )


def create_joke_grid_image_square(
  *,
  joke_ids: list[str] | None = None,
  jokes: list[models.PunnyJoke] | None = None,
  block_last_panel: bool = True,
) -> Image.Image:
  """Create a square image for a joke grid social post. If more than 2 jokes are provided, the last 2 jokes are used."""
  num_jokes = 2
  return _create_joke_grid_image(
    joke_ids=joke_ids[-num_jokes:] if joke_ids else None,
    jokes=jokes[-num_jokes:] if jokes else None,
    block_last_panel=block_last_panel,
  )


def _create_joke_grid_image(  # pylint: disable=too-many-branches,too-many-statements
  *,
  joke_ids: list[str] | None = None,
  jokes: list[models.PunnyJoke] | None = None,
  block_last_panel: bool = True,
) -> Image.Image:
  """Create a Pinterest pin image from multiple jokes.
  
  Creates a single large image with all setup and punchline images arranged
  in rows. Each joke takes one row with setup on the left and punchline on
  the right. Each image is scaled to 500x500 pixels. Rows follow the order
  of the joke_ids input when provided, otherwise the jokes list order.
  
  Args:
    joke_ids: List of joke IDs to include in the pin image.
    jokes: Optional list of joke models to render (skips Firestore fetch).
    block_last_panel: If True, overlay a blocker image over the bottom right
      punchline panel. Defaults to True.
    
  Returns:
    A PIL Image with dimensions 1000x(n*500) where n is the number of jokes.
    
  Raises:
    ValueError: If any joke is missing or missing required images.
  """
  if jokes is None:
    if not joke_ids:
      raise ValueError("joke_ids must be a non-empty list")
    jokes = firestore.get_punny_jokes(joke_ids)
  elif not jokes:
    raise ValueError("jokes must be a non-empty list")

  ordered_jokes = list(jokes)
  if joke_ids:
    jokes_by_id = {joke.key: joke for joke in jokes if joke.key}
    missing = [joke_id for joke_id in joke_ids if joke_id not in jokes_by_id]
    if missing:
      raise ValueError(f"Jokes not found: {missing}")
    ordered_jokes = [jokes_by_id[joke_id] for joke_id in joke_ids]

  # Verify all jokes have images
  for joke in ordered_jokes:
    if not joke.setup_image_url or not joke.punchline_image_url:
      raise ValueError(f"Joke {joke.key} is missing setup or punchline image")

  num_jokes = len(ordered_jokes)
  canvas_width = _PINTEREST_PANEL_SIZE_PX * 2
  canvas_height = num_jokes * _PINTEREST_PANEL_SIZE_PX

  # Create blank white canvas
  canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

  for row_index, joke in enumerate(ordered_jokes):
    y_offset = row_index * _PINTEREST_PANEL_SIZE_PX

    setup_url = joke.setup_image_url
    punchline_url = joke.punchline_image_url
    if not isinstance(setup_url, str) or not isinstance(punchline_url, str):
      raise ValueError(f"Joke {joke.key} is missing setup or punchline image")

    # Download and process setup image
    setup_img = cloud_storage.download_image_from_gcs(setup_url)
    setup_img = setup_img.resize(
      (_PINTEREST_PANEL_SIZE_PX, _PINTEREST_PANEL_SIZE_PX),
      Image.Resampling.LANCZOS)

    # Download and process punchline image
    punchline_img = cloud_storage.download_image_from_gcs(punchline_url)
    punchline_img = punchline_img.resize(
      (_PINTEREST_PANEL_SIZE_PX, _PINTEREST_PANEL_SIZE_PX),
      Image.Resampling.LANCZOS)

    # Paste setup on left (x=0), punchline on right (x=500)
    canvas.paste(setup_img, (0, y_offset))
    canvas.paste(punchline_img, (_PINTEREST_PANEL_SIZE_PX, y_offset))

  divider_color = _compute_joke_grid_divider_color(canvas, num_jokes)
  if divider_color and num_jokes > 1:
    draw = ImageDraw.Draw(canvas)
    for row_index in range(1, num_jokes):
      boundary_y = row_index * _PINTEREST_PANEL_SIZE_PX
      draw.line((0, boundary_y - 1, canvas_width - 1, boundary_y - 1),
                fill=divider_color,
                width=1)
      draw.line((0, boundary_y, canvas_width - 1, boundary_y),
                fill=divider_color,
                width=1)

  # Overlay blocker image on bottom right punchline if requested
  if block_last_panel and num_jokes > 0:
    blocker_img = cloud_storage.download_image_from_gcs(
      _PANEL_BLOCKER_OVERLAY_URL_POST_IT)
    # Ensure blocker image is RGBA for alpha transparency
    if blocker_img.mode != 'RGBA':
      blocker_img = blocker_img.convert('RGBA')

    blocker_img = blocker_img.resize(
      (_PINTEREST_PANEL_SIZE_PX, _PINTEREST_PANEL_SIZE_PX),
      Image.Resampling.LANCZOS)
    overlay_x = _PINTEREST_PANEL_SIZE_PX
    overlay_y = (num_jokes - 1) * _PINTEREST_PANEL_SIZE_PX
    # Convert canvas to RGBA for alpha compositing
    canvas = canvas.convert('RGBA')
    # Create full-size transparent overlay for proper alpha compositing
    overlay = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    # Paste RGBA blocker image - alpha channel will be used automatically
    overlay.paste(blocker_img, (overlay_x, overlay_y))
    # Alpha composite the overlay onto the canvas
    canvas = Image.alpha_composite(canvas, overlay)
    # Convert back to RGB
    canvas = canvas.convert('RGB')

  return canvas


def _add_page_number_to_image(
  image: Image.Image,
  *,
  page_number: int,
  total_pages: int,
  is_punchline: bool,
) -> Image.Image:
  """Render the page number text near the page corner."""
  if page_number <= 0 or total_pages <= 0:
    return image

  width, height = image.size
  if width == 0 or height == 0:
    return image

  draw = ImageDraw.Draw(image)
  font = get_text_font(_PAGE_NUMBER_FONT_SIZE)
  stroke_width = max(
    1, int(round(_PAGE_NUMBER_FONT_SIZE * _PAGE_NUMBER_STROKE_RATIO)))
  text = str(page_number)
  text_bbox = draw.textbbox(
    (0, 0),
    text,
    font=font,
    stroke_width=stroke_width,
  )
  text_width = text_bbox[2] - text_bbox[0]
  text_height = text_bbox[3] - text_bbox[1]

  offset_from_edge = int(round(_BOOK_PAGE_BLEED_PX * 3.5))
  text_x: float
  if is_punchline:
    text_x = offset_from_edge
  else:
    text_x = width - offset_from_edge - text_width
  text_y = height - offset_from_edge - text_height

  text_x = max(0, text_x)
  text_y = max(0, text_y)

  draw.text(
    (text_x, text_y),
    text,
    fill=_PAGE_NUMBER_TEXT_COLOR,
    font=font,
    stroke_width=stroke_width,
    stroke_fill=_PAGE_NUMBER_STROKE_COLOR,
  )
  return image


def _compose_landscape_ad_image(
  editor: image_editor.ImageEditor,
  setup_image: Image.Image,
  punchline_image: Image.Image,
) -> tuple[Image.Image, int]:
  """Create a 2048x1024 landscape PNG of the setup/punchline images."""
  base = editor.create_blank_image(_AD_LANDSCAPE_CANVAS_WIDTH,
                                   _AD_LANDSCAPE_CANVAS_HEIGHT)
  half_width = _AD_LANDSCAPE_CANVAS_WIDTH // 2
  setup_scaled = editor.scale_image(
    setup_image,
    new_width=half_width,
    new_height=_AD_LANDSCAPE_CANVAS_HEIGHT,
  )
  punchline_scaled = editor.scale_image(
    punchline_image,
    new_width=half_width,
    new_height=_AD_LANDSCAPE_CANVAS_HEIGHT,
  )

  base = editor.paste_image(base, setup_scaled, 0, 0)
  base = editor.paste_image(base, punchline_scaled, half_width, 0)

  return base, base.width


def _compose_square_drawing_ad_image(
  editor: image_editor.ImageEditor,
  setup_image: Image.Image,
  punchline_image: Image.Image,
  background_uri: str,
) -> tuple[Image.Image, int]:
  """Create a 1200x1200 square PNG with background and post-it style shadows."""
  # Load the portrait background image from GCS
  base = cloud_storage.download_image_from_gcs(background_uri)

  # Paste punchline image first so it's below the setup image
  # Transform punchline image
  punchline_scaled = editor.scale_image(
    punchline_image,
    new_width=_AD_SQUARE_JOKE_IMAGE_SIZE_PX,
    new_height=_AD_SQUARE_JOKE_IMAGE_SIZE_PX,
  )
  punchline_rotated = editor.rotate_image(punchline_scaled, -2)
  # Paste roughly bottom-right (diagonally opposed)
  base = editor.paste_image(base, punchline_rotated, 470, 635, add_shadow=True)

  # Transform setup image
  setup_scaled = editor.scale_image(
    setup_image,
    new_width=_AD_SQUARE_JOKE_IMAGE_SIZE_PX,
    new_height=_AD_SQUARE_JOKE_IMAGE_SIZE_PX,
  )
  setup_rotated = editor.rotate_image(setup_scaled, 5)
  # Paste near top-left
  base = editor.paste_image(base, setup_rotated, 190, 35, add_shadow=True)

  return base, base.width
