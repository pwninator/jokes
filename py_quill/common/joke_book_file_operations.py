"""Joke-book export file operations."""

from __future__ import annotations

import datetime
import importlib
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import Any, cast

import requests
from common import amazon_redirect, book_defs, models
from firebase_functions import logger
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.document import DocumentReference
from PIL import Image, ImageDraw, ImageFont
from services import cloud_storage, firestore, image_editor, pdf_client

_KDP_PRINT_COLOR_MODE = 'RGB'

_PAGE_NUMBER_FONT_URLS = (
  'https://github.com/googlefonts/nunito/raw/4be812cf4761b3ddc3b0ae894ef40ea21dcf6ff3/fonts/TTF/Nunito-Regular.ttf',
  'https://github.com/googlefonts/nunito/raw/refs/heads/main/fonts/variable/Nunito%5Bwght%5D.ttf',
)
_PAGE_NUMBER_STROKE_RATIO = 0.14
_PAGE_NUMBER_TEXT_COLOR = (33, 33, 33)
_PAGE_NUMBER_STROKE_COLOR = (255, 255, 255)

_BOOK_PAGE_ABOUT_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/book/999_about_page_template.png"
)

_PAPERBACK_SIZE_INCHES = 6.0
_PAGE_NUMBER_FONT_SIZE_RATIO = 0.2 / _PAPERBACK_SIZE_INCHES
_QR_CODE_CTA_FONT_SIZE_RATIO = 0.2 / _PAPERBACK_SIZE_INCHES
_PAGE_NUMBER_EDGE_OFFSET_RATIO = 0.4375 / _PAPERBACK_SIZE_INCHES
_BOOK_REVIEW_QR_X_RATIO = 1.35 / _PAPERBACK_SIZE_INCHES
_BOOK_REVIEW_QR_Y_RATIO = 4.45 / _PAPERBACK_SIZE_INCHES
_BOOK_REVIEW_QR_SIZE_RATIO = 1.0 / _PAPERBACK_SIZE_INCHES
_BOOK_REVIEW_QR_LABEL_MARGIN_TOP_RATIO = 0.01 / _PAPERBACK_SIZE_INCHES


@dataclass()
class BookPage:
  """One rendered book page plus its optional PDF hyperlink."""

  file_name: str
  image: Image.Image
  page_number: int | None = None
  hyperlink: pdf_client.HyperlinkSpec | None = None
  _image_bytes: bytes | None = None

  @property
  def image_bytes(self) -> bytes:
    """Return the image bytes if not already cached."""
    if not self._image_bytes:
      raise ValueError(f"Image bytes not encoded for page {self.file_name}")
    return self._image_bytes

  def encode(self,
             profile: BookExportProfile,
             color_mode: str = _KDP_PRINT_COLOR_MODE) -> None:
    """Encode the page image into JPEG bytes."""
    self._image_bytes = _convert_image_to_export_bytes(
      self.image,
      profile=profile,
      color_mode=color_mode,
    )

  def close(self) -> None:
    """Release any image resources owned by this page."""
    self.image.close()

  def trim(self, *, trim_left: int, trim_right: int) -> None:
    """Trim the page image and shift its hyperlink into final coordinates."""
    if trim_left < 0 or trim_right < 0:
      raise ValueError('trim_left and trim_right must be non-negative')
    if trim_left == 0 and trim_right == 0:
      return

    editor = image_editor.ImageEditor()
    trimmed_image = editor.trim_edges(
      image=self.image,
      left=trim_left,
      right=trim_right,
    )
    if trimmed_image is not self.image:
      self.image.close()
      self.image = trimmed_image

    if self.hyperlink and trim_left:
      self.hyperlink = pdf_client.HyperlinkSpec(
        url=self.hyperlink.url,
        x1=max(0, self.hyperlink.x1 - trim_left),
        y1=self.hyperlink.y1,
        x2=max(0, self.hyperlink.x2 - trim_left),
        y2=self.hyperlink.y2,
      )


@dataclass(frozen=True)
class JokeBookExportFiles:
  """Public URLs for generated joke-book export files."""

  zip_url: str | None
  paperback_pdf_url: str
  ebook_pdf_url: str


