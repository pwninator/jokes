"""Admin joke category management routes."""

from __future__ import annotations

import flask
from firebase_functions import logger
from google.cloud.firestore import DELETE_FIELD
from typing import Any, cast

from common import config, joke_category_operations, models, utils
from functions import auth_helpers
from services import cloud_storage
from services import firestore
from web.routes import web_bp


def _get_category_lunchbox_pdf_gcs_uris() -> dict[str, str]:
  """Fetch live lunchbox PDF URIs from the main category documents."""
  docs: Any = firestore.db().collection("joke_categories").stream()
  results: dict[str, str] = {}
  for doc in docs:
    if not getattr(doc, "exists", False):
      continue
    raw_data: Any = doc.to_dict()
    if not isinstance(raw_data, dict):
      continue
    data = cast(dict[str, object], raw_data)
    raw_pdf_gcs_uri = data.get("lunchbox_notes_pdf_gcs_uri")
    pdf_gcs_uri = raw_pdf_gcs_uri.strip() if isinstance(raw_pdf_gcs_uri,
                                                        str) else ""
    if pdf_gcs_uri:
      results[doc.id] = pdf_gcs_uri
  return results


@web_bp.route('/admin/joke-categories')
@auth_helpers.require_admin
def admin_joke_categories():
  """Render joke category admin page."""
  categories = firestore.get_all_joke_categories(
    fetch_cached_jokes=True,
    use_cache=True,
  )
  lunchbox_pdf_gcs_uris = _get_category_lunchbox_pdf_gcs_uris()
  for category in categories:
    category_id = getattr(category, "id", None)
    if isinstance(category_id, str) and category_id in lunchbox_pdf_gcs_uris:
      category.lunchbox_notes_pdf_gcs_uri = lunchbox_pdf_gcs_uris[category_id]

  def _state_key(category: models.JokeCategory) -> str:
    return (category.state or "").upper()

  def _unique_joke_count(
    categories_in_section: list[models.JokeCategory], ) -> int:
    seen: set[str] = set()
    for category in categories_in_section:
      for joke in category.jokes:
        joke_id = joke.key
        if isinstance(joke_id, str) and joke_id:
          seen.add(joke_id)
    return len(seen)

  approved: list[models.JokeCategory] = []
  seasonal: list[models.JokeCategory] = []
  proposed: list[models.JokeCategory] = []
  rejected: list[models.JokeCategory] = []
  book: list[models.JokeCategory] = []
  for category in categories:
    state = _state_key(category)
    if state == "APPROVED":
      approved.append(category)
    elif state == "SEASONAL":
      seasonal.append(category)
    elif state == "PROPOSED":
      proposed.append(category)
    elif state == "BOOK":
      book.append(category)
    else:
      rejected.append(category)

  uncategorized = firestore.get_uncategorized_public_jokes(categories)
  uncategorized_unique_count = len({
    j.key
    for j in (uncategorized or [])
    if isinstance(getattr(j, "key", None), str) and j.key
  })

  return flask.render_template(
    'admin/joke_categories.html',
    site_name='Snickerdoodle',
    joke_search_default_threshold=config.JOKE_SEARCH_TIGHT_THRESHOLD,
    approved_unique_joke_count=_unique_joke_count(approved),
    seasonal_unique_joke_count=_unique_joke_count(seasonal),
    proposed_unique_joke_count=_unique_joke_count(proposed),
    rejected_unique_joke_count=_unique_joke_count(rejected),
    book_unique_joke_count=_unique_joke_count(book),
    uncategorized_unique_joke_count=uncategorized_unique_count,
    approved_categories=approved,
    seasonal_categories=seasonal,
    proposed_categories=proposed,
    rejected_categories=rejected,
    book_categories=book,
    uncategorized_jokes=uncategorized,
    created=flask.request.args.get('created'),
    updated=flask.request.args.get('updated'),
    notes_generated=flask.request.args.get('notes_generated'),
    error=flask.request.args.get('error'),
    public_file_url_for_gcs=cloud_storage.get_public_cdn_url,
    joke_creation_url=utils.joke_creation_big_url(),
  )


