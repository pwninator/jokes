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
from services import firestore, search, cloud_storage
from functions import auth_helpers
from google.cloud.firestore import ArrayUnion

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'web',
                              'templates')
_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'static')
app = flask.Flask(__name__,
                  template_folder=_TEMPLATES_DIR,
                  static_folder=_STATIC_DIR)


def _load_css(filename: str) -> str:
  """Load a CSS file from the static directory."""
  css_path = os.path.join(_STATIC_DIR, 'css', filename)
  try:
    with open(css_path, 'r', encoding='utf-8') as css_file:
      return css_file.read()
  except FileNotFoundError:
    logger.error('Stylesheet missing at %s', css_path)
    return ''


_BASE_CSS = _load_css('base.css')
_SITE_CSS = _BASE_CSS + _load_css('style.css')


@app.context_processor
def _inject_template_globals() -> dict[str, str]:
  """Inject shared template variables such as compiled CSS and CF origin."""
  return {
    'site_css': _SITE_CSS,
    'functions_origin': utils.cloud_functions_base_url(),
  }


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
  """Render the landing page with the daily joke and fan favorites."""
  now_la = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
  today_la = now_la.date()

  top_jokes = firestore.get_top_jokes('popularity_score_recent', 10)

  favorites: list[models.PunnyJoke] = []
  seen_keys: set[str] = set()

  for joke in top_jokes:
    joke_key = joke.key or ''
    if joke_key and joke_key in seen_keys:
      continue
    favorites.append(joke)
    if joke_key:
      seen_keys.add(joke_key)
    if len(favorites) == 3:
      break

  daily_joke = None
  try:
    maybe_daily = firestore.get_daily_joke('daily_jokes', today_la)
    if maybe_daily:
      daily_joke = maybe_daily
      if maybe_daily.key:
        favorites = [j for j in favorites if j.key != maybe_daily.key]
        seen_keys.add(maybe_daily.key)
        for joke in top_jokes:
          if joke.key and joke.key in seen_keys:
            continue
          favorites.append(joke)
          if len(favorites) == 3:
            break
          seen_keys.add(joke.key or '')
  except Exception as exc:  # pylint: disable=broad-except
    logger.error('Failed to fetch daily joke for %s: %s', today_la.isoformat(),
                 str(exc))

  # Ensure we never show more than 3 favorites, even if logic above slipped
  favorites = favorites[:3]

  if not daily_joke and not favorites:
    return "Could not find any jokes to display.", 404

  hero_date_label = now_la.strftime('%b %d, %Y')
  html = flask.render_template(
    'index.html',
    daily_joke=daily_joke,
    favorites=favorites,
    hero_date_label=hero_date_label,
    canonical_url=flask.url_for('web.index', _external=True),
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return _html_response(html, cache_seconds=300, cdn_seconds=1200)


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


@web_bp.route('/book')
def book():
  """Render placeholder page for the Snickerdoodle joke book."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'book.html',
    canonical_url=flask.url_for('web.book', _external=True),
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return _html_response(html, cache_seconds=600, cdn_seconds=3600)


@web_bp.route('/about')
def about():
  """Render placeholder page for information about Snickerdoodle."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'about.html',
    canonical_url=flask.url_for('web.about', _external=True),
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return _html_response(html, cache_seconds=600, cdn_seconds=3600)


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


def _format_book_page_download(image_url: str | None) -> str | None:
  """Create a full-quality download link for book page images."""
  if not image_url:
    return None
  try:
    return utils.format_image_url(
      image_url,
      image_format='png',
      quality=100,
      remove_existing=True,
    )
  except ValueError:
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
  book_info = {
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
      'setup_image_download':
      _format_book_page_download(setup_url),
      'punchline_image_download':
      _format_book_page_download(punchline_url),
      'total_cost':
      joke_cost,
      'setup_original_image':
      _format_book_page_image(joke_data.get('setup_image_url')),
      'punchline_original_image':
      _format_book_page_image(joke_data.get('punchline_image_url')),
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
    book=book_info,
    jokes=joke_rows,
    generate_book_page_url=generate_book_page_url,
    update_book_page_url=flask.url_for('web.admin_update_joke_book_page'),
    book_total_cost=total_book_cost if joke_rows else None,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/joke-books/update-page', methods=['POST'])
@auth_helpers.require_admin
def admin_update_joke_book_page():
  """Update book page image selection for a single joke."""
  book_id = flask.request.form.get('joke_book_id')
  joke_id = flask.request.form.get('joke_id')
  new_setup_url = flask.request.form.get('new_book_page_setup_image_url')
  new_punchline_url = flask.request.form.get(
    'new_book_page_punchline_image_url')

  if not book_id or not joke_id:
    return flask.Response('joke_book_id and joke_id are required', 400)

  if not new_setup_url and not new_punchline_url:
    return flask.Response(('Provide new_book_page_setup_image_url or '
                           'new_book_page_punchline_image_url'), 400)

  client = firestore.db()
  book_ref = client.collection('joke_books').document(book_id)
  book_doc = book_ref.get()
  if not getattr(book_doc, 'exists', False):
    return flask.Response('Joke book not found', 404)

  book_data = book_doc.to_dict() or {}
  joke_ids = book_data.get('jokes') or []
  if isinstance(joke_ids, list) and joke_ids and joke_id not in joke_ids:
    return flask.Response('Joke does not belong to this book', 404)

  joke_ref = client.collection('jokes').document(joke_id)
  metadata_ref = joke_ref.collection('metadata').document('metadata')
  metadata_doc = metadata_ref.get()
  existing_metadata = metadata_doc.to_dict() if getattr(
    metadata_doc, 'exists', False) else {}

  current_setup = existing_metadata.get('book_page_setup_image_url')
  current_punchline = existing_metadata.get('book_page_punchline_image_url')

  updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    existing_metadata,
    new_setup_url or current_setup,
    new_punchline_url or current_punchline,
  )

  metadata_ref.set(updates, merge=True)

  return flask.jsonify({
    'book_id':
    book_id,
    'joke_id':
    joke_id,
    'book_page_setup_image_url':
    updates.get('book_page_setup_image_url'),
    'book_page_punchline_image_url':
    updates.get('book_page_punchline_image_url'),
  })


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
    'setup_original_image':
    _format_book_page_image(joke_data.get('setup_image_url')),
    'punchline_original_image':
    _format_book_page_image(joke_data.get('punchline_image_url')),
    'setup_image_download':
    _format_book_page_download(setup_url),
    'punchline_image_download':
    _format_book_page_download(punchline_url),
    'total_cost':
    _extract_total_cost(joke_data),
    'setup_original_preview':
    _format_joke_preview(joke_data.get('setup_image_url')),
    'punchline_original_preview':
    _format_joke_preview(joke_data.get('punchline_image_url')),
    'setup_variants':
    [_format_book_page_thumb(url) for url in setup_variants if url],
    'punchline_variants':
    [_format_book_page_thumb(url) for url in punchline_variants if url],
  }
  return flask.jsonify(resp_data)