@dataclass(frozen=True)
class BookExportProfile:
  """Rendering configuration for one joke-book export format."""

  name: str
  output_base_size_px: tuple[int, int]
  output_bleed_size_px: int
  jpeg_quality: int
  jpeg_subsampling: int
  jpeg_progressive: bool
  review_book_format: book_defs.BookFormat
  qr_label: str

  @property
  def pre_trim_width_px(self) -> int:
    """Return the scaled square width before inner-edge trimming."""
    return self.output_base_size_px[0] + (self.output_bleed_size_px * 2)

  @property
  def pre_trim_height_px(self) -> int:
    """Return the scaled square height before inner-edge trimming."""
    return self.output_base_size_px[1] + (self.output_bleed_size_px * 2)

  @property
  def final_width_px(self) -> int:
    """Return the final page width after inner-edge trimming."""
    return self.output_base_size_px[0] + self.output_bleed_size_px

  @property
  def final_height_px(self) -> int:
    """Return the final page height after trimming."""
    return self.output_base_size_px[1] + (self.output_bleed_size_px * 2)

  @property
  def requires_trimming(self) -> bool:
    """Return True if the profile requires trimming."""
    return self.output_bleed_size_px > 0

  @property
  def page_number_font_size_px(self) -> int:
    """Return the profile-scaled page-number font size."""
    return max(
      1, int(round(self.pre_trim_width_px * _PAGE_NUMBER_FONT_SIZE_RATIO)))

  @property
  def qr_label_font_size_px(self) -> int:
    """Return the profile-scaled QR CTA font size."""
    return max(
      1, int(round(self.pre_trim_width_px * _QR_CODE_CTA_FONT_SIZE_RATIO)))

  @property
  def page_number_offset_px(self) -> int:
    """Return the offset from the page's outer edge for page numbers."""
    return max(
      1,
      int(round(self.pre_trim_width_px * _PAGE_NUMBER_EDGE_OFFSET_RATIO)),
    )

  @property
  def qr_x_px(self) -> int:
    """Return the QR left position in pre-trim pixels."""
    return int(round(self.pre_trim_width_px * _BOOK_REVIEW_QR_X_RATIO))

  @property
  def qr_y_px(self) -> int:
    """Return the QR top position in pre-trim pixels."""
    return int(round(self.pre_trim_height_px * _BOOK_REVIEW_QR_Y_RATIO))

  @property
  def qr_size_px(self) -> int:
    """Return the square QR size in pixels for this profile."""
    return max(
      1,
      int(
        round(
          min(self.pre_trim_width_px, self.pre_trim_height_px) *
          _BOOK_REVIEW_QR_SIZE_RATIO)),
    )

  @property
  def qr_label_margin_top_px(self) -> int:
    """Return the vertical gap between the QR and CTA label."""
    return max(
      1,
      int(
        round(self.pre_trim_height_px *
              _BOOK_REVIEW_QR_LABEL_MARGIN_TOP_RATIO)),
    )


_PAPERBACK_EXPORT_PROFILE = BookExportProfile(
  name='paperback',
  output_base_size_px=(1800, 1800),
  output_bleed_size_px=38,
  jpeg_quality=100,
  jpeg_subsampling=0,
  jpeg_progressive=True,
  review_book_format=book_defs.BookFormat.PAPERBACK,
  qr_label="Scan me!",
)
_EBOOK_EXPORT_PROFILE = BookExportProfile(
  name='ebook',
  output_base_size_px=(700, 700),
  output_bleed_size_px=0,
  jpeg_quality=70,
  jpeg_subsampling=2,
  jpeg_progressive=True,
  review_book_format=book_defs.BookFormat.EBOOK,
  qr_label="Tap me!",
)


