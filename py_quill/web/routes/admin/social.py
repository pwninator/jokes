"""Admin social routes."""

from __future__ import annotations

import datetime

import flask
from common import models
from functions import auth_helpers
from services import firestore
from web.routes import web_bp
from web.routes.admin import joke_feed_utils

_SOCIAL_JOKES_PER_PAGE = 100
_SOCIAL_IMAGE_SIZE = 200
_SOCIAL_STATES: list[models.JokeState] = [
  models.JokeState.DAILY,
  models.JokeState.PUBLISHED,
]


def _filter_public_entries(
  joke_entries: list[tuple[models.PunnyJoke, str]],
) -> list[tuple[models.PunnyJoke, str]]:
  """Filter joke entries to only include public and in public state."""
  return [(joke, cursor) for joke, cursor in joke_entries
          if joke.is_public_and_in_public_state]


@web_bp.route('/admin/social')
@auth_helpers.require_admin
def admin_social():
  """Render the social feed with public daily + published jokes."""
  query_cursor = flask.request.args.get('cursor', default=None)
  selected_category_id = joke_feed_utils.parse_category_filter(
    flask.request.args.get("category"))
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  all_categories = firestore.get_all_joke_categories(use_cache=True)
  all_categories = [
    c for c in all_categories
    if (c.state or "").strip() in ("APPROVED", "SEASONAL")
  ]
  social_posts = firestore.get_joke_social_posts()

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=_SOCIAL_STATES,
    cursor=query_cursor,
    limit=_SOCIAL_JOKES_PER_PAGE,
    category_id=selected_category_id,
  )
  joke_entries = _filter_public_entries(joke_entries)
  jokes_list = joke_feed_utils.build_feed_entries(
    joke_entries,
    now_utc=now_utc,
  )

  return flask.render_template(
    'admin/social.html',
    site_name='Snickerdoodle',
    joke_creation_url=joke_feed_utils.joke_creation_url(),
    categories=all_categories,
    selected_category_id=selected_category_id,
    jokes=jokes_list,
    next_cursor=next_cursor,
    has_more=next_cursor is not None,
    image_size=_SOCIAL_IMAGE_SIZE,
    social_posts=social_posts,
    post_type_options=[t.value for t in models.JokeSocialPostType],
    default_post_type=models.JokeSocialPostType.JOKE_GRID.value,
  )


@web_bp.route('/jokes/feed/load-more-admin-social')
@auth_helpers.require_admin
def admin_social_load_more():
  """API endpoint to load more social jokes for infinite scroll."""
  cursor = flask.request.args.get('cursor', default=None)
  limit = flask.request.args.get('limit',
                                 default=_SOCIAL_JOKES_PER_PAGE,
                                 type=int)
  selected_category_id = joke_feed_utils.parse_category_filter(
    flask.request.args.get("category"))
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=_SOCIAL_STATES,
    cursor=cursor,
    limit=limit,
    category_id=selected_category_id,
  )
  joke_entries = _filter_public_entries(joke_entries)
  jokes_list = joke_feed_utils.build_feed_entries(
    joke_entries,
    now_utc=now_utc,
  )

  html_fragments = flask.render_template(
    'components/joke_feed_fragment.html',
    jokes=jokes_list,
    image_size=_SOCIAL_IMAGE_SIZE,
    admin_stats_enabled=True,
    selectable_cards=True,
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