@web_bp.route('/admin/joke-categories/<category_id>/live')
@auth_helpers.require_admin
def admin_get_joke_category_live(category_id: str):
  """Return live category fields for edit-form hydration.

  The admin categories page lists categories from `joke_cache/joke_categories`
  for speed, but the edit form needs live fields from `joke_categories/{id}`.
  """
  category_id = (category_id or "").strip()
  if not category_id:
    return flask.jsonify({"error": "missing_category_id"}), 400

  doc = firestore.db().collection("joke_categories").document(
    category_id).get()
  if not getattr(doc, "exists", False):
    return flask.jsonify({"error": "not_found"}), 404

  category = models.JokeCategory.from_firestore_dict(doc.to_dict() or {},
                                                     key=category_id)

  return flask.jsonify({
    "category_id":
    category.id or category_id,
    "display_name":
    category.display_name or "",
    "state": (category.state or "PROPOSED").upper(),
    "joke_description_query":
    category.joke_description_query or "",
    "search_distance":
    category.search_distance,
    "seasonal_name":
    category.seasonal_name or "",
    "book_id":
    category.book_id or "",
    "tags":
    category.tags or [],
    "negative_tags":
    category.negative_tags or [],
    "image_url":
    category.image_url or "",
    "image_description":
    category.image_description or "",
    "joke_id_order":
    category.joke_id_order or [],
  })


@web_bp.route('/admin/joke-categories/create', methods=['POST'])
@auth_helpers.require_admin
def admin_create_joke_category():
  """Create a joke category and initialize its cache."""
  form = flask.request.form or {}
  display_name = (form.get('display_name') or '').strip()
  image_description = (form.get('image_description') or '').strip()

  joke_description_query = (form.get('joke_description_query') or '').strip()
  search_distance_raw = (form.get('search_distance') or '').strip()
  seasonal_name = (form.get('seasonal_name') or '').strip()
  book_id = (form.get('book_id') or '').strip()
  tags_raw = (form.get('tags') or '').strip()
  negative_tags_raw = (form.get('negative_tags') or '').strip()

  search_distance = None
  if search_distance_raw:
    try:
      search_distance = float(search_distance_raw)
    except ValueError:
      return flask.redirect(
        '/admin/joke-categories?error=search_distance_invalid')

  def _parse_tags(raw: str) -> list[str]:
    if not raw:
      return []
    seen: set[str] = set()
    result: list[str] = []
    for part in raw.split(','):
      tag = (part or '').strip()
      if not tag or tag in seen:
        continue
      seen.add(tag)
      result.append(tag)
    return result

  tags = _parse_tags(tags_raw)
  negative_tags = _parse_tags(negative_tags_raw)

  if not display_name:
    return flask.redirect('/admin/joke-categories?error=display_name_required')

  if not joke_description_query and not seasonal_name and not tags and not book_id:
    return flask.redirect(
      '/admin/joke-categories?error=category_source_required')

  try:
    category_id = firestore.create_joke_category(
      display_name=display_name,
      state="PROPOSED",
      joke_description_query=joke_description_query or None,
      seasonal_name=seasonal_name or None,
      book_id=book_id or None,
      search_distance=search_distance,
      tags=tags or None,
      negative_tags=negative_tags or None,
      image_description=image_description or None,
    )

    category_data: dict[str, object] = {
      'state': 'PROPOSED',
      'joke_description_query': joke_description_query,
      'seasonal_name': seasonal_name,
      'book_id': book_id,
      'search_distance': search_distance,
      'tags': tags,
      'negative_tags': negative_tags,
    }
    if image_description:
      category_data['image_description'] = image_description

    _ = joke_category_operations.refresh_single_category_cache(
      category_id,
      category_data,
    )
    _ = joke_category_operations.rebuild_joke_categories_index()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed creating category {display_name}: {exc}")
    return flask.redirect('/admin/joke-categories?error=create_failed')

  return flask.redirect('/admin/joke-categories?created=1')


