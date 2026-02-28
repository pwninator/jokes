"""Admin joke book management routes."""

from __future__ import annotations

import datetime
from io import BytesIO
from pathlib import Path
from typing import cast

import flask
from common import (book_defs, config, image_generation,
                    joke_book_operations, models, utils)
from firebase_functions import logger
from functions import auth_helpers
from PIL import Image, UnidentifiedImageError
from services import cloud_storage
from storage import joke_books_firestore
from web.routes import web_bp
from web.routes.admin import joke_feed_utils


def _as_object_dict(value: object) -> dict[str, object]:
  """Return a shallow string-keyed dict view of a JSON-like object."""
  if not isinstance(value, dict):
    return {}
  return dict(cast(dict[str, object], value))


def _as_optional_string(value: object) -> str | None:
  """Return a non-empty string value, or None."""
  if isinstance(value, str) and value:
    return value
  return None


def _as_string_list(value: object) -> list[str]:
  """Return a filtered list of non-empty strings."""
  if not isinstance(value, list):
    return []
  return [
    item for item in cast(list[object], value)
    if isinstance(item, str) and item
  ]


def _as_int(value: object, default: int = 0) -> int:
  """Convert a numeric-like value to int with fallback."""
  if isinstance(value, bool):
    return int(value)
  if isinstance(value, int):
    return value
  if isinstance(value, float):
    return int(value)
  if isinstance(value, str):
    stripped = value.strip()
    if stripped:
      try:
        return int(stripped)
      except ValueError:
        return default
  return default


def _as_float(value: object, default: float = 0.0) -> float:
  """Convert a numeric-like value to float with fallback."""
  if isinstance(value, (int, float)):
    return float(value)
  if isinstance(value, str):
    stripped = value.strip()
    if stripped:
      try:
        return float(stripped)
      except ValueError:
        return default
  return default


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


def _format_book_asset_preview(gcs_uri: str | None) -> str | None:
  """Create a preview URL for a stored book-level asset."""
  if not gcs_uri:
    return None
  try:
    return cloud_storage.get_public_image_cdn_url(
      gcs_uri,
      width=800,
      quality=75,
    )
  except ValueError:
    return None


def _book_definition_options() -> list[dict[str, str]]:
  """Return admin-select options for available book definitions."""
  options: list[dict[str, str]] = []
  for book_key, book in sorted(
      book_defs.BOOKS.items(),
      key=lambda item: item[1].title,
  ):
    if book_defs.BookFormat.PAPERBACK not in book.variants:
      continue
    options.append({
      'value': book_key.value,
      'title': book.title,
    })
  return options


def _extract_total_cost(joke_data: dict[str, object]) -> float | None:
  """Safely extract total generation cost from joke data."""
  generation_metadata = _as_object_dict(joke_data.get('generation_metadata'))
  if not generation_metadata:
    return None

  total_cost = generation_metadata.get('total_cost')
  if isinstance(total_cost, (int, float)):
    return float(total_cost)

  try:
    return models.GenerationMetadata.from_dict(generation_metadata).total_cost
  except Exception:
    return None


def _convert_to_png_bytes(raw_bytes: bytes) -> bytes:
  """Validate raw image bytes and return PNG-encoded bytes."""
  try:
    image = Image.open(BytesIO(raw_bytes))
    image.load()  # pyright: ignore[reportUnusedCallResult]
  except (UnidentifiedImageError, OSError, ValueError) as exc:
    raise ValueError('Invalid image file') from exc

  if image.mode in ('RGBA', 'LA') or (image.mode == 'P'
                                      and 'transparency' in image.info):
    image = image.convert('RGBA')
  elif image.mode != 'RGB':
    image = image.convert('RGB')

  buffer = BytesIO()
  image.save(buffer, format='PNG')
  return buffer.getvalue()


def _status_for_joke_book_error(message: str) -> int:
  """Map storage-layer joke-book errors to HTTP status codes."""
  if 'not found' in message or 'does not belong to book' in message:
    return 404
  return 400