@web_bp.route('/admin/joke-books/upload-image', methods=['POST'])
@auth_helpers.require_admin
def admin_joke_book_upload_image():
  """Upload a custom image for a joke setup/punchline or book page."""
  logger.info(f"Admin joke book upload image request: {flask.request.form}")

  joke_id = flask.request.form.get('joke_id')
  book_id = flask.request.form.get('joke_book_id') or 'manual'
  target_field = flask.request.form.get('target_field')
  file = flask.request.files.get('file')
  logger.info(
    f"Joke ID: {joke_id}, Book ID: {book_id}, Target field: {target_field}, File: {file}"
  )

  if not joke_id or not target_field or not file:
    return flask.Response('Missing required fields', 400)

  allowed_fields = {
    'book_page_setup_image_url',
    'book_page_punchline_image_url',
    'setup_image_url',
    'punchline_image_url',
  }

  if target_field not in allowed_fields:
    return flask.Response(f'Invalid target field: {target_field}', 400)

  # Validate file type (basic check)
  if not file.filename:
    return flask.Response('No filename', 400)

  ext = os.path.splitext(file.filename)[1].lower()
  if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
    return flask.Response('Invalid file type', 400)

  # Determine storage path
  timestamp = datetime.datetime.now(
    datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')

  # Use a clean path structure: joke_books/{book_id}/{joke_id}/{type}_{timestamp}.ext
  # or jokes/{joke_id}/{type}_{timestamp}.ext for main images if preferred,
  # but keeping them grouped by "upload source" (joke book admin) might be cleaner
  # or just sticking to a standard "uploads" folder.
  # Let's stick to the user's context: if it's for a book page, put it in joke_books.
  # If it's for the main joke, maybe put it in jokes/custom?
  # The prompt suggested "joke_books/{book_id}/{joke_id}/{type}_{timestamp}.png" for book pages.

  if target_field.startswith('book_page'):
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"joke_books/{book_id}/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"
  else:
    # Main joke images
    type_prefix = 'setup' if 'setup' in target_field else 'punchline'
    gcs_path = f"jokes/{joke_id}/custom_{type_prefix}_{timestamp}{ext}"

  gcs_uri = f"gs://{config.IMAGE_BUCKET_NAME}/{gcs_path}"

  try:
    content = file.read()
    cloud_storage.upload_bytes_to_gcs(
      content, gcs_uri, file.content_type or 'application/octet-stream')
  except Exception as e:
    logger.error('Failed to upload image', exc_info=e)
    return flask.Response('Upload failed', 500)

  # Update Firestore
  public_url = cloud_storage.get_public_image_cdn_url(gcs_uri)
  client = firestore.db()
  joke_ref = client.collection('jokes').document(joke_id)

  if target_field.startswith('book_page'):
    # Update metadata doc
    metadata_ref = joke_ref.collection('metadata').document('metadata')
    # Determine variant field name
    variant_field = f"all_{target_field}s"  # e.g. all_book_page_setup_image_urls

    # Ensure doc exists
    if not metadata_ref.get().exists:
      metadata_ref.set({})

    metadata_ref.update({
      target_field: public_url,
      variant_field: ArrayUnion([public_url])
    })
  else:
    # Update main joke doc
    joke_ref.update({target_field: public_url})

    # Note: Main joke doc doesn't strictly track "all_setup_image_urls" in the same way
    # as metadata, or if it does, it wasn't specified in the prompt requirements
    # to update variants for main images. We'll stick to updating the main field.

  return flask.jsonify({'url': public_url})


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