@web_bp.route('/admin/joke-categories/<category_id>/update', methods=['POST'])
@auth_helpers.require_admin
def admin_update_joke_category(category_id: str):
  """Update a joke category document and refresh its cache."""
  form = flask.request.form or {}
  display_name = (form.get('display_name') or '').strip()
  state = (form.get('state') or 'PROPOSED').strip().upper()

  joke_description_query = (form.get('joke_description_query') or '').strip()
  search_distance_raw = (form.get('search_distance') or '').strip()
  seasonal_name = (form.get('seasonal_name') or '').strip()
  book_id = (form.get('book_id') or '').strip()
  tags_raw = (form.get('tags') or '').strip()
  negative_tags_raw = (form.get('negative_tags') or '').strip()

  search_distance = None
  if search_distance_raw:
    try:
      search_distance = float(search_distance_raw)
    except ValueError:
      return flask.redirect(
        '/admin/joke-categories?error=search_distance_invalid')

  def _parse_tags(raw: str) -> list[str]:
    if not raw:
      return []
    seen: set[str] = set()
    result: list[str] = []
    for part in raw.split(','):
      tag = (part or '').strip()
      if not tag or tag in seen:
        continue
      seen.add(tag)
      result.append(tag)
    return result

  tags = _parse_tags(tags_raw)
  negative_tags = _parse_tags(negative_tags_raw)

  image_url = (form.get('image_url') or '').strip()
  image_description = (form.get('image_description') or '').strip()
  joke_id_order_raw = (form.get('joke_id_order') or '').strip()

  all_image_urls = None
  if 'all_image_urls' in form:
    all_image_urls_raw = (form.get('all_image_urls') or '').splitlines()
    parsed: list[str] = []
    seen: set[str] = set()
    for line in all_image_urls_raw:
      url = (line or '').strip()
      if not url or url in seen:
        continue
      seen.add(url)
      parsed.append(url)
    all_image_urls = parsed

  if not category_id:
    return flask.redirect('/admin/joke-categories?error=missing_category_id')
  if not display_name:
    return flask.redirect('/admin/joke-categories?error=display_name_required')

  if not joke_description_query and not seasonal_name and not tags and not book_id:
    return flask.redirect(
      '/admin/joke-categories?error=category_source_required')

  joke_id_order = []
  if joke_id_order_raw:
    joke_id_order = [
      jid.strip() for jid in joke_id_order_raw.split(',') if jid.strip()
    ]

  payload: dict[str, object] = {
    'display_name':
    display_name,
    'state':
    state,
    'seasonal_name':
    seasonal_name if seasonal_name else DELETE_FIELD,
    'joke_description_query':
    joke_description_query if joke_description_query else DELETE_FIELD,
    'book_id':
    book_id if book_id else DELETE_FIELD,
    'search_distance':
    search_distance if search_distance is not None else DELETE_FIELD,
    'tags':
    tags if tags else DELETE_FIELD,
    'negative_tags':
    negative_tags if negative_tags else DELETE_FIELD,
    'image_description':
    image_description if image_description else DELETE_FIELD,
    'joke_id_order':
    joke_id_order if joke_id_order else DELETE_FIELD,
  }
  if 'image_url' in form:
    payload['image_url'] = image_url if image_url else DELETE_FIELD
  if all_image_urls is not None:
    payload[
      'all_image_urls'] = all_image_urls if all_image_urls else DELETE_FIELD

  try:
    client = firestore.db()
    _ = client.collection('joke_categories').document(category_id).set(
      payload,
      merge=True,
    )

    refresh_payload: dict[str, object] = {
      'state': state,
      'seasonal_name': seasonal_name,
      'joke_description_query': joke_description_query,
      'book_id': book_id,
      'search_distance': search_distance,
      'tags': tags,
      'negative_tags': negative_tags,
      'joke_id_order': joke_id_order,
    }
    _ = joke_category_operations.refresh_single_category_cache(
      category_id,
      refresh_payload,
    )
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed updating category {category_id}: {exc}")
    return flask.redirect('/admin/joke-categories?error=update_failed')

  return flask.redirect(f'/admin/joke-categories?updated={category_id}')
