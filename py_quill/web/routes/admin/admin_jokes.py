"""Admin jokes list routes."""

from __future__ import annotations

import datetime

import flask
from common import image_generation, models
from functions import auth_helpers
from services import firestore
from web.routes import web_bp
from web.routes.admin import joke_feed_utils

_JOKES_PER_PAGE = 10
_JOKE_IMAGE_SIZE = 350

_ALL_STATES: list[models.JokeState] = [
  models.JokeState.UNKNOWN,
  models.JokeState.DRAFT,
  models.JokeState.UNREVIEWED,
  models.JokeState.APPROVED,
  models.JokeState.REJECTED,
  models.JokeState.DAILY,
  models.JokeState.PUBLISHED,
]

_DEFAULT_SELECTED_STATES: list[models.JokeState] = [
  models.JokeState.UNKNOWN,
  models.JokeState.DRAFT,
  models.JokeState.UNREVIEWED,
  models.JokeState.APPROVED,
]


def _parse_state_filters(value: str | None) -> list[models.JokeState]:
  if not value:
    return list(_DEFAULT_SELECTED_STATES)

  parts = [p.strip().upper() for p in value.split(',') if p.strip()]
  selected: list[models.JokeState] = []
  seen: set[models.JokeState] = set()
  for part in parts:
    try:
      state = models.JokeState[part]
    except KeyError:
      continue
    if state in seen:
      continue
    seen.add(state)
    selected.append(state)

  return selected or list(_DEFAULT_SELECTED_STATES)


@web_bp.route('/admin/jokes')
@auth_helpers.require_admin
def admin_jokes():
  """Render admin jokes page with state filters + infinite scroll."""
  selected_states = _parse_state_filters(flask.request.args.get('states'))
  query_cursor = flask.request.args.get('cursor', default=None)
  selected_category_id = joke_feed_utils.parse_category_filter(
    flask.request.args.get("category"))
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  all_categories = firestore.get_all_joke_categories(use_cache=True)
  all_categories = [
    c for c in all_categories
    if (c.state or "").strip() in ("APPROVED", "SEASONAL")
  ]

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=selected_states,
    cursor=query_cursor,
    limit=_JOKES_PER_PAGE,
    category_id=selected_category_id,
  )
  jokes_list = joke_feed_utils.build_feed_entries(
    joke_entries,
    now_utc=now_utc,
  )

  selected_states_param = ",".join([s.value for s in selected_states])

  return flask.render_template(
    'admin/admin_jokes.html',
    site_name='Snickerdoodle',
    joke_creation_url=joke_feed_utils.joke_creation_url(),
    all_states=[s.value for s in _ALL_STATES],
    selected_states=[s.value for s in selected_states],
    selected_states_param=selected_states_param,
    categories=all_categories,
    selected_category_id=selected_category_id,
    jokes=jokes_list,
    next_cursor=next_cursor,
    has_more=next_cursor is not None,
    image_size=_JOKE_IMAGE_SIZE,
    image_qualities=list(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys()),
  )


@web_bp.route('/jokes/feed/load-more-admin-jokes')
@auth_helpers.require_admin
def admin_jokes_load_more():
  """API endpoint to load more admin jokes for infinite scroll."""
  cursor = flask.request.args.get('cursor', default=None)
  limit = flask.request.args.get('limit', default=_JOKES_PER_PAGE, type=int)
  selected_states = _parse_state_filters(flask.request.args.get('states'))
  selected_category_id = joke_feed_utils.parse_category_filter(
    flask.request.args.get("category"))
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=selected_states,
    cursor=cursor,
    limit=limit,
    category_id=selected_category_id,
  )
  jokes_list = joke_feed_utils.build_feed_entries(
    joke_entries,
    now_utc=now_utc,
  )

  html_fragments = flask.render_template(
    'components/joke_feed_fragment.html',
    jokes=jokes_list,
    image_size=_JOKE_IMAGE_SIZE,
    admin_state_badge_enabled=True,
    admin_stats_enabled=True,
    admin_edit_enabled=True,
  )

  response = {
    'html': html_fragments,
    'cursor': next_cursor,
    'has_more': next_cursor is not None,
  }

  resp = flask.make_response(flask.jsonify(response), 200)
  resp.headers['Content-Type'] = 'application/json; charset=utf-8'
  resp.headers['Cache-Control'] = 'no-store'
  return resp
