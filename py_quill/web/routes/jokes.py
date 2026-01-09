"""Jokes feed routes."""

from __future__ import annotations

import datetime

import flask
from services import firestore
from web.routes import web_bp
from web.utils import urls
from web.utils.responses import html_response

_JOKES_PER_PAGE = 10
_JOKE_IMAGE_SIZE = 450


@web_bp.route('/jokes')
def jokes():
  """Render the jokes feed page with first page of jokes."""
  jokes_list, next_cursor = firestore.get_joke_feed_page(cursor=None,
                                                         limit=_JOKES_PER_PAGE)

  canonical_url = urls.canonical_url(flask.url_for('web.jokes'))
  now_year = datetime.datetime.now(datetime.timezone.utc).year

  html = flask.render_template(
    'jokes.html',
    jokes=jokes_list,
    next_cursor=next_cursor,
    has_more=next_cursor is not None,
    image_size=_JOKE_IMAGE_SIZE,
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/jokes/load-more')
def jokes_load_more():
  """API endpoint to load more jokes for infinite scroll. Returns HTML fragments."""
  cursor = flask.request.args.get('cursor', default=None)
  limit = flask.request.args.get('limit', default=_JOKES_PER_PAGE, type=int)

  jokes_list, next_cursor = firestore.get_joke_feed_page(cursor=cursor,
                                                         limit=limit)

  # Render joke cards as HTML fragments
  html_fragments = flask.render_template(
    'components/joke_feed_fragment.html',
    jokes=jokes_list,
    image_size=_JOKE_IMAGE_SIZE,
  )

  response = {
    'html': html_fragments,
    'cursor': next_cursor,
    'has_more': next_cursor is not None,
  }

  resp = flask.make_response(flask.jsonify(response), 200)
  resp.headers['Content-Type'] = 'application/json; charset=utf-8'
  resp.headers['Cache-Control'] = 'public, max-age=300, s-maxage=1200'
  return resp
