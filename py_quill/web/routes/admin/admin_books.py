"""Admin joke book management routes."""

from __future__ import annotations

import datetime
import os

import flask
from firebase_functions import logger
from google.cloud.firestore import ArrayUnion

from common import config, image_generation, joke_book_operations, models, utils
from functions import auth_helpers
from services import cloud_storage, firestore
from web.routes import web_bp
from web.routes.admin import joke_feed_utils


def _format_book_page_image(image_url: str | None) -> str | None:
  """Normalize book page images to 800px squares for admin previews."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=800,
    )
  except ValueError:
    # If not a CDN URL, return as-is to avoid breaking the page.
    return image_url


def _format_book_page_download(image_url: str | None) -> str | None:
  """Create a full-quality download link for book page images."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=100,
      remove_existing=True,
    )
  except ValueError:
    return image_url


def _format_book_page_thumb(image_url: str | None) -> str | None:
  """Create a small thumbnail URL for variant tiles."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=100,
    )
  except ValueError:
    return image_url


def _format_joke_preview(image_url: str | None) -> str | None:
  """Create a small preview of the main joke images for context."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=200,
    )
  except ValueError:
    return image_url


def _extract_total_cost(joke_data: dict[str, object]) -> float | None:
  """Safely extract total generation cost from joke data."""
  generation_metadata = joke_data.get('generation_metadata')
  if not isinstance(generation_metadata, dict):
    return None

  total_cost = generation_metadata.get('total_cost')
  if isinstance(total_cost, (int, float)):
    return float(total_cost)

  try:
    return models.GenerationMetadata.from_dict(generation_metadata).total_cost
  except Exception:
    return None


