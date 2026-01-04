"""Operations for generating joke notes sheet images."""

from __future__ import annotations

from io import BytesIO

import requests
from firebase_functions import logger
from PIL import Image
from services import cloud_storage, firestore, pdf_client

_JOKE_NOTES_OVERLAY_URL = "https://images.quillsstorybook.com/cdn-cgi/image/format=png,quality=100/_joke_assets/lunchbox/lunchbox_notes_template.png"


def create_joke_notes_sheet_image(joke_ids: list[str]) -> Image.Image:
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


def create_joke_notes_sheet(
  joke_ids: list[str],
  *,
  quality: int = 80,
) -> bytes:
  """Creates a PDF with the joke notes sheet image."""
  notes_image = create_joke_notes_sheet_image(joke_ids)
  return pdf_client.create_pdf([notes_image], quality=quality)
