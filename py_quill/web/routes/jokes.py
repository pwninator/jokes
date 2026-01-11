"""Jokes feed routes."""

from __future__ import annotations

import datetime
import zoneinfo

import flask
from firebase_functions import logger
from google.cloud.firestore import FieldFilter, Query

from common import models, utils
from services import firestore, search
from web.routes import web_bp
from web.utils import urls
from web.utils.responses import html_response

_JOKES_PER_PAGE = 10
_JOKE_IMAGE_SIZE = 450
_COOKIE_NAME = 'jokes_feed_cursor'


def _fetch_topic_jokes(slug: str, limit: int) -> list[models.PunnyJoke]:
  """Fetch jokes for a given topic using vector search constrained by tags."""
  now_la = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
  field_filters = [('public_timestamp', '<=', now_la)]
  logger.info(
    f"Fetching jokes for topic: {slug} with limit: {limit}, field_filters: {field_filters}"
  )
  results = search.search_jokes(
    query=f"jokes about {slug}",
    label="web_topic",
    limit=limit,
    distance_threshold=0.31,
    field_filters=field_filters,
  )
  # Fetch full jokes by IDs and sort by popularity desc, then vector distance asc
  id_to_distance = {r.joke_id: r.vector_distance for r in results}
  jokes = firestore.get_punny_jokes(list(id_to_distance.keys()))
  jokes.sort(key=lambda j: (
    -1 * (getattr(j, 'num_saved_users_fraction', 0) or 0),
    id_to_distance.get(j.key, float('inf')),
  ))
  return jokes


def load_joke_topic_page(slug: str):
  """Render a topic page listing jokes with revealable punchlines."""
  # Basic, heuristic pagination using page size; true offsets require different queries
  page = flask.request.args.get('page', default='1')
  try:
    page_num = max(1, int(page))
  except Exception:
    page_num = 1

  page_size = 20
  jokes = _fetch_topic_jokes(slug, limit=page_size)

  canonical_path = flask.url_for('web.handle_joke_slug', slug=slug)
  canonical_url = urls.canonical_url(canonical_path)
  prev_url = None
  next_url = None
  # We only fetch one page; advertise next if we are full (best-effort UX)
  if page_num > 1:
    prev_url = urls.canonical_url(canonical_path, f"page={page_num - 1}")
  if len(jokes) == page_size:
    next_url = urls.canonical_url(canonical_path, f"page={page_num + 1}")

  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'topic.html',
    topic=slug,
    jokes=jokes,
    canonical_url=canonical_url,
    prev_url=prev_url,
    next_url=next_url,
    site_name='Snickerdoodle',
    now_year=now_year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1800)


def load_single_joke_page(slug: str):
  """Load and render a single joke page by slug."""
  standardized_slug = utils.get_text_slug(slug)
  if not standardized_slug:
    return "Joke not found.", 404

  # Query for exact match first
  query = firestore.db().collection('jokes').where(
    filter=FieldFilter('is_public', '==', True)).where(
      filter=FieldFilter('setup_text_slug', '==', standardized_slug)).limit(1)

  docs = list(query.stream())
  joke = None

  if docs:
    doc = docs[0]
    if doc.exists and doc.to_dict():
      joke = models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
  else:
    # No exact match, try nearest match
    query_nearest = firestore.db().collection('jokes').where(
      filter=FieldFilter('is_public', '==', True)).where(filter=FieldFilter(
        'setup_text_slug', '>', standardized_slug)).order_by(
          'setup_text_slug', direction=Query.ASCENDING).limit(1)

    docs_nearest = list(query_nearest.stream())
    if docs_nearest:
      doc = docs_nearest[0]
      if doc.exists and doc.to_dict():
        joke = models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)

  if not joke:
    return "Joke not found.", 404

  canonical_path = flask.url_for('web.handle_joke_slug', slug=slug)
  canonical_url = urls.canonical_url(canonical_path)
  now_year = datetime.datetime.now(datetime.timezone.utc).year

  html = flask.render_template(
    'single_joke.html',
    joke=joke,
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1800)


@web_bp.route('/')
def index():
  """Render the jokes feed page as the homepage.
  
  If a 'jokes_feed_cursor' cookie is present, resumes from that cursor position.
  Otherwise, starts from the beginning of the feed.
  """
  # Read cursor from cookie if present
  cookie_cursor = flask.request.cookies.get(_COOKIE_NAME)

  logger.info(f"Serving jokes feed page from cursor: {cookie_cursor}")

  joke_entries, next_cursor = firestore.get_joke_feed_page_entries(
    cursor=cookie_cursor,
    limit=_JOKES_PER_PAGE,
  )
  jokes_list = [{
    'joke': joke,
    'cursor': cursor,
  } for joke, cursor in joke_entries]

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


@web_bp.route('/jokes/<slug>')
def handle_joke_slug(slug: str):
  """Handle joke slug routes - topic pages for short slugs, single joke pages for long slugs."""
  if len(slug) <= 15:
    return load_joke_topic_page(slug)
  return load_single_joke_page(slug)


@web_bp.route('/jokes/feed/load-more-<slug>')
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
    joke_entries, next_cursor = firestore.get_joke_feed_page_entries(
      cursor=cursor,
      limit=limit,
    )
    jokes_list = [{
      'joke': joke,
      'cursor': cursor,
    } for joke, cursor in joke_entries]
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