@web_bp.route('/admin/joke-books')
@auth_helpers.require_admin
def admin_joke_books():
  """Render a simple table of all joke book documents."""
  books = firestore.get_all_joke_books()
  return flask.render_template(
    'admin/joke_books.html',
    books=books,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books/<book_id>')
@auth_helpers.require_admin
def admin_joke_book_detail(book_id: str):
  """Render an image-centric view of a single joke book."""
  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)
  book_doc = book_ref.get()
  if not getattr(book_doc, 'exists', False):
    return flask.Response('Joke book not found', status=404)

  book_data = book_doc.to_dict() or {}
  jokes = book_data.get('jokes') or []
  book_info = {
    'id': book_id,
    'book_name': book_data.get('book_name') or book_id,
    'zip_url': book_data.get('zip_url'),
  }

  joke_rows: list[dict[str, object]] = []
  total_book_cost = 0.0
  for sequence, joke_id in enumerate(jokes, start=1):
    joke_ref = client.collection('jokes').document(joke_id)
    joke_doc = joke_ref.get()
    joke_data = joke_doc.to_dict() or {} if getattr(joke_doc, 'exists',
                                                    False) else {}
    metadata_ref = joke_ref.collection('metadata').document('metadata')
    metadata_doc = metadata_ref.get()
    setup_url = None
    punchline_url = None
    setup_variants: list[str] = []
    punchline_variants: list[str] = []
    if getattr(metadata_doc, 'exists', False):
      metadata = metadata_doc.to_dict() or {}
      setup_url = metadata.get('book_page_setup_image_url')
      punchline_url = metadata.get('book_page_punchline_image_url')
      setup_variants = metadata.get('all_book_page_setup_image_urls') or []
      punchline_variants = metadata.get(
        'all_book_page_punchline_image_urls') or []

    joke_data_for_card = dict(joke_data)
    joke_data_for_card.setdefault('setup_text', '')
    joke_data_for_card.setdefault('punchline_text', '')
    joke_model = models.PunnyJoke.from_firestore_dict(joke_data_for_card,
                                                      joke_id)
    edit_payload = joke_feed_utils.build_edit_payload(joke_model)

    joke_cost = _extract_total_cost(joke_data)
    if isinstance(joke_cost, (int, float)):
      total_book_cost += float(joke_cost)

    num_views = int(joke_data.get('num_viewed_users') or 0)
    num_saves = int(joke_data.get('num_saved_users') or 0)
    num_shares = int(joke_data.get('num_shared_users') or 0)
    popularity_score = float(joke_data.get('popularity_score') or 0.0)
    num_saved_users_fraction = float(
      joke_data.get('num_saved_users_fraction') or 0.0)

    joke_rows.append({
      'sequence':
      sequence,
      'id':
      joke_id,
      'setup_image':
      _format_book_page_image(setup_url),
      'punchline_image':
      _format_book_page_image(punchline_url),
      'setup_image_download':
      _format_book_page_download(setup_url),
      'punchline_image_download':
      _format_book_page_download(punchline_url),
      'total_cost':
      joke_cost,
      'setup_original_image':
      _format_book_page_image(joke_data.get('setup_image_url')),
      'punchline_original_image':
      _format_book_page_image(joke_data.get('punchline_image_url')),
      'setup_preview':
      _format_joke_preview(joke_data.get('setup_image_url')),
      'punchline_preview':
      _format_joke_preview(joke_data.get('punchline_image_url')),
      'setup_variants':
      [_format_book_page_thumb(url) for url in setup_variants if url],
      'punchline_variants':
      [_format_book_page_thumb(url) for url in punchline_variants if url],
      'card_joke':
      joke_model,
      'edit_payload':
      edit_payload,
      'num_views':
      num_views,
      'num_saves':
      num_saves,
      'num_shares':
      num_shares,
      'popularity_score':
      popularity_score,
      'num_saved_users_fraction':
      num_saved_users_fraction,
    })

  if utils.is_emulator():
    generate_book_page_url = "http://127.0.0.1:5001/storyteller-450807/us-central1/generate_joke_book_page"
  else:
    generate_book_page_url = "https://generate-joke-book-page-uqdkqas7gq-uc.a.run.app"

  return flask.render_template(
    'admin/joke_book_detail.html',
    book=book_info,
    jokes=joke_rows,
    generate_book_page_url=generate_book_page_url,
    update_book_page_url=flask.url_for('web.admin_update_joke_book_page'),
    set_main_image_url=flask.url_for(
      'web.admin_set_main_joke_image_from_book_page'),
    joke_creation_url='/joke_creation_process',
    image_qualities=list(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys()),
    book_total_cost=total_book_cost if joke_rows else None,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books/update-page', methods=['POST'])
@auth_helpers.require_admin
def admin_update_joke_book_page():
  """Update book page image selection for a single joke."""
  book_id = flask.request.form.get('joke_book_id')
  joke_id = flask.request.form.get('joke_id')
  new_setup_url = flask.request.form.get('new_book_page_setup_image_url')
  new_punchline_url = flask.request.form.get(
    'new_book_page_punchline_image_url')

  if not book_id or not joke_id:
    return flask.Response('joke_book_id and joke_id are required', 400)

  if not new_setup_url and not new_punchline_url:
    return flask.Response(('Provide new_book_page_setup_image_url or '
                           'new_book_page_punchline_image_url'), 400)

  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)
  book_doc = book_ref.get()
  if not getattr(book_doc, 'exists', False):
    return flask.Response('Joke book not found', 404)

  book_data = book_doc.to_dict() or {}
  joke_ids = book_data.get('jokes') or []
  if isinstance(joke_ids, list) and joke_ids and joke_id not in joke_ids:
    return flask.Response('Joke does not belong to this book', 404)

  joke_ref = client.collection('jokes').document(joke_id)
  metadata_ref = joke_ref.collection('metadata').document('metadata')
  metadata_doc = metadata_ref.get()
  existing_metadata = metadata_doc.to_dict() if getattr(
    metadata_doc, 'exists', False) else {}

  current_setup = existing_metadata.get('book_page_setup_image_url')
  current_punchline = existing_metadata.get('book_page_punchline_image_url')

  updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    existing_metadata,
    new_setup_url or current_setup,
    new_punchline_url or current_punchline,
  )

  metadata_ref.set(updates, merge=True)

  return flask.jsonify({
    'book_id':
    book_id,
    'joke_id':
    joke_id,
    'book_page_setup_image_url':
    updates.get('book_page_setup_image_url'),
    'book_page_punchline_image_url':
    updates.get('book_page_punchline_image_url'),
  })


