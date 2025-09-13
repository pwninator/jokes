"""Web cloud functions."""

import datetime
import hashlib
import os
import zoneinfo

import flask
from common import models
from firebase_functions import https_fn, logger, options
from services import firestore, search

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'web',
                              'templates')
_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'static')

app = flask.Flask(__name__,
                  template_folder=_TEMPLATES_DIR,
                  static_folder=_STATIC_DIR)

web_bp = flask.Blueprint('web',
                         __name__,
                         template_folder=_TEMPLATES_DIR,
                         static_folder=_STATIC_DIR)

# Hard-coded topics list for sitemap generation
_WEB_TOPICS: list[str] = [
  'dogs',
  'cats',
  'pandas',
]

# -----------------------------
# Topic pages and SEO blueprint
# -----------------------------


def _html_response(html: str,
                   status: int = 200,
                   cache_seconds: int = 300,
                   cdn_seconds: int = 1800) -> flask.Response:
  """Create an HTML response with caching and ETag headers."""
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  payload = html.encode('utf-8')
  resp.headers['ETag'] = hashlib.md5(payload).hexdigest()  # nosec B303
  resp.headers['Cache-Control'] = (
    f'public, max-age={cache_seconds}, s-maxage={cdn_seconds}, '
    'stale-while-revalidate=86400')
  resp.headers['Last-Modified'] = (datetime.datetime.now(
    datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
  return resp


def _fetch_topic_jokes(topic: str, limit: int) -> list:
  """Fetch jokes for a given topic using vector search constrained by tags."""
  now_la = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
  field_filters = [('public_timestamp', '<=', now_la)]
  logger.info(
    f"Fetching jokes for topic: {topic} with limit: {limit}, field_filters: {field_filters}"
  )
  results = search.search_jokes(
    query=f"jokes about {topic}",
    label="web_topic",
    limit=limit,
    distance_threshold=0.31,
    field_filters=field_filters,
  )
  joke_ids = [r.joke.key for r in results]
  return firestore.get_punny_jokes(joke_ids)


@web_bp.route('/')
def index():
  """Render the landing page with the joke of the day."""
  today = datetime.datetime.now(datetime.timezone.utc).date()
  joke = firestore.get_daily_joke("daily_jokes", today)

  if not joke:
    return "Could not find a joke of the day.", 404

  html = flask.render_template(
    'index.html',
    joke=joke,
    site_name='Snickerdoodle',
  )
  return _html_response(html, cache_seconds=300, cdn_seconds=1800)


@web_bp.route('/jokes/<topic>')
def topic_page(topic: str):
  """Render a topic page listing jokes with revealable punchlines."""
  # Basic, heuristic pagination using page size; true offsets require different queries
  page = flask.request.args.get('page', default='1')
  try:
    page_num = max(1, int(page))
  except Exception:
    page_num = 1

  page_size = 12
  jokes = _fetch_topic_jokes(topic, limit=page_size)

  base_url = flask.request.url_root.rstrip('/')
  canonical_url = f"{base_url}/jokes/{topic}"
  prev_url = None
  next_url = None
  # We only fetch one page; advertise next if we are full (best-effort UX)
  if page_num > 1:
    prev_url = f"{canonical_url}?page={page_num - 1}"
  if len(jokes) == page_size:
    next_url = f"{canonical_url}?page={page_num + 1}"

  html = flask.render_template(
    'topic.html',
    topic=topic,
    jokes=jokes,
    canonical_url=canonical_url,
    prev_url=prev_url,
    next_url=next_url,
    site_name='Snickerdoodle',
  )
  return _html_response(html, cache_seconds=300, cdn_seconds=1800)


@web_bp.route('/sitemap.xml')
def sitemap():
  """Generate a simple sitemap for topics."""
  topics = _WEB_TOPICS

  base_url = flask.request.url_root.rstrip('/')
  urlset_parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ]
  now = datetime.datetime.now(
    datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  for topic in topics:
    urlset_parts.append('<url>')
    urlset_parts.append(f'<loc>{base_url}/jokes/{topic}</loc>')
    urlset_parts.append(f'<lastmod>{now}</lastmod>')
    urlset_parts.append('<changefreq>daily</changefreq>')
    urlset_parts.append('<priority>0.8</priority>')
    urlset_parts.append('</url>')
  urlset_parts.append('</urlset>')
  xml = "".join(urlset_parts)

  resp = flask.make_response(xml, 200)
  resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
  resp.headers['Cache-Control'] = 'public, max-age=600, s-maxage=3600'
  return resp


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  min_instances=1,
  timeout_sec=30,
)
def web_search_page(req: https_fn.Request) -> https_fn.Response:
  """A web page that displays jokes based on a search query."""
  with app.request_context(req.environ):
    return app.full_dispatch_request()


# Register blueprint last so the app is ready before request handling
app.register_blueprint(web_bp)
