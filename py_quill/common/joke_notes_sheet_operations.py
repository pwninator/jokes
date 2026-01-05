"""Operations for generating joke notes sheet images."""

from __future__ import annotations

import hashlib
from io import BytesIO

import requests
from common import config
from firebase_functions import logger
from PIL import Image
from services import cloud_storage, firestore, pdf_client

_JOKE_NOTES_OVERLAY_URL = "https://images.quillsstorybook.com/cdn-cgi/image/format=png,quality=100/_joke_assets/lunchbox/lunchbox_notes_template.png"

_PDF_DIR_GCS_URI = f"gs://{config.TEMP_FILE_BUCKET_NAME}/joke_notes_sheets"


def get_joke_notes_sheet(
  joke_ids: list[str],
  *,
  quality: int = 80,
) -> str:
  """Creates a PDF with the joke notes sheet image, uploads to GCS, and returns the GCS URI."""
  filename = _generate_pdf_filename(joke_ids)
  gcs_uri = f"{_PDF_DIR_GCS_URI}/{filename}"

  if cloud_storage.gcs_file_exists(gcs_uri):
    return gcs_uri

  notes_image = _create_joke_notes_sheet_image(joke_ids)
  pdf_bytes = pdf_client.create_pdf([notes_image], quality=quality)
  cloud_storage.upload_bytes_to_gcs(
    content_bytes=pdf_bytes,
    gcs_uri=gcs_uri,
    content_type="application/pdf",
  )
  return gcs_uri


def _generate_pdf_filename(joke_ids: list[str]) -> str:
  """Generate a deterministic filename from joke IDs using SHA-256.

  Joke IDs are sorted before hashing so different orderings produce the same
  filename.
  """
  joke_ids_str = ",".join(sorted(joke_ids))
  hash_digest = hashlib.sha256(joke_ids_str.encode("utf-8")).hexdigest()
  return f"{hash_digest}.pdf"


def _create_joke_notes_sheet_image(joke_ids: list[str]) -> Image.Image:
  """Creates a printable sheet of joke notes with setup and punchline images.

  The output is a 3300x2550 image containing up to 6 jokes
  arranged in a 2x3 grid. Each joke consists of the punchline image on the
  left and the setup image on the right.

  Args:
    joke_ids: List of joke IDs to include (max 6).

  Returns:
    PIL Image for the composed notes sheet.
  """
  if len(joke_ids) > 5:
    joke_ids = joke_ids[:5]

  # Canvas dimensions
  canvas_width = 3300
  canvas_height = 2550
  margin = 150

  # Joke cell dimensions
  joke_width = 1500  # 750 + 750
  joke_height = 750

  # Create blank white canvas
  canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

  for i, joke_id in enumerate(joke_ids):
    # Calculate position
    col = i % 2
    row = i // 2

    x_offset = margin + (col * joke_width)
    y_offset = margin + (row * joke_height)

    # Fetch joke
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      logger.warn(f"Joke {joke_id} not found, skipping in notes sheet.")
      continue

    setup_url = joke.setup_image_url
    punchline_url = joke.punchline_image_url

    if not setup_url or not punchline_url:
      logger.warn(f"Joke {joke_id} missing images, skipping in notes sheet.")
      continue

    try:
      # Download images
      setup_gcs = cloud_storage.extract_gcs_uri_from_image_url(setup_url)
      punchline_gcs = cloud_storage.extract_gcs_uri_from_image_url(
        punchline_url)

      setup_img = cloud_storage.download_image_from_gcs(setup_gcs)
      punchline_img = cloud_storage.download_image_from_gcs(punchline_gcs)

      # Resize to 750x750
      setup_img = setup_img.resize((750, 750))
      punchline_img = punchline_img.resize((750, 750))

      # Paste: Punchline (Left), Setup (Right)
      canvas.paste(punchline_img, (x_offset, y_offset))
      canvas.paste(setup_img, (x_offset + 750, y_offset))

    except Exception as e:
      logger.error(f"Error processing joke {joke_id} for notes sheet: {e}")
      continue

  try:
    response = requests.get(_JOKE_NOTES_OVERLAY_URL, timeout=10)
    response.raise_for_status()
    template_image = Image.open(BytesIO(response.content)).convert('RGBA')
    if template_image.size != (canvas_width, canvas_height):
      logger.warn("Joke notes template size mismatch: "
                  f"{template_image.size} vs {(canvas_width, canvas_height)}")
      template_image = template_image.resize(
        (canvas_width, canvas_height),
        resample=Image.Resampling.LANCZOS,
      )
    canvas = canvas.convert('RGBA')
    canvas = Image.alpha_composite(canvas, template_image)
    canvas = canvas.convert('RGB')
  except (requests.RequestException, OSError) as exc:
    logger.error(f"Error loading joke notes template: {exc}")

  return canvas