class _BookPageTextDrawer:
  """Measures and draws styled text onto a single book page image."""

  def __init__(
    self,
    image: Image.Image,
    *,
    text: str,
    font_size: int,
  ):
    self._draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
    self.text: str = text
    self.font: ImageFont.FreeTypeFont | ImageFont.ImageFont = get_text_font(
      font_size)
    self.stroke_width: int = max(
      1, int(round(font_size * _PAGE_NUMBER_STROKE_RATIO)))
    self._bbox: tuple[int, int, int, int] | None = None

  @property
  def bbox(self) -> tuple[int, int, int, int]:
    """Return the cached text bounding box."""
    if self._bbox is None:
      text_bbox = self._draw.textbbox(
        (0, 0),
        self.text,
        font=self.font,
        stroke_width=self.stroke_width,
      )
      self._bbox = (
        int(text_bbox[0]),
        int(text_bbox[1]),
        int(text_bbox[2]),
        int(text_bbox[3]),
      )
    return self._bbox

  @property
  def width(self) -> int:
    """Return the rendered text width in pixels."""
    return self.bbox[2] - self.bbox[0]

  @property
  def height(self) -> int:
    """Return the rendered text height in pixels."""
    return self.bbox[3] - self.bbox[1]

  def draw_text(self, *, x: float, y: float) -> None:
    """Draw the text at the provided coordinates."""
    self._draw.text(
      (x, y),
      self.text,
      fill=_PAGE_NUMBER_TEXT_COLOR,
      font=self.font,
      stroke_width=self.stroke_width,
      stroke_fill=_PAGE_NUMBER_STROKE_COLOR,
    )


def export_joke_book_files(
  book: models.JokeBook,
  *,
  export_zip_paperback: bool = False,
) -> JokeBookExportFiles:
  """Create and store the paperback/ebook PDF exports for a joke book."""

  paperback_pages: list[BookPage] = []
  ebook_pages: list[BookPage] = []
  try:
    paperback_pages = _build_book_export_pages(
      book,
      profile=_PAPERBACK_EXPORT_PROFILE,
    )
    ebook_pages = _build_book_export_pages(
      book,
      profile=_EBOOK_EXPORT_PROFILE,
    )

    paperback_pdf_bytes = pdf_client.create_pdf(
      [(page.image_bytes, page.hyperlink) for page in paperback_pages],
      dpi=300,
      quality=_PAPERBACK_EXPORT_PROFILE.jpeg_quality,
    )
    ebook_pdf_bytes = pdf_client.create_pdf(
      [(page.image_bytes, page.hyperlink) for page in ebook_pages],
      dpi=300,
      quality=_EBOOK_EXPORT_PROFILE.jpeg_quality,
    )

    zip_gcs_uri, paperback_pdf_gcs_uri, ebook_pdf_gcs_uri = (
      _build_joke_book_export_uris())
    paperback_pdf_gcs_uri = cloud_storage.upload_bytes_to_gcs(
      paperback_pdf_bytes,
      paperback_pdf_gcs_uri,
      'application/pdf',
    )
    ebook_pdf_gcs_uri = cloud_storage.upload_bytes_to_gcs(
      ebook_pdf_bytes,
      ebook_pdf_gcs_uri,
      'application/pdf',
    )
    zip_gcs_uri = cloud_storage.upload_bytes_to_gcs(
      _build_zip_bytes(paperback_pages),
      zip_gcs_uri,
      'application/zip',
    ) if export_zip_paperback else None

    return JokeBookExportFiles(
      zip_url=cloud_storage.get_public_url(zip_gcs_uri)
      if zip_gcs_uri else None,
      paperback_pdf_url=cloud_storage.get_public_url(paperback_pdf_gcs_uri),
      ebook_pdf_url=cloud_storage.get_public_url(ebook_pdf_gcs_uri),
    )
  finally:
    _close_book_pages(paperback_pages)
    _close_book_pages(ebook_pages)


def _enhance_book_export_page_image(
  page_image: Image.Image,
  *,
  editor: image_editor.ImageEditor,
) -> Image.Image:
  """Apply the default image-enhancement pass to a rendered export page."""
  return editor.enhance_image(page_image)


