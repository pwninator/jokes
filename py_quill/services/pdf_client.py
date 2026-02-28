"""PDF operations."""

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import img2pdf
from common import models
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from services import cloud_storage

_PDF_POINTS_PER_INCH = 72


@dataclass(frozen=True)
class HyperlinkSpec:
  """Clickable rectangle overlay for a generated PDF page."""

  page_index: int
  url: str
  x1: float
  y1: float
  x2: float
  y2: float


def _can_embed_jpeg_bytes(
  image_bytes: bytes,
  *,
  page_width: int | None,
  page_height: int | None,
) -> bool:
  """Return True when JPEG bytes can be embedded into the PDF unchanged."""
  try:
    with Image.open(BytesIO(image_bytes)) as image:
      if image.format != 'JPEG':
        return False
      if image.mode != 'RGB':
        return False
      if page_width is not None and page_height is not None:
        return image.size == (page_width, page_height)
      return True
  except OSError:
    return False


def create_pdf(
  images: list[Any],
  dpi: int = 300,
  quality: int = 80,
  page_width: int | None = None,
  page_height: int | None = None,
  hyperlinks: list[HyperlinkSpec] | None = None,
) -> bytes:
  """Creates a PDF from a list of images.

  Args:
      images: List of images. Can be PIL Image objects, bytes, models.Image
        objects, or strings (GCS URIs).
      dpi: DPI of the images in the PDF.
      quality: JPEG quality of the images in the PDF.
      page_width: Width of the pages in pixels.
      page_height: Height of the pages in pixels.
      hyperlinks: Optional clickable URL rectangles, with coordinates in pixels.

  Returns:
      The PDF bytes.
  """
  jpeg_bytes_list = []
  page_pixel_sizes: list[tuple[int, int]] = []

  for image_item in images:
    # 1. Resolve to PIL Image
    img: Image.Image | None = None
    if isinstance(image_item, Image.Image):
      img = image_item
    elif isinstance(image_item, bytes):
      if _can_embed_jpeg_bytes(
          image_item,
          page_width=page_width,
          page_height=page_height,
      ):
        with Image.open(BytesIO(image_item)) as embedded_image:
          embedded_image.load()  # pyright: ignore[reportUnusedCallResult]
          page_pixel_sizes.append(embedded_image.size)
        jpeg_bytes_list.append(image_item)
        continue
      img = Image.open(BytesIO(image_item))
    elif isinstance(image_item, str):
      img = cloud_storage.download_image_from_gcs(image_item)
    elif isinstance(image_item, models.Image):
      if not image_item.gcs_uri:
        raise ValueError(f"Image model has no GCS URI: {image_item}")
      img = cloud_storage.download_image_from_gcs(image_item.gcs_uri)
    else:
      raise ValueError(f"Unsupported image type: {type(image_item)}")

    # Ensure RGB (handling RGBA or others that JPEG doesn't support directly)
    if img.mode != 'RGB':
      img = img.convert('RGB')

    # 2. Resize if needed
    if page_width is not None and page_height is not None:
      if img.size != (page_width, page_height):
        img = img.resize((page_width, page_height), Image.Resampling.LANCZOS)

    # 3. Convert to JPEG bytes
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality, dpi=(dpi, dpi))
    jpeg_bytes = buffer.getvalue()
    jpeg_bytes_list.append(jpeg_bytes)
    page_pixel_sizes.append(img.size)

    # Explicitly close the PIL image to free memory, though garbage collection
    # usually handles it.
    img.close()

  # 4. Create PDF
  # img2pdf.convert can take a list of bytes
  pdf_bytes = img2pdf.convert(jpeg_bytes_list)

  if not pdf_bytes:
    raise ValueError("No images to convert to PDF")
  if hyperlinks:
    return _add_hyperlinks_to_pdf(
      pdf_bytes,
      page_pixel_sizes=page_pixel_sizes,
      dpi=dpi,
      hyperlinks=hyperlinks,
    )
  return pdf_bytes


def _pdf_rect_from_pixels(
  hyperlink: HyperlinkSpec,
  *,
  page_width_px: int,
  page_height_px: int,
  dpi: int,
) -> RectangleObject:
  """Convert a top-left-origin pixel rectangle into PDF point coordinates."""
  del page_width_px  # width validation is unnecessary for conversion math
  points_per_pixel = _PDF_POINTS_PER_INCH / dpi
  return RectangleObject((
    hyperlink.x1 * points_per_pixel,
    (page_height_px - hyperlink.y2) * points_per_pixel,
    hyperlink.x2 * points_per_pixel,
    (page_height_px - hyperlink.y1) * points_per_pixel,
  ))


def _validate_hyperlink(
  hyperlink: HyperlinkSpec,
  *,
  page_count: int,
  page_width_px: int,
  page_height_px: int,
) -> None:
  """Validate a hyperlink spec against the generated PDF pages."""
  if hyperlink.page_index < 0 or hyperlink.page_index >= page_count:
    raise ValueError(f"Invalid hyperlink page_index: {hyperlink.page_index}")
  if not hyperlink.url:
    raise ValueError("Hyperlink URL is required")
  if hyperlink.x2 <= hyperlink.x1 or hyperlink.y2 <= hyperlink.y1:
    raise ValueError(f"Invalid hyperlink rectangle: {hyperlink}")
  if hyperlink.x1 < 0 or hyperlink.y1 < 0:
    raise ValueError(f"Invalid hyperlink rectangle: {hyperlink}")
  if hyperlink.x2 > page_width_px or hyperlink.y2 > page_height_px:
    raise ValueError(f"Invalid hyperlink rectangle: {hyperlink}")


def _add_hyperlinks_to_pdf(
  pdf_bytes: bytes,
  *,
  page_pixel_sizes: list[tuple[int, int]],
  dpi: int,
  hyperlinks: list[HyperlinkSpec],
) -> bytes:
  """Add link annotations to an existing PDF."""
  reader = PdfReader(BytesIO(pdf_bytes))
  writer = PdfWriter()
  writer.append_pages_from_reader(reader)

  for hyperlink in hyperlinks:
    if hyperlink.page_index < 0 or hyperlink.page_index >= len(
        page_pixel_sizes):
      raise ValueError(f"Invalid hyperlink page_index: {hyperlink.page_index}")
    page_width_px, page_height_px = page_pixel_sizes[hyperlink.page_index]
    _validate_hyperlink(
      hyperlink,
      page_count=len(page_pixel_sizes),
      page_width_px=page_width_px,
      page_height_px=page_height_px,
    )
    writer.add_uri(
      hyperlink.page_index,
      hyperlink.url,
      _pdf_rect_from_pixels(
        hyperlink,
        page_width_px=page_width_px,
        page_height_px=page_height_px,
        dpi=dpi,
      ),
    )

  output = BytesIO()
  _ = writer.write(output)
  return output.getvalue()
