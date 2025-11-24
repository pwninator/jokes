"""Web cloud functions."""

import datetime
import hashlib
import os
import zoneinfo

import flask
from common import models
from common import config
from common import utils
from firebase_functions import https_fn, logger, options
from services import firestore, search
from functions import auth_helpers

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'web',
                              'templates')
_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'static')
app = flask.Flask(__name__,
                  template_folder=_TEMPLATES_DIR,
                  static_folder=_STATIC_DIR)

# Canonical public base URL used for sitemaps and absolute links.
_PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL',
                                  'https://snickerdoodlejokes.com').rstrip('/')

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


def _firebase_web_config() -> dict[str, str]:
  """Return Firebase config for the web admin login."""
  return config.FIREBASE_WEB_CONFIG


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


def _fetch_topic_jokes(topic: str, limit: int) -> list[models.PunnyJoke]:
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
  # Fetch full jokes by IDs and sort by popularity desc, then vector distance asc
  id_to_distance = {r.joke_id: r.vector_distance for r in results}
  jokes = firestore.get_punny_jokes(list(id_to_distance.keys()))
  jokes.sort(key=lambda j: (
    -1 * (getattr(j, 'num_saved_users_fraction', 0) or 0),
    id_to_distance.get(j.key, float('inf')),
  ))
  return jokes


@web_bp.route('/')
def index():
  """Render the landing page with the top 10 jokes."""
  jokes = firestore.get_top_jokes('popularity_score_recent', 10)

  if not jokes:
    return "Could not find any top jokes.", 404

  html = flask.render_template(
    'index.html',
    jokes=jokes,
    canonical_url=flask.url_for('web.index', _external=True),
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
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

  page_size = 20
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

  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'topic.html',
    topic=topic,
    jokes=jokes,
    canonical_url=canonical_url,
    prev_url=prev_url,
    next_url=next_url,
    site_name='Snickerdoodle',
    now_year=now_year,
  )
  return _html_response(html, cache_seconds=300, cdn_seconds=1800)


def _redirect_to_admin_dashboard() -> flask.Response:
  """Redirect helper that always points to the admin dashboard."""
  dashboard_path = flask.url_for('web.admin_dashboard')
  dashboard_url = auth_helpers.resolve_admin_redirect(flask.request,
                                                      dashboard_path,
                                                      dashboard_path)
  return flask.redirect(dashboard_url)


