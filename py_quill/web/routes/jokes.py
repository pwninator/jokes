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
_COOKIE_NAME = 'jokes_feed_cursor'


@web_bp.route('/')
def index():
  """Render the jokes feed page as the homepage.
  
  If a 'jokes_feed_cursor' cookie is present, resumes from that cursor position.
  Otherwise, starts from the beginning of the feed.
  """
  # Read cursor from cookie if present
  saved_cursor = flask.request.cookies.get(_COOKIE_NAME)

  jokes_list, next_cursor = firestore.get_joke_feed_page(cursor=saved_cursor,
                                                         limit=_JOKES_PER_PAGE)

  canonical_url = urls.canonical_url('/')
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

  return html_response(html, cache_seconds=0, cdn_seconds=0)


@web_bp.route('/jokes')
def jokes():
  """Redirect /jokes to the homepage."""
  return flask.redirect('/', code=301)


@web_bp.route('/jokes/load-more-<slug>')
def jokes_load_more(slug: str):
  """API endpoint to load more jokes for infinite scroll. Returns HTML fragments.
  
  Args:
    slug: Data source identifier (e.g., 'feed'). Determines which function to use
      for fetching jokes.
  
  Returns:
    JSON response with html, cursor, and has_more fields.
    
  Raises:
    404 if slug is not recognized.
  """
  cursor = flask.request.args.get('cursor', default=None)
  limit = flask.request.args.get('limit', default=_JOKES_PER_PAGE, type=int)

  # Switch on slug to determine which data fetching function to use
  jokes_list: list = []
  next_cursor: str | None = None

  if slug == 'feed':
    jokes_list, next_cursor = firestore.get_joke_feed_page(cursor=cursor,
                                                           limit=limit)
  # Future slugs can be added here
  else:
    flask.abort(404, description=f"Unknown feed slug: {slug}")

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
