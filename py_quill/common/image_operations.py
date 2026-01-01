"""Image operations built on top of the PIL-based image editor."""

from __future__ import annotations

import datetime
import math
import zipfile
from dataclasses import dataclass
from functools import lru_cache, partial
from io import BytesIO
from typing import Callable

import requests
from agents import constants
from common import config, models
from firebase_functions import logger
from PIL import Image, ImageDraw, ImageFont
from services import cloud_storage, firestore, image_client, image_editor

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


def zip_joke_page_images_for_kdp(joke_ids: list[str]) -> str:
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
  total_pages = len(joke_ids) * 2
  current_page_number = 1

  # Add a blank intro page as page 002 before any joke pages.
  intro_bytes = create_blank_book_cover(color_mode=_KDP_PRINT_COLOR_MODE)
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
    setup_img_url = metadata.get('book_page_setup_image_url')
    punchline_img_url = metadata.get('book_page_punchline_image_url')
    if not setup_img_url or not punchline_img_url:
      raise ValueError(f"Joke {joke_id} does not have book page images")

    setup_image = cloud_storage.download_image_from_gcs(setup_img_url)
    punchline_image = cloud_storage.download_image_from_gcs(punchline_img_url)

    setup_bytes = _convert_for_print_kdp(
      setup_image,
      is_punchline=False,
      page_number=current_page_number,
      total_pages=total_pages,
      color_mode=_KDP_PRINT_COLOR_MODE,
    )
    current_page_number += 1
    punchline_bytes = _convert_for_print_kdp(
      punchline_image,
      is_punchline=True,
      page_number=current_page_number,
      total_pages=total_pages,
      color_mode=_KDP_PRINT_COLOR_MODE,
    )
    current_page_number += 1

    setup_file_name = f"{page_index:03d}_{joke_id}_setup.jpg"
    page_index += 1
    punchline_file_name = f"{page_index:03d}_{joke_id}_punchline.jpg"
    page_index += 1
    files.append((setup_file_name, setup_bytes))
    files.append((punchline_file_name, punchline_bytes))

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
  To preserve the full joke artwork we first outpaint each source image by
  adding 5% margin on every side and, on edges that require bleed, enough extra
  canvas so that the final trimmed image still has 38 pixels of bleed. The
  outpainted result is then upscaled by 2x before being scaled back down to the
  exact 1838x1876 print dimensions.

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

  metadata_ref = (firestore.db().collection('jokes').document(
    joke_id).collection('metadata').document('metadata'))
  metadata_snapshot = metadata_ref.get()
  metadata_data: dict[str, object] = {}
  if metadata_snapshot.exists:
    metadata_data = metadata_snapshot.to_dict() or {}

  base_setup_url = joke.setup_image_url
  base_punchline_url = joke.punchline_image_url
  if base_image_source == 'book_page':
    meta_setup = metadata_data.get('book_page_setup_image_url')
    meta_punchline = metadata_data.get('book_page_punchline_image_url')
    base_setup_url = meta_setup or base_setup_url
    base_punchline_url = meta_punchline or base_punchline_url

  if not base_setup_url or not base_punchline_url:
    raise ValueError(
      f'Joke {joke_id} does not have image URLs for base_image_source {base_image_source}'
    )

  if not overwrite:
    existing_setup = metadata_data.get('book_page_setup_image_url')
    existing_punchline = metadata_data.get('book_page_punchline_image_url')
    if (isinstance(existing_setup, str) and existing_setup
        and isinstance(existing_punchline, str) and existing_punchline):
      return existing_setup, existing_punchline

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
      setup_image_description=joke.setup_image_description,
      punchline_image_description=joke.punchline_image_description,
      output_file_name_base=f'{joke_id}_book_page',
      additional_setup_instructions=additional_setup_instructions,
      additional_punchline_instructions=additional_punchline_instructions,
    )

  metadata_book_page_updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    existing_metadata=metadata_data,
    new_setup_page_url=generation_result.generated_setup_image.url,
    new_punchline_page_url=generation_result.generated_punchline_image.url,
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
  firestore.update_punny_joke(
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
Create a professional-quality children's book illustration in the style of soft-core colored pencils on medium-tooth paper. The artwork must feature organic, sketch-like outlines rendered in a darker, saturated shade of the subject's fill color (e.g., deep orange lines for yellow fur, dark indigo for blue water), strictly avoiding black ink or graphite contours. Use visible directional strokes and tight cross-hatching to build up color saturation layer by layer. The look should be rich and vibrant, yet retain the individual stroke texture, ensuring the white of the paper peeks through slightly to create warmth without looking messy, patchy, or unfinished. The image must be fully rendered in full color across the entire scene—backgrounds must be detailed and finished, not monochromatic or vignette-style. Subject proportions should follow a cute, chibi style (oversized heads, large expressive eyes with highlights, small bodies), resulting in an aesthetic that feels tactile and hand-crafted, yet polished enough for high-quality printing.

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


def generate_book_pages_with_nano_banana_pro(
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


def generate_book_pages_style_update(
  *,
  setup_image: models.Image,
  punchline_image: models.Image,
  setup_text: str,
  punchline_text: str,
  output_file_name_base: str,
  additional_setup_instructions: str,
  additional_punchline_instructions: str,
  include_image_description: bool = True,
) -> _BookPageGenerationResult:
  """Generate book pages using simplified style-update flow."""
  generation_client = image_client.get_client(
    label='book_page_generation',
    model=image_client.ImageModel.GEMINI_NANO_BANANA_PRO,
    file_name_base=output_file_name_base,
  )

  canvas_image, style_ref1, style_ref2 = _get_style_update_reference_images()

  simple_setup_image = _get_simple_book_page(
    setup_image,
    f"{output_file_name_base}_setup",
  )
  simple_punchline_image = _get_simple_book_page(
    punchline_image,
    f"{output_file_name_base}_punchline",
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
) -> models.Image:
  """Generates a naively upscaled book page image with black margins."""
  if not image_model.gcs_uri:
    raise ValueError(f"Image model {image_model} must have a GCS URI")

  image = cloud_storage.download_image_from_gcs(image_model.gcs_uri)

  outpaint_client = image_client.get_client(
    label='book_page_generation',
    model=image_client.ImageModel.DUMMY_OUTPAINTER,
    file_name_base=output_file_name_base,
  )
  margin_pixels = math.ceil(image.width * 0.1)
  target_size = 2048 - margin_pixels
  upscaled_image = image.resize(
    (target_size, target_size),
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


def _convert_for_print_kdp(
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
    trim_right = 38

  trimmed_image = editor.trim_edges(
    image=scaled_image,
    left=trim_left,
    right=trim_right,
  )

  if page_number <= 0:
    raise ValueError('page_number must be positive')
  if total_pages <= 0:
    raise ValueError('total_pages must be positive')
  _add_page_number_to_image(
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
def _get_page_number_font(font_size: int) -> ImageFont.ImageFont:
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
  font = _get_page_number_font(_PAGE_NUMBER_FONT_SIZE)
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

  offset_from_edge = _BOOK_PAGE_BLEED_PX * 3
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
) -> tuple[bytes, int]:
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

  buffer = BytesIO()
  base.save(buffer, format='PNG')
  return buffer.getvalue(), base.width
