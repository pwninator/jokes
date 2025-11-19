"""Utility cloud functions for Firestore migrations."""

import datetime
import json
import traceback
from io import BytesIO

from firebase_admin import firestore
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param
from PIL import Image, UnidentifiedImageError

from common import config, models
from services import cloud_storage, firestore as firestore_service, image_editor

_db = None  # pylint: disable=invalid-name


def db() -> firestore.client:
  """Get the firestore client."""
  global _db  # pylint: disable=global-statement
  if _db is None:
    _db = firestore.client()
  return _db


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
)
def run_firestore_migration(req: https_fn.Request) -> https_fn.Response:
  """Run the image enhancement Firestore migration."""
  # Health check
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'GET':
    return https_fn.Response(
      json.dumps({
        "error": "Only GET requests are supported",
        "success": False
      }),
      status=405,
      mimetype='application/json',
    )

  try:
    dry_run = get_bool_param(req, 'dry_run', True)
    max_jokes = get_int_param(req, 'max_jokes', 0)

    html_response = run_image_enhancement_migration(
      dry_run=dry_run,
      max_jokes=max_jokes,
    )
    return https_fn.Response(html_response, status=200, mimetype='text/html')

  except Exception as e:  # pylint: disable=broad-except
    logger.error(f"Firestore migration failed: {e}")
    logger.error(traceback.format_exc())
    return https_fn.Response(
      json.dumps({
        "success": False,
        "error": str(e),
        "message": "Failed to run Firestore migration"
      }),
      status=500,
      mimetype='application/json',
    )


def run_image_enhancement_migration(
  dry_run: bool,
  max_jokes: int,
) -> str:
  """
    Enhance setup and punchline images for all jokes unless already migrated.

    Args:
        dry_run: If True, the migration will only log the changes that would be made.
        max_jokes: The maximum number of jokes to modify. If 0, all jokes will be processed.

    Returns:
        An HTML page listing the jokes that were updated.
    """
  logger.info("Starting image enhancement migration...")

  jokes = firestore_service.get_all_punny_jokes()
  editor = image_editor.ImageEditor()

  updated_jokes: list[dict[str, object]] = []
  skipped_jokes: list[dict[str, object]] = []
  updated_count = 0

  for joke in jokes:
    if max_jokes and updated_count >= max_jokes:
      logger.info(f"Reached max_jokes limit of {max_jokes}.")
      break

    joke_id = joke.key
    if not joke_id:
      skipped_jokes.append({
        "id": None,
        "reason": "missing_joke_id",
      })
      continue

    try:
      migration_doc = _get_migrations_doc_ref(joke_id)
      migration_snapshot = migration_doc.get()
      if migration_snapshot.exists:
        data = migration_snapshot.to_dict() or {}
        if bool(data.get('image_enhancement')):
          skipped_jokes.append({
            "id": joke_id,
            "reason": "already_migrated",
          })
          continue

      if not joke.setup_image_url or not joke.punchline_image_url:
        skipped_jokes.append({
          "id": joke_id,
          "reason": "missing_image_urls",
        })
        continue

      if dry_run:
        updated_jokes.append({
          "id": joke_id,
          "setup_image_url": joke.setup_image_url,
          "punchline_image_url": joke.punchline_image_url,
          "dry_run": True,
        })
        updated_count += 1
        continue

      enhanced_setup = _enhance_single_image(
        editor=editor,
        joke_id=joke_id,
        image_url=joke.setup_image_url,
        image_kind="setup",
      )
      enhanced_punchline = _enhance_single_image(
        editor=editor,
        joke_id=joke_id,
        image_url=joke.punchline_image_url,
        image_kind="punchline",
      )

      joke.set_setup_image(enhanced_setup, update_text=False)
      joke.set_punchline_image(enhanced_punchline, update_text=False)

      firestore_service.upsert_punny_joke(joke)
      migration_doc.set({'image_enhancement': True}, merge=True)

      updated_jokes.append({
        "id": joke_id,
        "setup_image_url": enhanced_setup.url,
        "punchline_image_url": enhanced_punchline.url,
        "dry_run": False,
      })
      updated_count += 1

    except Exception as err:  # pylint: disable=broad-except
      logger.error(f"Failed to enhance images for joke {joke_id}: {err}")
      skipped_jokes.append({
        "id": joke_id,
        "reason": f"error:{err}",
      })
      continue

  return _build_html_report(
    dry_run=dry_run,
    updated_jokes=updated_jokes,
    skipped_jokes=skipped_jokes,
  )


def _get_migrations_doc_ref(joke_id: str):
  """Return the Firestore document reference for a joke's migrations metadata."""
  return (db().collection('jokes').document(joke_id).collection(
    'metadata').document('migrations'))


def _enhance_single_image(
  *,
  editor: image_editor.ImageEditor,
  joke_id: str,
  image_url: str,
  image_kind: str,
) -> models.Image:
  """Download, enhance, and persist a single image, returning its metadata."""
  if not image_url:
    raise ValueError(f"Joke {joke_id} missing {image_kind} image URL.")

  source_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(image_url)
  image_bytes = cloud_storage.download_bytes_from_gcs(source_gcs_uri)

  try:
    with Image.open(BytesIO(image_bytes)) as pil_image:
      enhanced_image = editor.enhance_image(pil_image)
      buffer = BytesIO()
      enhanced_image.save(buffer, format='PNG')
      enhanced_bytes = buffer.getvalue()
  except UnidentifiedImageError as exc:
    raise ValueError(
      f"Unable to decode {image_kind} image for joke {joke_id}") from exc

  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
  file_base = f"{joke_id}_{image_kind}_enhanced_{timestamp}"
  destination_gcs_uri = cloud_storage.get_gcs_uri(
    config.IMAGE_BUCKET_NAME,
    file_base,
    "png",
  )

  cloud_storage.upload_bytes_to_gcs(
    enhanced_bytes,
    destination_gcs_uri,
    "image/png",
  )
  final_url = cloud_storage.get_final_image_url(destination_gcs_uri)

  return models.Image(
    url=final_url,
    gcs_uri=destination_gcs_uri,
  )


def _build_html_report(
  *,
  dry_run: bool,
  updated_jokes: list[dict[str, object]],
  skipped_jokes: list[dict[str, object]],
) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Image Enhancement Migration Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"
  html += f"<h2>Updated Jokes ({len(updated_jokes)})</h2>"

  if updated_jokes:
    html += "<ul>"
    for joke in updated_jokes:
      html += (f"<li><b>{joke['id']}</b>: "
               f"setup_url={joke.get('setup_image_url')}, "
               f"punchline_url={joke.get('punchline_image_url')}, "
               f"dry_run={joke.get('dry_run', False)}</li>")
    html += "</ul>"
  else:
    html += "<p>No jokes were updated.</p>"

  html += f"<h2>Skipped Jokes ({len(skipped_jokes)})</h2>"
  if skipped_jokes:
    html += "<ul>"
    for joke in skipped_jokes:
      html += (f"<li><b>{joke.get('id')}</b>: "
               f"reason={joke.get('reason')}</li>")
    html += "</ul>"
  else:
    html += "<p>No jokes were skipped.</p>"

  html += "</body></html>"
  return html