@web_bp.route('/admin/joke-books')
@auth_helpers.require_admin
def admin_joke_books():
  """Render a simple table of all joke book documents."""
  books = joke_books_firestore.list_joke_books()
  return flask.render_template(
    'admin/joke_books.html',
    books=books,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books/<book_id>')
@auth_helpers.require_admin
def admin_joke_book_detail(book_id: str):
  """Render an image-centric view of a single joke book."""
  book, entries = joke_books_firestore.get_joke_book_detail_raw(book_id)
  if not book:
    return flask.Response('Joke book not found', status=404)

  joke_rows: list[dict[str, object]] = []
  total_book_cost = 0.0
  for sequence, entry in enumerate(entries, start=1):
    joke_id = str(entry.get('id') or '')
    joke_data = _as_object_dict(entry.get('joke'))
    metadata = _as_object_dict(entry.get('metadata'))
    setup_url = _as_optional_string(metadata.get('book_page_setup_image_url'))
    punchline_url = _as_optional_string(
      metadata.get('book_page_punchline_image_url'))
    setup_variants = _as_string_list(
      metadata.get('all_book_page_setup_image_urls'))
    punchline_variants = _as_string_list(
      metadata.get('all_book_page_punchline_image_urls'))
    book_page_ready = bool(metadata.get('book_page_ready', False))

    joke_data_for_card = dict(joke_data)
    _ = joke_data_for_card.setdefault('setup_text', '')
    _ = joke_data_for_card.setdefault('punchline_text', '')
    joke_model = models.PunnyJoke.from_firestore_dict(joke_data_for_card,
                                                      joke_id)
    edit_payload = joke_feed_utils.build_edit_payload(joke_model)

    joke_cost = _extract_total_cost(joke_data)
    if isinstance(joke_cost, (int, float)):
      total_book_cost += float(joke_cost)

    num_views = _as_int(joke_data.get('num_viewed_users'))
    num_saves = _as_int(joke_data.get('num_saved_users'))
    num_shares = _as_int(joke_data.get('num_shared_users'))
    popularity_score = _as_float(joke_data.get('popularity_score'))
    num_saved_users_fraction = _as_float(
      joke_data.get('num_saved_users_fraction'))

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
      _format_book_page_image(
        _as_optional_string(joke_data.get('setup_image_url'))),
      'punchline_original_image':
      _format_book_page_image(
        _as_optional_string(joke_data.get('punchline_image_url'))),
      'setup_original_image_raw':
      _as_optional_string(joke_data.get('setup_image_url')),
      'punchline_original_image_raw':
      _as_optional_string(joke_data.get('punchline_image_url')),
      'setup_preview':
      _format_joke_preview(
        _as_optional_string(joke_data.get('setup_image_url'))),
      'punchline_preview':
      _format_joke_preview(
        _as_optional_string(joke_data.get('punchline_image_url'))),
      'setup_variants': [{
        'image_url': url,
        'thumb_url': _format_book_page_thumb(url) or url,
      } for url in setup_variants if url],
      'punchline_variants': [{
        'image_url': url,
        'thumb_url': _format_book_page_thumb(url) or url,
      } for url in punchline_variants if url],
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
      'book_page_ready':
      book_page_ready,
    })

  if utils.is_emulator():
    generate_book_page_url = "http://127.0.0.1:5001/storyteller-450807/us-central1/generate_joke_book_page"
  else:
    generate_book_page_url = "https://generate-joke-book-page-uqdkqas7gq-uc.a.run.app"

  return flask.render_template(
    'admin/joke_book_detail.html',
    book=book,
    book_definition_options=_book_definition_options(),
    belongs_to_page_preview_url=_format_book_asset_preview(
      book.belongs_to_page_gcs_uri),
    jokes=joke_rows,
    generate_book_page_url=generate_book_page_url,
    update_book_page_url=flask.url_for('web.admin_update_joke_book_page'),
    set_main_image_url=flask.url_for(
      'web.admin_set_main_joke_image_from_book_page'),
    upload_belongs_to_page_url=flask.url_for(
      'web.admin_joke_book_upload_belongs_to_page'),
    update_associated_book_url=flask.url_for(
      'web.admin_joke_book_update_associated_book'),
    joke_creation_url=utils.joke_creation_url(),
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
  remove_setup_url = flask.request.form.get('remove_book_page_setup_image_url')
  remove_punchline_url = flask.request.form.get(
    'remove_book_page_punchline_image_url')

  if not book_id or not joke_id:
    return flask.Response('joke_book_id and joke_id are required', 400)

  if (not new_setup_url and not new_punchline_url and not remove_setup_url
      and not remove_punchline_url):
    return flask.Response(('Provide new_book_page_setup_image_url, '
                           'new_book_page_punchline_image_url, '
                           'remove_book_page_setup_image_url, or '
                           'remove_book_page_punchline_image_url'), 400)

  try:
    setup_response, punchline_response = (
      joke_books_firestore.update_book_page_selection(
        book_id=book_id,
        joke_id=joke_id,
        new_setup_url=new_setup_url,
        new_punchline_url=new_punchline_url,
        remove_setup_url=remove_setup_url,
        remove_punchline_url=remove_punchline_url,
      ))
  except ValueError as exc:
    return flask.Response(str(exc), _status_for_joke_book_error(str(exc)))

  return flask.jsonify({
    'book_id': book_id,
    'joke_id': joke_id,
    'book_page_setup_image_url': setup_response,
    'book_page_punchline_image_url': punchline_response,
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

  try:
    page_url = joke_books_firestore.promote_book_page_image_to_main(
      book_id=book_id,
      joke_id=joke_id,
      target=target,
    )
  except ValueError as exc:
    return flask.Response(str(exc), _status_for_joke_book_error(str(exc)))

  main_field = 'setup_image_url' if target == 'setup' else 'punchline_image_url'
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
  book = joke_books_firestore.get_joke_book(book_id)
  if not book or joke_id not in book.jokes:
    return flask.jsonify({'error': 'Joke not found'}), 404

  joke_data, metadata = joke_books_firestore.get_joke_with_metadata(joke_id)
  if joke_data is None:
    return flask.jsonify({'error': 'Joke not found'}), 404

  joke_data = _as_object_dict(joke_data)
  metadata = _as_object_dict(metadata)
  setup_url = _as_optional_string(metadata.get('book_page_setup_image_url'))
  punchline_url = _as_optional_string(
    metadata.get('book_page_punchline_image_url'))
  setup_variants = _as_string_list(
    metadata.get('all_book_page_setup_image_urls'))
  punchline_variants = _as_string_list(
    metadata.get('all_book_page_punchline_image_urls'))

  resp_data = {
    'id':
    joke_id,
    'setup_image':
    _format_book_page_image(setup_url),
    'punchline_image':
    _format_book_page_image(punchline_url),
    'setup_original_image':
    _format_book_page_image(
      _as_optional_string(joke_data.get('setup_image_url'))),
    'punchline_original_image':
    _format_book_page_image(
      _as_optional_string(joke_data.get('punchline_image_url'))),
    'setup_original_image_raw':
    _as_optional_string(joke_data.get('setup_image_url')),
    'punchline_original_image_raw':
    _as_optional_string(joke_data.get('punchline_image_url')),
    'setup_image_download':
    _format_book_page_download(setup_url),
    'punchline_image_download':
    _format_book_page_download(punchline_url),
    'total_cost':
    _extract_total_cost(joke_data),
    'setup_original_preview':
    _format_joke_preview(_as_optional_string(
      joke_data.get('setup_image_url'))),
    'punchline_original_preview':
    _format_joke_preview(
      _as_optional_string(joke_data.get('punchline_image_url'))),
    'setup_variants': [{
      'image_url': url,
      'thumb_url': _format_book_page_thumb(url) or url,
    } for url in setup_variants if url],
    'punchline_variants': [{
      'image_url': url,
      'thumb_url': _format_book_page_thumb(url) or url,
    } for url in punchline_variants if url],
    'num_views':
    _as_int(joke_data.get('num_viewed_users')),
    'num_saves':
    _as_int(joke_data.get('num_saved_users')),
    'num_shares':
    _as_int(joke_data.get('num_shared_users')),
    'popularity_score':
    _as_float(joke_data.get('popularity_score')),
    'num_saved_users_fraction':
    _as_float(joke_data.get('num_saved_users_fraction')),
  }
  return flask.jsonify(resp_data)


@web_bp.route('/admin/joke-books/<book_id>/jokes/add', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_add_joke(book_id: str):
  """Add a joke or multiple jokes to the book."""
  payload = _as_object_dict(flask.request.get_json(silent=True))
  joke_ids = _as_string_list(payload.get('joke_ids'))

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
  payload = _as_object_dict(flask.request.get_json(silent=True))
  new_position = payload.get('new_position')
  if new_position is None:
    return flask.jsonify({'error': 'new_position is required'}), 400

  try:
    # Convert from 1-based UI index to 0-based list index
    idx = int(cast(int | float | str, new_position)) - 1
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

  try:
    png_bytes = _convert_to_png_bytes(file.read())
  except ValueError as exc:
    logger.warn(f'Invalid image upload: {exc}')
    return flask.Response('Invalid image file', 400)

  timestamp = datetime.datetime.now(
    datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
  ext = '.png'

  if target_field.startswith('book_page'):
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"joke_books/{book_id}/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"
  else:
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"jokes/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"

  gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{gcs_path}"

  try:
    _ = cloud_storage.upload_bytes_to_gcs(png_bytes, gcs_uri, 'image/png')
  except Exception as exc:
    logger.error('Failed to upload image', exc_info=exc)
    return flask.Response('Upload failed', 500)

  public_url = cloud_storage.get_public_image_cdn_url(gcs_uri)
  joke_books_firestore.persist_uploaded_joke_image(
    joke_id=joke_id,
    book_id=book_id,
    target_field=target_field,
    public_url=public_url,
  )

  return flask.jsonify({'url': public_url})


@web_bp.route('/admin/joke-books/upload-belongs-to-page', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_upload_belongs_to_page():
  """Upload and persist the belongs-to page image for a joke book."""
  book_id = flask.request.form.get('joke_book_id')
  file = flask.request.files.get('file')

  if not book_id or not file:
    return flask.Response('Missing required fields', 400)

  book = joke_books_firestore.get_joke_book(book_id)
  if not book:
    return flask.Response('Joke book not found', 404)
  if not file.filename:
    return flask.Response('No filename', 400)

  content_type = (file.mimetype or '').strip() or 'application/octet-stream'
  if not content_type.startswith('image/'):
    return flask.Response('Invalid image file', 400)

  file_bytes = file.read()
  if not file_bytes:
    return flask.Response('Invalid image file', 400)

  suffix = Path(file.filename).suffix.lower()
  file_name = utils.create_timestamped_firestore_key(
    'belongs_to',
    book.book_name or book.id or 'book',
  )
  gcs_path = f'_joke_assets/book/{file_name}{suffix}'
  gcs_uri = f'gs://{config.IMAGE_BUCKET_NAME}/{gcs_path}'

  try:
    _ = cloud_storage.upload_bytes_to_gcs(
      file_bytes,
      gcs_uri,
      content_type,
    )
  except Exception as exc:
    logger.error('Failed to upload belongs-to page', exc_info=exc)
    return flask.Response('Upload failed', 500)

  updated_book = joke_books_firestore.update_joke_book_belongs_to_page(
    book_id,
    belongs_to_page_gcs_uri=gcs_uri,
  )
  preview_url = _format_book_asset_preview(
    updated_book.belongs_to_page_gcs_uri)
  return flask.jsonify({
    'belongs_to_page_gcs_uri': updated_book.belongs_to_page_gcs_uri,
    'preview_url': preview_url,
  })


@web_bp.route('/admin/joke-books/update-associated-book', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_update_associated_book():
  """Update the optional associated book definition for a joke book."""
  book_id = flask.request.form.get('joke_book_id')
  if not book_id:
    return flask.Response('joke_book_id is required', 400)

  associated_book_key = flask.request.form.get('associated_book_key')
  try:
    updated_book = joke_books_firestore.update_joke_book_associated_book_key(
      book_id,
      associated_book_key=associated_book_key,
    )
  except ValueError as exc:
    return flask.Response(str(exc), _status_for_joke_book_error(str(exc)))

  associated_book_title = None
  if updated_book.associated_book_key:
    associated_book_title = book_defs.BOOKS[book_defs.BookKey(
      updated_book.associated_book_key)].title

  return flask.jsonify({
    'associated_book_key': updated_book.associated_book_key,
    'associated_book_title': associated_book_title,
  })
