"""Admin printable notes management route."""

from __future__ import annotations

import flask
from firebase_functions import logger

from common import models, utils
from functions import auth_helpers
from services import cloud_storage, firestore
from web.routes import web_bp


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
      sheet_doc = firestore.db().collection('joke_sheets').document(sheet.key).get()
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
              cdn_url = cloud_storage.get_public_image_cdn_url(joke.setup_image_url)
              setup_url = utils.format_image_url(cdn_url, width=150, quality=50)
            except ValueError:
              pass
          else:
            # Already a CDN URL, format it
            try:
              setup_url = utils.format_image_url(joke.setup_image_url, width=150, quality=50)
            except ValueError:
              setup_url = joke.setup_image_url
        if joke.punchline_image_url:
          # Convert GCS URI to CDN URL if needed, then format
          if joke.punchline_image_url.startswith('gs://'):
            try:
              cdn_url = cloud_storage.get_public_image_cdn_url(joke.punchline_image_url)
              punchline_url = utils.format_image_url(cdn_url, width=150, quality=50)
            except ValueError:
              pass
          else:
            # Already a CDN URL, format it
            try:
              punchline_url = utils.format_image_url(joke.punchline_image_url, width=150, quality=50)
            except ValueError:
              punchline_url = joke.punchline_image_url
        
        joke_images.append({
          'setup_url': setup_url,
          'punchline_url': punchline_url,
        })
      
      sheets_data.append({
        'sheet': sheet,
        'sheet_image_url': sheet_image_url,
        'joke_images': joke_images,
        'display_index': sheet.display_index or (sheet.index + 1 if sheet.index is not None else 1),
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


def _get_joke_sheets_cache(
) -> list[tuple[models.JokeCategory, list[models.JokeSheet]]]:
  """Get the joke sheets cache, with error handling."""
  try:
    return firestore.get_joke_sheets_cache()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke sheets cache: {exc}",
      extra={"json_fields": {
        "event": "admin_printable_notes_cache_fetch_failed",
      }},
    )
    return []
