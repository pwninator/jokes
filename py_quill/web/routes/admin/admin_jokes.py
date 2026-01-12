"""Admin jokes list routes."""

from __future__ import annotations

import datetime

import flask

from common import models
from functions import auth_helpers
from services import firestore
from web.routes import web_bp

_JOKES_PER_PAGE = 10
_JOKE_IMAGE_SIZE = 400

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


def _is_future_daily(joke: models.PunnyJoke, *,
                     now_utc: datetime.datetime) -> bool:
  if joke.state != models.JokeState.DAILY:
    return False
  public_ts = getattr(joke, "public_timestamp", None)
  if public_ts is None:
    return False
  if not isinstance(public_ts, datetime.datetime):
    return False
  if public_ts.tzinfo is None:
    # Treat naive timestamps as UTC.
    public_ts = public_ts.replace(tzinfo=datetime.timezone.utc)
  return public_ts > now_utc


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
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=selected_states,
    cursor=query_cursor,
    limit=_JOKES_PER_PAGE,
  )
  for joke, _ in joke_entries:
    # Attach a template-friendly flag for future-daily styling.
    joke.is_future_daily = _is_future_daily(
      joke, now_utc=now_utc)  # type: ignore[attr-defined]
  jokes_list = [{
    'joke': joke,
    'cursor': cursor,
  } for joke, cursor in joke_entries]

  selected_states_param = ",".join([s.value for s in selected_states])

  return flask.render_template(
    'admin/admin_jokes.html',
    site_name='Snickerdoodle',
    joke_creation_url='/joke_creation_process',
    all_states=[s.value for s in _ALL_STATES],
    selected_states=[s.value for s in selected_states],
    selected_states_param=selected_states_param,
    jokes=jokes_list,
    next_cursor=next_cursor,
    has_more=next_cursor is not None,
    image_size=_JOKE_IMAGE_SIZE,
  )


@web_bp.route('/jokes/feed/load-more-admin-jokes')
@auth_helpers.require_admin
def admin_jokes_load_more():
  """API endpoint to load more admin jokes for infinite scroll."""
  cursor = flask.request.args.get('cursor', default=None)
  limit = flask.request.args.get('limit', default=_JOKES_PER_PAGE, type=int)
  selected_states = _parse_state_filters(flask.request.args.get('states'))
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  joke_entries, next_cursor = firestore.get_joke_by_state(
    states=selected_states,
    cursor=cursor,
    limit=limit,
  )
  for joke, _ in joke_entries:
    joke.is_future_daily = _is_future_daily(
      joke, now_utc=now_utc)  # type: ignore[attr-defined]
  jokes_list = [{
    'joke': joke,
    'cursor': cursor,
  } for joke, cursor in joke_entries]

  html_fragments = flask.render_template(
    'components/joke_feed_fragment.html',
    jokes=jokes_list,
    image_size=_JOKE_IMAGE_SIZE,
    admin_mode=True,
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