@web_bp.route('/admin/joke-books/set-main-image', methods=['POST'])
@auth_helpers.require_admin
def admin_set_main_joke_image_from_book_page():
  """Promote the selected book page image to the main joke image."""
  book_id = flask.request.form.get('joke_book_id')
  joke_id = flask.request.form.get('joke_id')
  target = flask.request.form.get('target')

  if not book_id or not joke_id:
    return flask.Response('joke_book_id and joke_id are required', 400)

  if target not in {'setup', 'punchline'}:
    return flask.Response('target must be setup or punchline', 400)

  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)
  book_doc = book_ref.get()
  if not getattr(book_doc, 'exists', False):
    return flask.Response('Joke book not found', 404)

  book_data = book_doc.to_dict() or {}
  joke_ids = book_data.get('jokes') or []
  if isinstance(joke_ids, list) and joke_ids and joke_id not in joke_ids:
    return flask.Response('Joke does not belong to this book', 404)

  joke_ref = client.collection('jokes').document(joke_id)
  metadata_ref = joke_ref.collection('metadata').document('metadata')
  metadata_doc = metadata_ref.get()
  metadata = metadata_doc.to_dict() if getattr(metadata_doc, 'exists',
                                               False) else {}

  page_field = ('book_page_setup_image_url'
                if target == 'setup' else 'book_page_punchline_image_url')
  page_url = metadata.get(page_field)
  if not page_url:
    return flask.Response('Book page image not found', 400)

  main_field = 'setup_image_url' if target == 'setup' else 'punchline_image_url'
  history_field = 'all_setup_image_urls' if target == 'setup' else 'all_punchline_image_urls'
  upscaled_field = 'setup_image_url_upscaled' if target == 'setup' else 'punchline_image_url_upscaled'

  joke_ref.update({
    main_field: page_url,
    history_field: ArrayUnion([page_url]),
    upscaled_field: None,
  })

  return flask.jsonify({
    'book_id': book_id,
    'joke_id': joke_id,
    main_field: page_url,
  })


@web_bp.route('/admin/joke-books/<book_id>/jokes/<joke_id>/refresh')
@auth_helpers.require_admin
def admin_joke_book_refresh(book_id: str, joke_id: str):
  """Return latest images and cost for a single joke in a book."""
  logger.info(f'Refreshing joke {joke_id} for book {book_id}')
  client = firestore.db()
  joke_ref = client.collection('jokes').document(joke_id)
  joke_doc = joke_ref.get()
  if not getattr(joke_doc, 'exists', False):
    return flask.jsonify({'error': 'Joke not found'}), 404

  joke_data = joke_doc.to_dict() or {}
  metadata_ref = joke_ref.collection('metadata').document('metadata')
  metadata_doc = metadata_ref.get()
  setup_url = None
  punchline_url = None
  setup_variants: list[str] = []
  punchline_variants: list[str] = []
  if getattr(metadata_doc, 'exists', False):
    metadata = metadata_doc.to_dict() or {}
    setup_url = metadata.get('book_page_setup_image_url')
    punchline_url = metadata.get('book_page_punchline_image_url')
    setup_variants = metadata.get('all_book_page_setup_image_urls') or []
    punchline_variants = metadata.get(
      'all_book_page_punchline_image_urls') or []

  resp_data = {
    'id':
    joke_id,
    'setup_image':
    _format_book_page_image(setup_url),
    'punchline_image':
    _format_book_page_image(punchline_url),
    'setup_original_image':
    _format_book_page_image(joke_data.get('setup_image_url')),
    'punchline_original_image':
    _format_book_page_image(joke_data.get('punchline_image_url')),
    'setup_image_download':
    _format_book_page_download(setup_url),
    'punchline_image_download':
    _format_book_page_download(punchline_url),
    'total_cost':
    _extract_total_cost(joke_data),
    'setup_original_preview':
    _format_joke_preview(joke_data.get('setup_image_url')),
    'punchline_original_preview':
    _format_joke_preview(joke_data.get('punchline_image_url')),
    'setup_variants':
    [_format_book_page_thumb(url) for url in setup_variants if url],
    'punchline_variants':
    [_format_book_page_thumb(url) for url in punchline_variants if url],
    'num_views':
    int(joke_data.get('num_viewed_users') or 0),
    'num_saves':
    int(joke_data.get('num_saved_users') or 0),
    'num_shares':
    int(joke_data.get('num_shared_users') or 0),
    'popularity_score':
    float(joke_data.get('popularity_score') or 0.0),
    'num_saved_users_fraction':
    float(joke_data.get('num_saved_users_fraction') or 0.0),
  }
  return flask.jsonify(resp_data)


