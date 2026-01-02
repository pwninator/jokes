"""PDF operations."""

from io import BytesIO
from typing import Any

import img2pdf
from PIL import Image

from common import models
from services import cloud_storage


def create_pdf(
    images: list[Any],
    dpi: int = 300,
    quality: int = 80,
    page_width: int | None = None,
    page_height: int | None = None,
) -> bytes:
  """Creates a PDF from a list of images.

  Args:
      images: List of images. Can be PIL Image objects, bytes, models.Image
        objects, or strings (GCS URIs).
      dpi: DPI of the images in the PDF.
      quality: JPEG quality of the images in the PDF.
      page_width: Width of the pages in pixels.
      page_height: Height of the pages in pixels.

  Returns:
      The PDF bytes.
  """
  jpeg_bytes_list = []

  for image_item in images:
    # 1. Resolve to PIL Image
    img: Image.Image | None = None
    if isinstance(image_item, Image.Image):
      img = image_item
    elif isinstance(image_item, bytes):
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

    # Explicitly close the PIL image to free memory, though garbage collection
    # usually handles it.
    img.close()

  # 4. Create PDF
  # img2pdf.convert can take a list of bytes
  pdf_bytes = img2pdf.convert(jpeg_bytes_list)

  return pdf_bytes
