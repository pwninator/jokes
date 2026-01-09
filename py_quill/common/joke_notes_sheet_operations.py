"""Operations for generating joke notes sheet images."""

from __future__ import annotations

import hashlib
from io import BytesIO

import requests
from common import config, models
from firebase_functions import logger
from PIL import Image
from services import cloud_storage, firestore, pdf_client

_JOKE_NOTES_SHEET_VERSION = 1

_JOKE_NOTES_OVERLAY_URL = "https://images.quillsstorybook.com/cdn-cgi/image/format=png,quality=100/_joke_assets/lunchbox/joke_notes_overlay.png"

_PDF_DIR_GCS_URI = f"gs://{config.PUBLIC_FILE_BUCKET_NAME}/joke_notes_sheets{_JOKE_NOTES_SHEET_VERSION}"
_IMAGE_DIR_GCS_URI = f"gs://{config.IMAGE_BUCKET_NAME}/joke_notes_sheets{_JOKE_NOTES_SHEET_VERSION}"


def ensure_joke_notes_sheet(
  jokes: list[models.PunnyJoke],
  *,
  quality: int = 80,
  category_id: str | None = None,
  index: int | None = None,
) -> models.JokeSheet:
  """Create a joke notes sheet (PNG + PDF), upload to GCS, upsert Firestore, and return the sheet.

  Notes:
  - The Firestore doc is unique by joke IDs only (sorted `joke_str`).
  - The asset filenames include `quality`, so subsequent calls with different
    quality will overwrite the stored URIs on the same Firestore doc.
  - The saved-users fraction is averaged across the supplied jokes.
  """
  joke_ids = [joke.key for joke in jokes if joke.key]
  filename_base = _generate_file_stem(joke_ids, quality=quality)
  pdf_gcs_uri = f"{_PDF_DIR_GCS_URI}/{filename_base}.pdf"
  image_gcs_uri = f"{_IMAGE_DIR_GCS_URI}/{filename_base}.png"

  pdf_exists = cloud_storage.gcs_file_exists(pdf_gcs_uri)
  image_exists = cloud_storage.gcs_file_exists(image_gcs_uri)

  if not (pdf_exists and image_exists):
    notes_image = _create_joke_notes_sheet_image(jokes)

    if not image_exists:
      image_bytes = _encode_png(notes_image)
      cloud_storage.upload_bytes_to_gcs(
        content_bytes=image_bytes,
        gcs_uri=image_gcs_uri,
        content_type="image/png",
      )

    if not pdf_exists:
      pdf_bytes = pdf_client.create_pdf([notes_image], quality=quality)
      cloud_storage.upload_bytes_to_gcs(
        content_bytes=pdf_bytes,
        gcs_uri=pdf_gcs_uri,
        content_type="application/pdf",
      )

  sheet = models.JokeSheet(
    joke_ids=list(joke_ids),
    category_id=category_id,
    index=index,
    image_gcs_uri=image_gcs_uri,
    pdf_gcs_uri=pdf_gcs_uri,
    avg_saved_users_fraction=average_saved_users_fraction(jokes),
  )
  return firestore.upsert_joke_sheet(sheet)


def _generate_file_stem(joke_ids: list[str], *, quality: int) -> str:
  """Generate a deterministic file stem from joke IDs using SHA-256.

  Joke IDs are sorted before hashing so different orderings produce the same
  stem.
  """
  hash_components = sorted(joke_ids) + [
    f"quality={int(quality)}",
    f"version={_JOKE_NOTES_SHEET_VERSION}",
  ]
  hash_source = "|".join(hash_components)
  return hashlib.sha256(hash_source.encode("utf-8")).hexdigest()


def _encode_png(image: Image.Image) -> bytes:
  """Encode a PIL image as PNG bytes."""
  buf = BytesIO()
  image.save(buf, format="PNG")
  return buf.getvalue()


def _create_joke_notes_sheet_image(
  jokes: list[models.PunnyJoke], ) -> Image.Image:
  """Creates a printable sheet of joke notes with setup and punchline images.

  The output is a 3300x2550 image containing up to 5 jokes
  arranged in a 2x3 grid. Each joke consists of the punchline image on the
  left and the setup image on the right.

  Args:
    jokes: List of jokes to include (max 5).

  Returns:
    PIL Image for the composed notes sheet.
  """
  if len(jokes) > 5:
    jokes = jokes[:5]

  # Canvas dimensions
  canvas_width = 3300
  canvas_height = 2550
  margin = 150

  # Joke cell dimensions
  joke_width = 1500  # 750 + 750
  joke_height = 750

  # Create blank white canvas
  canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

  for i, joke in enumerate(jokes):
    # Calculate position
    col = i % 2
    row = i // 2

    x_offset = margin + (col * joke_width)
    y_offset = margin + (row * joke_height)

    joke_id = joke.key or f"index-{i}"
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


def average_saved_users_fraction(jokes: list[models.PunnyJoke]) -> float:
  """Compute the average saved-users fraction across the provided jokes."""
  if not jokes:
    return 0.0
  total = 0.0
  for joke in jokes:
    try:
      total += float(joke.num_saved_users_fraction or 0.0)
    except (TypeError, ValueError):
      total += 0.0
  return total / len(jokes)