@web_bp.route('/admin/joke-books/<book_id>/jokes/add', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_add_joke(book_id: str):
  """Add a joke or multiple jokes to the book."""
  payload = flask.request.get_json(silent=True) or {}
  joke_ids = payload.get('joke_ids')

  if not joke_ids:
    return flask.jsonify({'error': 'joke_ids is required'}), 400

  try:
    joke_book_operations.add_jokes_to_book(book_id, joke_ids)
    return flask.jsonify({'status': 'ok'})
  except Exception as exc:
    logger.error('Failed to add jokes', exc_info=exc)
    return flask.jsonify({'error': str(exc)}), 500


@web_bp.route('/admin/joke-books/<book_id>/jokes/<joke_id>/remove',
              methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_remove_joke(book_id: str, joke_id: str):
  """Remove a joke from the book."""
  try:
    joke_book_operations.remove_joke_from_book(book_id, joke_id)
    return flask.jsonify({'status': 'ok'})
  except Exception as exc:
    logger.error('Failed to remove joke', exc_info=exc)
    return flask.jsonify({'error': str(exc)}), 500


@web_bp.route('/admin/joke-books/<book_id>/jokes/<joke_id>/reorder',
              methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_reorder_joke(book_id: str, joke_id: str):
  """Reorder a joke in the book."""
  payload = flask.request.get_json(silent=True) or {}
  new_position = payload.get('new_position')
  if new_position is None:
    return flask.jsonify({'error': 'new_position is required'}), 400

  try:
    # Convert from 1-based UI index to 0-based list index
    idx = int(new_position) - 1
    joke_book_operations.reorder_joke_in_book(book_id, joke_id, idx)
    return flask.jsonify({'status': 'ok'})
  except Exception as exc:
    logger.error('Failed to reorder joke', exc_info=exc)
    return flask.jsonify({'error': str(exc)}), 500


@web_bp.route('/admin/joke-books/upload-image', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_upload_image():
  """Upload a custom image for a joke setup/punchline or book page."""
  logger.info(f"Admin joke book upload image request: {flask.request.form}")

  joke_id = flask.request.form.get('joke_id')
  book_id = flask.request.form.get('joke_book_id') or 'manual'
  target_field = flask.request.form.get('target_field')
  file = flask.request.files.get('file')
  logger.info(
    f"Joke ID: {joke_id}, Book ID: {book_id}, Target field: {target_field}, File: {file}"
  )

  if not joke_id or not target_field or not file:
    return flask.Response('Missing required fields', 400)

  allowed_fields = {
    'book_page_setup_image_url',
    'book_page_punchline_image_url',
    'setup_image_url',
    'punchline_image_url',
  }

  if target_field not in allowed_fields:
    return flask.Response(f'Invalid target field: {target_field}', 400)

  if not file.filename:
    return flask.Response('No filename', 400)

  ext = os.path.splitext(file.filename)[1].lower()
  if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
    return flask.Response('Invalid file type', 400)

  timestamp = datetime.datetime.now(
    datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')

  if target_field.startswith('book_page'):
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"joke_books/{book_id}/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"
  else:
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"jokes/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"

  gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{gcs_path}"

  try:
    content = file.read()
    cloud_storage.upload_bytes_to_gcs(
      content, gcs_uri, file.content_type or 'application/octet-stream')
  except Exception as exc:
    logger.error('Failed to upload image', exc_info=exc)
    return flask.Response('Upload failed', 500)

  public_url = cloud_storage.get_public_image_cdn_url(gcs_uri)
  client = firestore.db()
  joke_ref = client.collection('jokes').document(joke_id)

  if target_field.startswith('book_page'):
    metadata_ref = joke_ref.collection('metadata').document('metadata')
    variant_field = f"all_{target_field}s"

    if not metadata_ref.get().exists:
      metadata_ref.set({})

    metadata_ref.update({
      target_field: public_url,
      variant_field: ArrayUnion([public_url]),
    })
  else:
    joke_ref.update({target_field: public_url})

  return flask.jsonify({'url': public_url})
