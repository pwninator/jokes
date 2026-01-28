"""Admin joke picker API routes."""

from __future__ import annotations

import datetime

import flask
from common import models, utils
from functions import auth_helpers
from services import firestore
from web.routes import web_bp
from web.routes.admin import joke_feed_utils

_DEFAULT_JOKES_PER_PAGE = 100
_DEFAULT_IMAGE_SIZE = 200


def _parse_states(value: str | None) -> list[models.JokeState]:
  raw_values = [part.strip() for part in (value or "").split(",") if part]
  states: list[models.JokeState] = []
  for raw in raw_values:
    if raw in models.JokeState.__members__:
      states.append(models.JokeState[raw])
  return states


@web_bp.route("/admin/api/jokes/picker")
@auth_helpers.require_admin
def admin_joke_picker() -> flask.Response:
  """Return jokes for the admin joke picker."""
  states = _parse_states(flask.request.args.get("states"))
  if not states:
    return flask.make_response(
      flask.jsonify({"error": "states parameter required"}),
      400,
    )

  cursor = flask.request.args.get("cursor") or None
  category_id = joke_feed_utils.parse_category_filter(
    flask.request.args.get("category"), )
  limit = flask.request.args.get("limit",
                                 default=_DEFAULT_JOKES_PER_PAGE,
                                 type=int)
  public_only = (flask.request.args.get("public_only") or "").lower() == "true"
  image_size = flask.request.args.get(
    "image_size",
    default=_DEFAULT_IMAGE_SIZE,
    type=int,
  )

  now_utc = datetime.datetime.now(datetime.timezone.utc)
  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=states,
    cursor=cursor,
    limit=limit,
    category_id=category_id,
  )

  if public_only:
    joke_entries = [(joke, joke_cursor) for joke, joke_cursor in joke_entries
                    if joke.is_public_and_in_public_state]

  jokes_list = joke_feed_utils.build_feed_entries(
    joke_entries,
    now_utc=now_utc,
    thumb_size=image_size,
  )

  html = flask.render_template(
    "components/joke_feed_fragment.html",
    jokes=jokes_list,
    image_size=image_size,
    admin_stats_enabled=True,
    selectable_cards=True,
  )

  jokes = []
  for entry in jokes_list:
    jokes.append({
      "id":
      entry.joke.key,
      "setup_text":
      entry.joke.setup_text,
      "punchline_text":
      entry.joke.punchline_text,
      "setup_url":
      utils.format_image_url(entry.joke.setup_image_url, width=image_size)
      if entry.joke.setup_image_url else "",
      "punchline_url":
      utils.format_image_url(entry.joke.punchline_image_url, width=image_size)
      if entry.joke.punchline_image_url else "",
      "cursor":
      entry.cursor,
      "is_future_daily":
      entry.is_future_daily,
    })

  resp = flask.make_response(
    flask.jsonify({
      "html": html,
      "jokes": jokes,
      "cursor": next_cursor,
      "has_more": next_cursor is not None,
    }),
    200,
  )
  resp.headers["Content-Type"] = "application/json; charset=utf-8"
  resp.headers["Cache-Control"] = "no-store"
  return resp


@web_bp.route("/admin/api/jokes/categories")
@auth_helpers.require_admin
def admin_joke_picker_categories() -> flask.Response:
  """Return joke categories for the admin joke picker."""
  all_categories = firestore.get_all_joke_categories(use_cache=True)
  categories = [
    category for category in all_categories
    if (category.state or "").strip() in ("APPROVED", "SEASONAL")
  ]

  resp = flask.make_response(
    flask.jsonify({
      "categories": [{
        "id": category.id,
        "display_name": category.display_name,
        "public_joke_count": category.public_joke_count or 0,
      } for category in categories],
    }),
    200,
  )
  resp.headers["Content-Type"] = "application/json; charset=utf-8"
  resp.headers["Cache-Control"] = "no-store"
  return resp
