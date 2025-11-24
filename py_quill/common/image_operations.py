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

_BOOK_PAGE_STYLE_REFERENCE_IMAGE_URI = "https://storage.googleapis.com/images.quillsstorybook.com/_joke_assets/book_page_reference_image_1024.jpg"

_BOOK_PAGE_BASE_SIZE = 1800
_BOOK_PAGE_BLEED_PX = 38
_BOOK_PAGE_FINAL_WIDTH = _BOOK_PAGE_BASE_SIZE + _BOOK_PAGE_BLEED_PX
_BOOK_PAGE_FINAL_HEIGHT = _BOOK_PAGE_BASE_SIZE + (_BOOK_PAGE_BLEED_PX * 2)


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
    setup_img_url = metadata.get('book_page_setup_image_url')
    punchline_img_url = metadata.get('book_page_punchline_image_url')
    if not setup_img_url or not punchline_img_url:
      raise ValueError(f"Joke {joke_id} does not have book page images")

    setup_image = cloud_storage.download_image_from_gcs(setup_img_url)
    punchline_image = cloud_storage.download_image_from_gcs(punchline_img_url)

    setup_bytes = _convert_for_print_kdp(setup_image, is_punchline=False)
    punchline_bytes = _convert_for_print_kdp(punchline_image,
                                             is_punchline=True)

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

  Returns:
      The setup and punchline book page images.

  Raises:
      ValueError: If the joke is not found or is missing required image URLs.
  """
  logger.info(f'Creating book pages for joke {joke_id}')

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
      return existing_setup, existing_punchline

  setup_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.setup_image_url)
  punchline_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    joke.punchline_image_url)
  logger.info(
    f"Processing original images: {setup_gcs_uri} and {punchline_gcs_uri}")

  setup_image = cloud_storage.download_image_from_gcs(setup_gcs_uri)
  punchline_image = cloud_storage.download_image_from_gcs(punchline_gcs_uri)

  style_reference_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    _BOOK_PAGE_STYLE_REFERENCE_IMAGE_URI)
  style_reference_image = cloud_storage.download_image_from_gcs(
    style_reference_gcs_uri)
  generation_result = generate_book_pages_with_nano_banana_pro(
    setup_image=setup_image,
    punchline_image=punchline_image,
    style_reference_image=style_reference_image,
    setup_image_description=joke.setup_image_description,
    punchline_image_description=joke.punchline_image_description,
    output_file_name_base=f'{joke_id}_book_page',
    additional_setup_instructions=additional_setup_instructions,
    additional_punchline_instructions=additional_punchline_instructions,
  )

  metadata_book_page_updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    metadata_data,
    generation_result.generated_setup_image.url,
    generation_result.generated_punchline_image.url,
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


_BOOK_PAGE_PROMPT_TEMPLATE = """
{intro}

Generate a new, polished version of the CONTENT image that is seamlessly extended through the black bleed margins and adheres to the art style defined below.

Art style:
Create a professional-quality children's book illustration in the style of soft-core colored pencils on medium-tooth paper. The artwork must feature organic, sketch-like outlines rendered in a darker, saturated shade of the subject's fill color (e.g., deep orange lines for yellow fur, dark indigo for blue water), strictly avoiding black ink or graphite contours. Use visible directional strokes and tight cross-hatching to build up color saturation layer by layer. The look should be rich and vibrant, yet retain the individual stroke texture, ensuring the white of the paper peeks through slightly to create warmth without looking messy, patchy, or unfinished. The image must be fully rendered in full color across the entire scene—backgrounds must be detailed and finished, not monochromatic or vignette-style. Subject proportions should follow a cute, chibi style (oversized heads, large expressive eyes with highlights, small bodies), resulting in an aesthetic that feels tactile and hand-crafted, yet polished enough for high-quality printing.

 Your new image must:
  - Show the exact same words as the CONTENT image.
  - Use the exact same scene, composition, and camera angle as the CONTENT image. The main characters, their poses and positioning, expressions, etc. MUST be identical. You may ONLY make the following changes:
    - Fix mistakes/errors, such as anatomical errors on the characters, objects, etc.
    - Fix inconsistencies in the font, e.g. if some or all of the text are in cursive, different fonts, different colors, etc., convert the text to match the text font/color/style of the reference image.
    - Add details to the main characters/objects to make them more polished, complete, and visually appealing, but be sure to respect the artistic style of a child-like colored pencil drawing.
    - Seamlessly extend the image (both canvas and drawing) into the black margins. Some/all of this area will be trimmed off during printing, so make sure these elements are not critical to the joke. The goal is to use this margin as bleed for printing.
    - Add/remove/change the supporting foreground/background elements to make the image make sense and be more visually appealing.
    - If the CONTENT image has a lot of empty space, add supporting foreground/background elements to fill it. Make sure these elements play a supporting role and do not conflict with the main subject.
  - All text and major elements must be outside of the bleed area.
  - Be drawn on the same textured paper canvas as the reference image.
  - The final image must make sense. If there are any supporting elemments in the CONTENT image that get in the way of your bleed margin expansion, you may change them to make the image make sense.
{additional_requirements}

{{additional_instructions}}

Here is the description for the CONTENT image. You must follow this description exactly:
{{image_description}}

