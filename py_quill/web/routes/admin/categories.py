"""Admin joke category management routes."""

from __future__ import annotations

import flask
from firebase_functions import logger

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