def _create_qr_code_image(
  content: str,
  *,
  size_px: int,
) -> Image.Image:
  """Create a square QR code image for the provided content."""
  try:
    qr_module: Any = importlib.import_module('qrcode')
  except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
      'qrcode dependency is required for book review QR codes') from exc

  qr = qr_module.QRCode(
    version=None,
    error_correction=qr_module.constants.ERROR_CORRECT_M,
    box_size=10,
    border=4,
  )
  qr.add_data(content)
  qr.make(fit=True)
  raw_qr_image: Any = qr.make_image(fill_color='black', back_color='white')
  if hasattr(raw_qr_image, 'get_image'):
    raw_qr_image = raw_qr_image.get_image()
  qr_image = cast(Image.Image, raw_qr_image).convert('RGB')
  if qr_image.size != (size_px, size_px):
    qr_image = qr_image.resize((size_px, size_px), Image.Resampling.NEAREST)
  return qr_image


def _add_review_qr_to_page(
  page: BookPage,
  *,
  profile: BookExportProfile,
  associated_book_key: str,
) -> None:
  """Overlay a review QR code and matching link onto a page."""
  review_url = _get_about_page_review_bridge_url(
    associated_book_key,
    book_format=profile.review_book_format,
  )
  qr_image = _create_qr_code_image(
    review_url,
    size_px=profile.qr_size_px,
  )
  try:
    page.image.paste(qr_image, (profile.qr_x_px, profile.qr_y_px))
    label_drawer = _BookPageTextDrawer(
      page.image,
      text=profile.qr_label,
      font_size=profile.qr_label_font_size_px,
    )
    label_x = (profile.qr_x_px +
               ((profile.qr_size_px - label_drawer.width) / 2))
    label_y = (profile.qr_y_px + profile.qr_size_px +
               profile.qr_label_margin_top_px)
    label_drawer.draw_text(x=label_x, y=label_y)

    hyperlink_x1 = min(profile.qr_x_px, int(label_x))
    hyperlink_y1 = profile.qr_y_px
    hyperlink_x2 = max(
      profile.qr_x_px + profile.qr_size_px,
      int(label_x + label_drawer.width),
    )
    hyperlink_y2 = int(label_y + label_drawer.height)
    page.hyperlink = pdf_client.HyperlinkSpec(
      url=review_url,
      x1=max(0, hyperlink_x1),
      y1=hyperlink_y1,
      x2=hyperlink_x2,
      y2=hyperlink_y2,
    )
  finally:
    qr_image.close()


def _get_about_page_review_bridge_url(
  associated_book_key: str,
  *,
  book_format: book_defs.BookFormat,
) -> str:
  """Return the public review redirect URL for the about-page QR/link."""
  return amazon_redirect.get_amazon_redirect_bridge_url(
    book_defs.BookKey(associated_book_key),
    page_type=amazon_redirect.AmazonRedirectPageType.REVIEW,
    book_format=book_format,
    source=book_defs.AttributionSource.BOOK_ABOUT_PAGE,
  )


def _build_book_export_pages(
  book: models.JokeBook,
  *,
  profile: BookExportProfile,
) -> list[BookPage]:
  """Build ordered rendered pages for one export profile."""
  if not book.belongs_to_page_gcs_uri:
    raise ValueError('Joke book is missing belongs_to_page_gcs_uri')
  if not book.jokes:
    raise ValueError("Joke book has no jokes")

  editor = image_editor.ImageEditor()
  pages = [
    _build_belongs_to_page(book, profile=profile, editor=editor),
    _build_blank_page(profile=profile, editor=editor),
  ]
  pages.extend(
    _build_joke_pages(book,
                      profile=profile,
                      editor=editor,
                      starting_file_index=len(pages) + 1))
  pages.append(_build_about_page(
    book,
    profile=profile,
    editor=editor,
  ))

  _trim_and_add_page_numbers(pages, profile=profile)
  for page in pages:
    page.encode(profile=profile)

  return pages


def _build_belongs_to_page(
  book: models.JokeBook,
  *,
  profile: BookExportProfile,
  editor: image_editor.ImageEditor,
) -> BookPage:
  """Build the leading belongs-to page."""
  if not book.belongs_to_page_gcs_uri:
    raise ValueError('Joke book is missing belongs_to_page_gcs_uri')

  with cloud_storage.download_image_from_gcs(
      book.belongs_to_page_gcs_uri) as belongs_to_image:
    page_image = _convert_for_book_export(
      belongs_to_image,
      profile=profile,
      image_editor_instance=editor,
    )

  belongs_to_file_name = cloud_storage.get_gcs_file_name(
    book.belongs_to_page_gcs_uri)
  return BookPage(
    file_name=f'001_{belongs_to_file_name}',
    image=page_image,
  )