@web_bp.route('/admin/login')
def admin_login():
  """Render the admin login page with Google Sign-In."""
  verification = auth_helpers.verify_session(flask.request)
  if verification:
    _, claims = verification
    if claims.get('role') == 'admin':
      target = flask.request.args.get('next')
      if target:
        redirect_url = auth_helpers.resolve_admin_redirect(
          flask.request,
          target,
          flask.url_for('web.admin_dashboard'),
        )
        return flask.redirect(redirect_url)
      return _redirect_to_admin_dashboard()

  next_arg = flask.request.args.get('next')
  resolved_next = auth_helpers.resolve_admin_redirect(
    flask.request,
    next_arg,
    flask.url_for('web.admin_dashboard'),
  )
  firebase_config = _firebase_web_config()
  return flask.render_template(
    'admin/login.html',
    firebase_config=firebase_config,
    next_url=resolved_next,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/session', methods=['POST'])
def admin_session():
  """Exchange an ID token for a session cookie."""
  payload = flask.request.get_json(silent=True) or {}
  id_token = payload.get('idToken')
  if not id_token:
    return flask.jsonify({'error': 'idToken is required'}), 400

  try:
    session_cookie = auth_helpers.create_session_cookie(id_token)
  except Exception as exc:
    logger.error(f'Failed to create session cookie: {exc}')
    return flask.jsonify({'error': 'Unauthorized'}), 401

  response = flask.jsonify({'status': 'ok'})
  cookie_domain = auth_helpers.cookie_domain_for_request(flask.request)
  auth_helpers.set_session_cookie(response,
                                  session_cookie,
                                  domain=cookie_domain)
  logger.info(
    'Issued admin session cookie (host=%s xfh=%s scheme=%s cookie_domain=%s)',
    flask.request.host,
    flask.request.headers.get('X-Forwarded-Host'),
    flask.request.scheme,
    cookie_domain,
  )
  return response


@web_bp.route('/admin/logout', methods=['POST'])
def admin_logout():
  """Clear the admin session cookie."""
  response = flask.jsonify({'status': 'signed_out'})
  cookie_domain = auth_helpers.cookie_domain_for_request(flask.request)
  auth_helpers.clear_session_cookie(response, domain=cookie_domain)
  return response


@web_bp.route('/admin')
@auth_helpers.require_admin
def admin_dashboard():
  """Admin landing page."""
  return flask.render_template(
    'admin/dashboard.html',
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books')
@auth_helpers.require_admin
def admin_joke_books():
  """Render a simple table of all joke book documents."""
  client = firestore.db()
  docs = client.collection('joke_books').stream()
  books: list[dict[str, object]] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict() or {}
    jokes = data.get('jokes') or []
    joke_count = len(jokes) if isinstance(jokes, list) else 0
    books.append({
      'id': doc.id,
      'book_name': data.get('book_name', ''),
      'joke_count': joke_count,
      'zip_url': data.get('zip_url'),
    })

  books.sort(key=lambda book: str(book.get('book_name') or book.get('id')))

  return flask.render_template(
    'admin/joke_books.html',
    books=books,
    site_name='Snickerdoodle',
  )


def _format_book_page_image(image_url: str | None) -> str | None:
  """Normalize book page images to 800px squares for admin previews."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=800,
    )
  except ValueError:
    # If not a CDN URL, return as-is to avoid breaking the page.
    return image_url


def _format_book_page_thumb(image_url: str | None) -> str | None:
  """Create a small thumbnail URL for variant tiles."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=100,
    )
  except ValueError:
    return image_url


def _format_joke_preview(image_url: str | None) -> str | None:
  """Create a small preview of the main joke images for context."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=70,
      width=200,
    )
  except ValueError:
    return image_url


def _extract_total_cost(joke_data: dict[str, object]) -> float | None:
  """Safely extract total generation cost from joke data."""
  generation_metadata = joke_data.get('generation_metadata')
  if not isinstance(generation_metadata, dict):
    return None

  total_cost = generation_metadata.get('total_cost')
  if isinstance(total_cost, (int, float)):
    return float(total_cost)

  try:
    return models.GenerationMetadata.from_dict(generation_metadata).total_cost
  except Exception:
    return None


@web_bp.route('/admin/joke-books/<book_id>')
@auth_helpers.require_admin
def admin_joke_book_detail(book_id: str):
  """Render an image-centric view of a single joke book."""
  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)
  book_doc = book_ref.get()
  if not book_doc.exists:
    return flask.Response('Joke book not found', status=404)

  book_data = book_doc.to_dict() or {}
  jokes = book_data.get('jokes') or []
  book = {
    'id': book_id,
    'book_name': book_data.get('book_name') or book_id,
    'zip_url': book_data.get('zip_url'),
  }

  joke_rows: list[dict[str, object]] = []
  total_book_cost = 0.0
  for sequence, joke_id in enumerate(jokes, start=1):
    joke_ref = client.collection('jokes').document(joke_id)
    joke_doc = joke_ref.get()
    joke_data = joke_doc.to_dict() or {} if getattr(joke_doc, 'exists',
                                                    False) else {}
    metadata_ref = joke_ref.collection('metadata').document('metadata')
    metadata_doc = metadata_ref.get()
    setup_url = None
    punchline_url = None
    setup_variants: list[str] = []
    punchline_variants: list[str] = []
    if getattr(metadata_doc, 'exists', False):
      metadata = metadata_doc.to_dict() or {}
      setup_url = metadata.get('book_page_setup_image_url')
      punchline_url = metadata.get('book_page_punchline_image_url')
      setup_variants = metadata.get('all_book_page_setup_image_urls') or []
      punchline_variants = metadata.get(
        'all_book_page_punchline_image_urls') or []

    joke_cost = _extract_total_cost(joke_data)
    if isinstance(joke_cost, (int, float)):
      total_book_cost += float(joke_cost)

    joke_rows.append({
      'sequence':
      sequence,
      'id':
      joke_id,
      'setup_image':
      _format_book_page_image(setup_url),
      'punchline_image':
      _format_book_page_image(punchline_url),
      'total_cost':
      joke_cost,
      'setup_preview':
      _format_joke_preview(joke_data.get('setup_image_url')),
      'punchline_preview':
      _format_joke_preview(joke_data.get('punchline_image_url')),
      'setup_variants':
      [_format_book_page_thumb(url) for url in setup_variants if url],
      'punchline_variants':
      [_format_book_page_thumb(url) for url in punchline_variants if url],
    })

  if utils.is_emulator():
    generate_book_page_url = "http://127.0.0.1:5001/storyteller-450807/us-central1/generate_joke_book_page"
  else:
    generate_book_page_url = "https://generate-joke-book-page-uqdkqas7gq-uc.a.run.app"

  return flask.render_template(
    'admin/joke_book_detail.html',
    book=book,
    jokes=joke_rows,
    generate_book_page_url=generate_book_page_url,
    update_book_page_url=(
      "http://127.0.0.1:5001/storyteller-450807/us-central1/update_joke_book"
      if utils.is_emulator() else
      "https://update-joke-book-uqdkqas7gq-uc.a.run.app"),
    book_total_cost=total_book_cost if joke_rows else None,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books/<book_id>/jokes/<joke_id>/refresh')
@auth_helpers.require_admin
def admin_joke_book_refresh(book_id: str, joke_id: str):
  """Return latest images and cost for a single joke in a book."""
  logger.info('Refreshing joke %s for book %s', joke_id, book_id)
  client = firestore.db()
  joke_ref = client.collection('jokes').document(joke_id)
  joke_doc = joke_ref.get()
  if not getattr(joke_doc, 'exists', False):
    return flask.jsonify({'error': 'Joke not found'}), 404

  joke_data = joke_doc.to_dict() or {}
  metadata_ref = joke_ref.collection('metadata').document('metadata')
  metadata_doc = metadata_ref.get()
  setup_url = None
  punchline_url = None
  setup_variants: list[str] = []
  punchline_variants: list[str] = []
  if getattr(metadata_doc, 'exists', False):
    metadata = metadata_doc.to_dict() or {}
    setup_url = metadata.get('book_page_setup_image_url')
    punchline_url = metadata.get('book_page_punchline_image_url')
    setup_variants = metadata.get('all_book_page_setup_image_urls') or []
    punchline_variants = metadata.get(
      'all_book_page_punchline_image_urls') or []

  resp_data = {
    'id':
    joke_id,
    'setup_image':
    _format_book_page_image(setup_url),
    'punchline_image':
    _format_book_page_image(punchline_url),
    'total_cost':
    _extract_total_cost(joke_data),
    'setup_variants':
    [_format_book_page_thumb(url) for url in setup_variants if url],
    'punchline_variants':
    [_format_book_page_thumb(url) for url in punchline_variants if url],
  }
  return flask.jsonify(resp_data)


@web_bp.route('/sitemap.xml')
def sitemap():
  """Generate a simple sitemap for topics."""
  topics = _WEB_TOPICS

  base_url = _PUBLIC_BASE_URL
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