First, think deeply about the following:
  - What is the composition of the CONTENT image? What are the main subjects, supporting elements, and background elements? What is the camera angle and perspective? What effect and emotion is the artist trying to convey?
  - What are the crucial elements of the CONTENT image that must be preserved in the final image?
  - Does the CONTENT image already adhere to the art style described above? If not, what changes need to be made?
  - Does the CONTENT image contain any mistakes or errors? If so, how can they be fixed in the final image?
    - Example: Anatomical errors on the characters
    - Example: Incorrectly or poorly drawn objects
    - Example: Inconsistencies with the given image description
{additional_thinking}

Then, generate the final image, which should be high quality, professional-looking copy of the CONTENT image, suitable for a children's picture book, and print ready with appropriate bleed margins.
"""

_BOOK_PAGE_SETUP_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given 2 images. The first is a an illustration of the setup line of a two-liner joke, and the second image is a style reference image:

  - A CONTENT image of a drawing with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the setup of the joke.

  - A STYLE reference image of a super cute drawing of a construction worker cat on textured paper. This is an example for you to visualize the desired art style described below. Use this image ONLY as reference for:
    - Art style: Super cute colored pencil drawing, with a clear main subject, and supporting/background elements that extend to the edge of the canvas.
    - Canvas/background: Off-white textured paper
    - Font: Clean "handwritten" style
    - Overall aesthetic: Super cute and silly
""",
  additional_requirements="",
  additional_thinking="""
  - Is the CONTENT image missing any supporting foreground/background elements, or does any existing ones need to be enhanced to make the image more visually appealing?
""",
)

_BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE = _BOOK_PAGE_PROMPT_TEMPLATE.format(
  intro=
  """You are given 2 images that form a two-panel illustration of a two-liner joke:

  - A SETUP reference image that visualizes the 1st panel: the setup line of the joke. Use this image as consistency reference for:
    - Any recurring characters, objects, and scenes.
    - Art style: Super cute colored pencil drawing, with a clear main subject, and supporting/background elements that extend to the edge of the canvas.
    - Canvas/background: Off-white textured paper
    - Font: Clean "handwritten" style
    - Overall aesthetic: Super cute and silly

  - A CONTENT image of a drawing with text with black margins all around it. The black margins represent the bleed area for printing. This image visualizes the punchline of the joke.
  """,
  additional_requirements="""
  - Any recurring characters or elements from the SETUP image must be consistent with the SETUP image.
""",
  additional_thinking="""
  - Does the CONTENT image take place in the same setting as the SETUP image? If it's not clear from the images, think about whether it should based on the joke and context. If so, are the view and perspective exactly the same or different?
  - What elements of the SETUP image are (or should be) present in the CONTENT image? For each, are they viewed from exactly the same angle/perspective? Which parts should be visible in the CONTENT image?
""",
)


@dataclass(frozen=True)
class _BookPageGenerationResult:

  simple_setup_image: models.Image
  simple_punchline_image: models.Image
  generated_setup_image: models.Image
  generated_punchline_image: models.Image


def generate_book_pages_with_nano_banana_pro(
  *,
  setup_image: Image.Image,
  punchline_image: Image.Image,
  style_reference_image: Image.Image,
  setup_image_description: str,
  punchline_image_description: str,
  output_file_name_base: str,
  additional_setup_instructions: str,
  additional_punchline_instructions: str,
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

  simple_setup_image = _get_simple_book_page(
    setup_image,
    f"{output_file_name_base}_setup",
  )
  generated_setup_image = generation_client.generate_image(
    prompt=_BOOK_PAGE_SETUP_PROMPT_TEMPLATE.format(
      image_description=setup_image_description,
      additional_instructions=_format_additional_instructions(
        additional_setup_instructions)),
    reference_images=[simple_setup_image, style_reference_image],
  )

  simple_punchline_image = _get_simple_book_page(
    punchline_image,
    f"{output_file_name_base}_punchline",
  )
  generated_punchline_image = generation_client.generate_image(
    prompt=_BOOK_PAGE_PUNCHLINE_PROMPT_TEMPLATE.format(
      image_description=punchline_image_description,
      additional_instructions=_format_additional_instructions(
        additional_punchline_instructions)),
    reference_images=[generated_setup_image, simple_punchline_image],
  )

  return _BookPageGenerationResult(
    simple_setup_image=simple_setup_image,
    simple_punchline_image=simple_punchline_image,
    generated_setup_image=generated_setup_image,
    generated_punchline_image=generated_punchline_image,
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


def _get_simple_book_page(
  image: Image.Image,
  output_file_name_base: str,
) -> models.Image:
  """Generates a naively upscaled book page image with black margins."""
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
  is_punchline: bool,
  image_editor_instance: image_editor.ImageEditor | None = None,
) -> bytes:
  """Convert an image to be print-ready for Kindle Direct Publishing.
  
  Conversion includes:
    1. Scale image to correct size at desired DPI.
    2. Trim the bleed area off of the inner edge.
    3. Convert to CMYK.
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

  cmyk_image = trimmed_image.convert('CMYK')

  if abs(cmyk_image.width -
         _BOOK_PAGE_FINAL_WIDTH) > 2 or abs(cmyk_image.height -
                                            _BOOK_PAGE_FINAL_HEIGHT) > 2:
    raise ValueError(
      f"Expected image size {_BOOK_PAGE_FINAL_WIDTH}x{_BOOK_PAGE_FINAL_HEIGHT}, got {cmyk_image.width}x{cmyk_image.height}"
    )

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