def _build_blank_page(*,
                      profile: BookExportProfile,
                      editor: image_editor.ImageEditor,
                      color_mode: str = _KDP_PRINT_COLOR_MODE) -> BookPage:
  """Build the blank page."""
  image = editor.create_blank_image(
    width=profile.pre_trim_width_px,
    height=profile.pre_trim_height_px,
    color_mode=color_mode,
  )

  return BookPage(file_name='002_blank.jpg', image=image)


def _build_joke_pages(
  book: models.JokeBook,
  *,
  profile: BookExportProfile,
  editor: image_editor.ImageEditor,
  starting_file_index: int,
) -> list[BookPage]:
  """Build all numbered setup and punchline joke pages."""
  pages: list[BookPage] = []
  current_file_index = starting_file_index
  current_page_number = 1

  for joke_id in book.jokes:
    setup_img_url, punchline_img_url = _get_book_page_image_uris_for_joke(
      joke_id)
    pages.append(
      _build_rendered_joke_page(
        image_gcs_uri=setup_img_url,
        page_number=current_page_number,
        profile=profile,
        file_name=f"{current_file_index:03d}_{joke_id}_setup.jpg",
        editor=editor,
      ))
    current_page_number += 1
    current_file_index += 1
    pages.append(
      _build_rendered_joke_page(
        image_gcs_uri=punchline_img_url,
        page_number=current_page_number,
        profile=profile,
        file_name=f"{current_file_index:03d}_{joke_id}_punchline.jpg",
        editor=editor,
      ))
    current_page_number += 1
    current_file_index += 1

  return pages


def _build_about_page(
  book: models.JokeBook,
  *,
  profile: BookExportProfile,
  editor: image_editor.ImageEditor,
) -> BookPage:
  """Build the final about page, with QR when a book association exists."""

  about_file_name = cloud_storage.get_gcs_file_name(_BOOK_PAGE_ABOUT_GCS_URI)
  if not about_file_name.startswith('999_'):
    about_file_name = f'999_{about_file_name}'

  with cloud_storage.download_image_from_gcs(
      _BOOK_PAGE_ABOUT_GCS_URI) as about_image:

    about_page = BookPage(
      file_name=about_file_name,
      image=_convert_for_book_export(
        about_image,
        profile=profile,
        image_editor_instance=editor,
      ),
    )

    if book.associated_book_key:
      _add_review_qr_to_page(
        about_page,
        profile=profile,
        associated_book_key=book.associated_book_key,
      )

    return about_page


def _get_book_page_image_uris_for_joke(joke_id: str) -> tuple[str, str]:
  """Return the stored setup and punchline book-page image URIs for a joke."""
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
  return setup_img_url, punchline_img_url


def _build_rendered_joke_page(
  image_gcs_uri: str,
  *,
  page_number: int,
  profile: BookExportProfile,
  file_name: str,
  editor: image_editor.ImageEditor,
) -> BookPage:
  """Build one rendered and enhanced numbered joke page."""
  with cloud_storage.download_image_from_gcs(image_gcs_uri) as source_image:
    converted_image = _convert_for_book_export(
      source_image,
      profile=profile,
      image_editor_instance=editor,
    )
    processed_image = _enhance_book_export_page_image(
      converted_image,
      editor=editor,
    )
    if processed_image is not converted_image:
      converted_image.close()
    return BookPage(
      file_name=file_name,
      image=processed_image,
      page_number=page_number,
    )


def _close_book_pages(pages: list[BookPage]) -> None:
  """Close all images owned by rendered book pages."""
  if not pages:
    return
  for page in pages:
    page.close()


def _build_zip_bytes(files: list[BookPage]) -> bytes:
  """Build a ZIP archive from the provided file list."""
  zip_buffer = BytesIO()
  with zipfile.ZipFile(
      zip_buffer,
      mode='w',
      compression=zipfile.ZIP_DEFLATED,
  ) as zip_file:
    for page in files:
      zip_file.writestr(page.file_name, page.image_bytes)
  return zip_buffer.getvalue()


