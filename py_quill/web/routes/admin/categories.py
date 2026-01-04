"""Admin joke category management routes."""

from __future__ import annotations

import flask
from firebase_functions import logger
from google.cloud.firestore import DELETE_FIELD

from common import joke_category_operations
from functions import auth_helpers
from services import firestore
from web.routes import web_bp


@web_bp.route('/admin/joke-categories')
@auth_helpers.require_admin
def admin_joke_categories():
  """Render joke category admin page."""
  categories = firestore.get_all_joke_categories(fetch_cached_jokes=True)

  def _state_key(category) -> str:
    state = (getattr(category, "state", None) or "").upper()
    return state

  approved: list = []
  proposed: list = []
  rejected: list = []
  for category in categories:
    state = _state_key(category)
    if state == "APPROVED":
      approved.append(category)
    elif state == "PROPOSED":
      proposed.append(category)
    else:
      rejected.append(category)

  uncategorized = firestore.get_uncategorized_public_jokes(categories)

  return flask.render_template(
    'admin/joke_categories.html',
    site_name='Snickerdoodle',
    approved_categories=approved,
    proposed_categories=proposed,
    rejected_categories=rejected,
    uncategorized_jokes=uncategorized,
    created=flask.request.args.get('created'),
    updated=flask.request.args.get('updated'),
    error=flask.request.args.get('error'),
  )


@web_bp.route('/admin/joke-categories/create', methods=['POST'])
@auth_helpers.require_admin
def admin_create_joke_category():
  """Create a joke category and initialize its cache."""
  form = flask.request.form or {}
  category_type = (form.get('category_type') or '').strip().lower()
  display_name = (form.get('display_name') or '').strip()
  image_description = (form.get('image_description') or '').strip()

  joke_description_query = (form.get('joke_description_query') or '').strip()
  seasonal_name = (form.get('seasonal_name') or '').strip()

  if not display_name:
    return flask.redirect('/admin/joke-categories?error=display_name_required')

  if category_type == 'seasonal':
    if not seasonal_name:
      return flask.redirect(
        '/admin/joke-categories?error=seasonal_name_required')
    joke_description_query = ''
  else:
    # Default to search type.
    if not joke_description_query:
      return flask.redirect(
        '/admin/joke-categories?error=joke_description_query_required')
    seasonal_name = ''

  try:
    category_id = firestore.create_joke_category(
      display_name=display_name,
      state='PROPOSED',
      joke_description_query=joke_description_query or None,
      seasonal_name=seasonal_name or None,
      image_description=image_description or None,
    )

    category_data = {
      'state': 'PROPOSED',
      'joke_description_query': joke_description_query,
      'seasonal_name': seasonal_name,
    }
    if image_description:
      category_data['image_description'] = image_description

    joke_category_operations.refresh_single_category_cache(
      category_id,
      category_data,
    )
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

  category_type = (form.get('category_type') or '').strip().lower()
  joke_description_query = (form.get('joke_description_query') or '').strip()
  seasonal_name = (form.get('seasonal_name') or '').strip()

  image_url = (form.get('image_url') or '').strip()
  image_description = (form.get('image_description') or '').strip()
  all_image_urls = None
  if 'all_image_urls' in form:
    all_image_urls_raw = (form.get('all_image_urls') or '').splitlines()
    parsed = []
    seen = set()
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

  is_seasonal = category_type == 'seasonal' or bool(seasonal_name)
  if is_seasonal:
    if not seasonal_name:
      return flask.redirect(
        '/admin/joke-categories?error=seasonal_name_required')
    joke_description_query = ''
  else:
    if not joke_description_query:
      return flask.redirect(
        '/admin/joke-categories?error=joke_description_query_required')
    seasonal_name = ''

  payload: dict[str, object] = {
    'display_name':
    display_name,
    'state':
    state,
    'seasonal_name':
    seasonal_name if seasonal_name else DELETE_FIELD,
    'joke_description_query':
    joke_description_query if joke_description_query else DELETE_FIELD,
    'image_description':
    image_description if image_description else DELETE_FIELD,
  }
  if 'image_url' in form:
    payload['image_url'] = image_url if image_url else DELETE_FIELD
  if all_image_urls is not None:
    payload[
      'all_image_urls'] = all_image_urls if all_image_urls else DELETE_FIELD

  try:
    client = firestore.db()
    client.collection('joke_categories').document(category_id).set(
      payload,
      merge=True,
    )

    joke_category_operations.refresh_single_category_cache(
      category_id,
      {
        'state': state,
        'seasonal_name': seasonal_name,
        'joke_description_query': joke_description_query,
      },
    )
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Failed updating category {category_id}: {exc}")
    return flask.redirect('/admin/joke-categories?error=update_failed')

  return flask.redirect(f'/admin/joke-categories?updated={category_id}')
