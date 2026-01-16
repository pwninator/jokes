"""Admin printable notes management route."""

from __future__ import annotations

import flask
from firebase_functions import logger

import datetime
from io import BytesIO

from common import config, image_operations, models, utils
from functions import auth_helpers
from services import cloud_storage, firestore
from web.routes import web_bp

_MAX_PIN_JOKES = 5


@web_bp.route('/admin/printable-notes')
@auth_helpers.require_admin
def admin_printable_notes():
  """Render admin printable notes page showing all sheets organized by category."""
  cache_entries = _get_joke_sheets_cache()

  categories_data = []
  for category, sheets in cache_entries:
    category_id = category.id
    if not category_id:
      continue

    # Get full category to access image_url
    full_category = firestore.get_joke_category(category_id)
    category_image_url = None
    if full_category and full_category.image_url:
      # Try to convert GCS URI to CDN URL, or use as-is if already a CDN URL
      image_url = full_category.image_url
      if image_url.startswith('gs://'):
        try:
          cdn_url = cloud_storage.get_public_image_cdn_url(image_url)
          category_image_url = utils.format_image_url(cdn_url, width=120)
        except ValueError:
          pass
      else:
        # Already a CDN URL, format it
        try:
          category_image_url = utils.format_image_url(image_url, width=120)
        except ValueError:
          category_image_url = image_url

    sheets_data = []
    for sheet in sheets:
      if not sheet.key:
        continue

      # Fetch full sheet document to get joke_ids
      sheet_doc = firestore.db().collection('joke_sheets').document(
        sheet.key).get()
      if not getattr(sheet_doc, 'exists', False):
        continue

      sheet_dict = sheet_doc.to_dict() or {}
      joke_ids = sheet_dict.get('joke_ids') or []
      if not isinstance(joke_ids, list):
        joke_ids = []

      # Fetch jokes
      jokes = firestore.get_punny_jokes(joke_ids) if joke_ids else []

      # Get sheet image URL
      sheet_image_url = None
      if sheet.image_gcs_uri:
        try:
          cdn_url = cloud_storage.get_public_image_cdn_url(sheet.image_gcs_uri)
          sheet_image_url = utils.format_image_url(cdn_url, width=200)
        except ValueError:
          pass

      # Get joke images
      joke_images = []
      for joke in jokes[:5]:  # Max 5 jokes per sheet
        setup_url = None
        punchline_url = None
        if joke.setup_image_url:
          # Convert GCS URI to CDN URL if needed, then format
          if joke.setup_image_url.startswith('gs://'):
            try:
              cdn_url = cloud_storage.get_public_image_cdn_url(
                joke.setup_image_url)
              setup_url = utils.format_image_url(cdn_url,
                                                 width=150,
                                                 quality=50)
            except ValueError:
              pass
          else:
            # Already a CDN URL, format it
            try:
              setup_url = utils.format_image_url(joke.setup_image_url,
                                                 width=150,
                                                 quality=50)
            except ValueError:
              setup_url = joke.setup_image_url
        if joke.punchline_image_url:
          # Convert GCS URI to CDN URL if needed, then format
          if joke.punchline_image_url.startswith('gs://'):
            try:
              cdn_url = cloud_storage.get_public_image_cdn_url(
                joke.punchline_image_url)
              punchline_url = utils.format_image_url(cdn_url,
                                                     width=150,
                                                     quality=50)
            except ValueError:
              pass
          else:
            # Already a CDN URL, format it
            try:
              punchline_url = utils.format_image_url(joke.punchline_image_url,
                                                     width=150,
                                                     quality=50)
            except ValueError:
              punchline_url = joke.punchline_image_url

        joke_images.append({
          'joke_id': joke.key,
          'setup_url': setup_url,
          'punchline_url': punchline_url,
        })

      sheets_data.append({
        'sheet':
        sheet,
        'sheet_image_url':
        sheet_image_url,
        'joke_images':
        joke_images,
        'display_index':
        sheet.display_index
        or (sheet.index + 1 if sheet.index is not None else 1),
      })

    if sheets_data:
      categories_data.append({
        'category': category,
        'category_image_url': category_image_url,
        'sheets': sheets_data,
      })

  return flask.render_template(
    'admin/printable_notes.html',
    site_name='Snickerdoodle',
    categories=categories_data,
  )


@web_bp.route('/admin/printable-notes/create-pin', methods=['POST'])
@web_bp.route('/admin/create-pin', methods=['POST'])
@auth_helpers.require_admin
def admin_create_pin_image():
  """Create a Pinterest pin image from selected joke IDs."""
  data = flask.request.get_json() or {}
  joke_ids = data.get('joke_ids', [])

  if not joke_ids or not isinstance(joke_ids, list):
    return flask.jsonify({'error': 'joke_ids required as a list'}), 400
  if len(joke_ids) > _MAX_PIN_JOKES:
    return flask.jsonify({'error': 'joke_ids must have at most 5 items'}), 400

  try:
    # Create the pin image
    pin_image = image_operations.create_pinterest_pin_image(
      joke_ids=joke_ids)

    # Convert PIL Image to PNG bytes
    buffer = BytesIO()
    pin_image.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()

    # Upload to GCS
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    gcs_uri = cloud_storage.get_gcs_uri(
      config.TEMP_FILE_BUCKET_NAME,
      f'pinterest_pin_{timestamp}',
      'png',
    )
    cloud_storage.upload_bytes_to_gcs(
      image_bytes,
      gcs_uri,
      'image/png',
    )

    # Get public CDN URL
    pin_url = cloud_storage.get_public_cdn_url(gcs_uri)

    return flask.jsonify({'pin_url': pin_url})

  except ValueError as exc:
    logger.error(
      f"Failed to create pin image: {exc}",
      extra={
        "json_fields": {
          "event": "admin_create_pin_image_failed",
          "joke_ids": joke_ids,
        }
      },
    )
    return flask.jsonify({'error': str(exc)}), 400
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Unexpected error creating pin image: {exc}",
      extra={
        "json_fields": {
          "event": "admin_create_pin_image_error",
          "joke_ids": joke_ids,
        }
      },
    )
    return flask.jsonify({'error': 'Failed to create pin image'}), 500


def _get_joke_sheets_cache(
) -> list[tuple[models.JokeCategory, list[models.JokeSheet]]]:
  """Get the joke sheets cache, with error handling."""
  try:
    return firestore.get_joke_sheets_cache()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke sheets cache: {exc}",
      extra={
        "json_fields": {
          "event": "admin_printable_notes_cache_fetch_failed",
        }
      },
    )
    return []