def _build_joke_book_export_uris() -> tuple[str, str, str]:
  """Return paired GCS URIs for the export files."""
  timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
  bucket_name = 'snickerdoodle_temp_files'
  base_name = f'joke_book_pages_{timestamp}'
  zip_gcs_uri = f'gs://{bucket_name}/{base_name}.zip'
  paperback_pdf_gcs_uri = f'gs://{bucket_name}/{base_name}_paperback.pdf'
  ebook_pdf_gcs_uri = f'gs://{bucket_name}/{base_name}_ebook.pdf'
  return zip_gcs_uri, paperback_pdf_gcs_uri, ebook_pdf_gcs_uri


def _scale_book_export_image(
  image: Image.Image,
  *,
  profile: BookExportProfile,
  editor: image_editor.ImageEditor,
) -> Image.Image:
  """Scale an image to the pre-trim dimensions for an export profile."""
  return editor.scale_image(
    image,
    new_width=profile.pre_trim_width_px,
    new_height=profile.pre_trim_height_px,
  )


def _trim_and_add_page_numbers(
  pages: list[BookPage],
  *,
  profile: BookExportProfile,
) -> None:
  """Trim pages and add page numbers using one shared left/right pass."""
  max_page_number = max(
    (page.page_number for page in pages if page.page_number is not None),
    default=0,
  )

  for page_index, page in enumerate(pages):
    is_left_page = page_index % 2 == 1
    if profile.requires_trimming:
      page.trim(
        trim_left=profile.output_bleed_size_px if not is_left_page else 0,
        trim_right=profile.output_bleed_size_px if is_left_page else 0,
      )
    if page.page_number is not None:
      _add_page_number_to_image(
        page.image,
        page_number=page.page_number,
        total_pages=max_page_number,
        is_punchline=is_left_page,
        font_size=profile.page_number_font_size_px,
        offset_from_edge=profile.page_number_offset_px,
      )


def _convert_image_to_export_bytes(
  image: Image.Image,
  *,
  profile: BookExportProfile,
  color_mode: str,
) -> bytes:
  """Encode a rendered export page as JPEG bytes."""
  if abs(image.width -
         profile.final_width_px) > 2 or abs(image.height -
                                            profile.final_height_px) > 2:
    raise ValueError(
      f"Expected image size {profile.final_width_px}x{profile.final_height_px}, got {image.width}x{image.height}"
    )

  converted_image = image.convert(color_mode)
  try:
    buffer = BytesIO()
    converted_image.save(
      buffer,
      format='JPEG',
      quality=profile.jpeg_quality,
      subsampling=profile.jpeg_subsampling,
      progressive=profile.jpeg_progressive,
      optimize=True,
      dpi=(300, 300),
    )
    return buffer.getvalue()
  finally:
    converted_image.close()


def _convert_for_book_export(
  image: Image.Image,
  *,
  profile: BookExportProfile,
  image_editor_instance: image_editor.ImageEditor | None = None,
) -> Image.Image:
  """Convert an image to a pre-trim rendered image for an export profile."""
  editor = image_editor_instance or image_editor.ImageEditor()
  return _scale_book_export_image(
    image,
    profile=profile,
    editor=editor,
  )


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
    except OSError as exc:  # pragma: no cover
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
  font_size: int,
  offset_from_edge: int,
) -> None:
  """Render the page number text near the page corner."""
  if page_number <= 0 or total_pages <= 0:
    raise ValueError('page_number and total_pages must be positive')

  width, height = image.size
  if width == 0 or height == 0:
    raise ValueError('image must have non-zero width and height')

  text_drawer = _BookPageTextDrawer(
    image,
    text=str(page_number),
    font_size=font_size,
  )
  text_x: float
  if is_punchline:
    text_x = offset_from_edge
  else:
    text_x = width - offset_from_edge - text_drawer.width
  text_y = height - offset_from_edge - text_drawer.height

  text_x = max(0, text_x)
  text_y = max(0, text_y)

  text_drawer.draw_text(x=text_x, y=text_y)
