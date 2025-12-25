"""Web cloud functions."""

import datetime
import hashlib
import os
import re
import uuid
import zoneinfo
from concurrent.futures import ThreadPoolExecutor

import flask
import requests
from common import amazon_redirect, config, joke_lead_operations, models, utils
from firebase_functions import https_fn, logger, options
from functions import auth_helpers
from google.cloud.firestore import ArrayUnion
from services import cloud_storage, firestore, search

_GA4_MEASUREMENT_ID = "G-D2B7E8PXJJ"
_GA4_TIMEOUT_SECONDS = 1.0
_GA4_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_GA_COOKIE_CLIENT_ID_RE = re.compile(r"^\d+\.\d+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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
    logger.error(f'Stylesheet missing at {css_path}')
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


def _html_no_store_response(html: str, status: int = 200) -> flask.Response:
  """Create an HTML response that should never be cached."""
  resp = flask.make_response(html, status)
  resp.headers['Content-Type'] = 'text/html; charset=utf-8'
  resp.headers['Cache-Control'] = 'no-store'
  return resp


def _resolve_request_country_code(req: flask.Request) -> str:
  """Determine the ISO country code for the current request."""
  override = amazon_redirect.normalize_country_code(
    req.args.get('country_override'))
  if override:
    return override

  header_code = amazon_redirect.normalize_country_code(
    req.headers.get('X-Appengine-Country'))
  if header_code:
    return header_code

  return amazon_redirect.DEFAULT_COUNTRY_CODE


def _log_amazon_redirect(redirect_key: str,
                         requested_country: str,
                         resolved_country: str,
                         target_url: str,
                         source: str | None = None) -> None:
  """Log redirect metadata for analytics/debugging."""
  user_agent = flask.request.headers.get('User-Agent', '')[:500]
  logger.info(
    f'amazon_redirect {redirect_key}/{source} -> {target_url} ({requested_country} -> {resolved_country})',
    extra={
      "json_fields": {
        "event": "amazon_redirect",
        "redirect_key": redirect_key,
        "source": source,
        "requested_country_code": requested_country,
        "resolved_country_code": resolved_country,
        "target_url": target_url,
        "user_agent": user_agent,
      }
    },
  )


def _render_ga4_redirect_page(
  *,
  target_url: str,
  canonical_url: str,
  page_title: str,
  heading: str,
  message: str | None,
  link_text: str,
  ga4_event_base_name: str,
  ga4_event_params: dict,
  meta_pixel_event_name: str | None = None,
  site_name: str = 'Snickerdoodle',
) -> flask.Response:
  """Render a no-store redirect page and log GA4 events server + client side.

  Server-side uses GA4 Measurement Protocol (best-effort, async).
  Client-side uses `redirect.html` to emit a `gtag('event', ...)` before
  `location.replace(...)` (best-effort).
  
  Optionally tracks Meta Pixel event if `meta_pixel_event_name` is provided.
  Both trackers run in parallel with coordinated completion before redirect.
  """
  base_name = (ga4_event_base_name or '').strip()
  client_event_name = f'{base_name}_client'
  click_event_name = f'{base_name}_click'
  server_event_name = f'{base_name}_server'
  event_params = ga4_event_params or {}

  client_id = _ga4_client_id_for_request(flask.request)
  _submit_ga4_event_fire_and_forget(
    measurement_id=_GA4_MEASUREMENT_ID,
    api_secret=config.get_google_analytics_api_key(),
    client_id=client_id,
    event_name=server_event_name,
    event_params={
      **event_params,
      'page_location': flask.request.url,
    },
    user_agent=flask.request.headers.get('User-Agent'),
    user_ip=flask.request.headers.get('X-Forwarded-For')
    or flask.request.remote_addr,
  )

  html = flask.render_template(
    'redirect.html',
    page_title=page_title,
    heading=heading,
    message=message,
    target_url=target_url,
    link_text=link_text,
    event_name=client_event_name,
    event_params=event_params,
    click_event_name=click_event_name,
    meta_pixel_event_name=meta_pixel_event_name,
    canonical_url=canonical_url,
    prev_url=None,
    next_url=None,
    site_name=site_name,
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return _html_no_store_response(html, status=200)


def _handle_amazon_redirect(redirect_key: str) -> flask.Response:
  """Shared handler for public Amazon redirect endpoints."""
  config_entry = amazon_redirect.AMAZON_REDIRECTS.get(redirect_key)
  if not config_entry:
    return flask.Response('Redirect not found', status=404)

  requested_country = _resolve_request_country_code(flask.request)
  source = flask.request.args.get('source')
  if not source:
    source = "aa"
  target_url, resolved_country, resolved_asin = config_entry.resolve_target_url(
    requested_country, source)
  _log_amazon_redirect(
    redirect_key,
    requested_country,
    resolved_country,
    target_url,
    source,
  )

  event_params = {
    'redirect_key': redirect_key,
    'requested_country_code': requested_country,
    'resolved_country_code': resolved_country,
    'resolved_asin': resolved_asin,
    'page_type': config_entry.page_type.value,
    'source': source,
  }
  return _render_ga4_redirect_page(
    target_url=target_url,
    canonical_url=flask.request.url,
    page_title=config_entry.label,
    heading='Redirecting to Amazon…',
    message='Taking you to Amazon now.',
    link_text='Continue to Amazon',
    ga4_event_base_name='amazon_redirect',
    ga4_event_params=event_params,
  )


def _ga4_client_id_for_request(req: flask.Request) -> str:
  """Return client_id for GA4 Measurement Protocol.

  Prefers the existing GA cookie `_ga` (stable across web analytics), otherwise
  falls back to a random per-request ID (no cookie set by redirects).
  """
  ga_cookie = req.cookies.get('_ga')
  if ga_cookie:
    # Typical format: GA1.1.1234567890.1234567890
    parts = ga_cookie.split('.')
    if len(parts) >= 2:
      candidate = f"{parts[-2]}.{parts[-1]}"
      if _GA_COOKIE_CLIENT_ID_RE.match(candidate):
        return candidate

  return str(uuid.uuid4())


def _submit_ga4_event_fire_and_forget(
  *,
  measurement_id: str,
  api_secret: str,
  client_id: str,
  event_name: str,
  event_params: dict,
  user_agent: str | None,
  user_ip: str | None,
) -> None:
  """Send a GA4 Measurement Protocol event without blocking the request."""

  def _send() -> None:
    try:
      url = "https://www.google-analytics.com/mp/collect"
      params = {
        "measurement_id": measurement_id,
        "api_secret": api_secret,
      }
      payload = {
        "client_id":
        client_id,
        "events": [{
          "name": event_name,
          "params": {
            **(event_params or {}),
            # Minimal engagement time so GA accepts it as an event.
            "engagement_time_msec":
            1,
          },
        }],
      }
      headers = {"Content-Type": "application/json"}
      if user_agent:
        headers["User-Agent"] = user_agent
      if user_ip:
        headers["X-Forwarded-For"] = user_ip
      logger.info(
        f"Sending GA4 MP event '{event_name}' with params: {params}, payload: {payload}, headers: {headers}"
      )
      requests.post(url,
                    params=params,
                    json=payload,
                    headers=headers,
                    timeout=_GA4_TIMEOUT_SECONDS)
    except Exception as exc:  # pylint: disable=broad-except
      logger.warn(f"Failed to send GA4 MP event '{event_name}': {exc}")

  future = _GA4_EXECUTOR.submit(_send)

  def _log_unexpected_error(fut) -> None:  # pragma: no cover
    try:
      fut.result()
    except Exception as exc:  # pylint: disable=broad-except
      logger.warn(f"Unexpected GA4 MP failure: {exc}")

  future.add_done_callback(_log_unexpected_error)


def _redirect_endpoint_for_key(
    redirect_key: str) -> tuple[str | None, str | None]:
  """Return endpoint name and slug for a redirect key."""
  if redirect_key.startswith('review-'):
    slug = redirect_key.removeprefix('review-')
    return 'web.amazon_review_redirect', slug
  if redirect_key.startswith('book-'):
    slug = redirect_key.removeprefix('book-')
    return 'web.amazon_book_redirect', slug
  return None, None


def _amazon_redirect_view_models() -> list[dict[str, str]]:
  """Return metadata for all configured Amazon redirects."""
  items: list[dict[str, str]] = []
  for key, config_entry in amazon_redirect.AMAZON_REDIRECTS.items():
    endpoint, slug = _redirect_endpoint_for_key(key)
    if not endpoint or slug is None:
      continue
    path = flask.url_for(endpoint, slug=slug)
    supported_countries = sorted(list(config_entry.supported_countries))
    items.append({
      'key': key,
      'label': config_entry.label,
      'description': config_entry.description,
      'asin': config_entry.asin,
      'page_type': config_entry.page_type.value,
      'url': path,
      'supported_countries': supported_countries,
    })
  items.sort(key=lambda item: item['label'])
  return items


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


@web_bp.route('/review-<path:slug>')
def amazon_review_redirect(slug: str):
  """Redirect to an Amazon review page for supported slugs."""
  return _handle_amazon_redirect(f'review-{slug}')


@web_bp.route('/book-<path:slug>')
def amazon_book_redirect(slug: str):
  """Redirect to an Amazon product page for supported slugs."""
  return _handle_amazon_redirect(f'book-{slug}')


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
    logger.error(
      f'Failed to fetch daily joke for {today_la.isoformat()}: {str(exc)}')

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


@web_bp.route('/lunchbox', methods=['GET', 'POST'])
def lunchbox():
  """Render / handle the lunchbox lead capture page."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = flask.url_for('web.lunchbox', _external=True)

  error_message = None
  email_value = ''
  status_override: int | None = None

  if flask.request.method == 'POST':
    email_value = (flask.request.form.get('email') or '').strip().lower()

    if not email_value or not _EMAIL_RE.match(email_value):
      error_message = 'Please enter a valid email address.'
      status_override = 400
    else:
      try:
        country_code = _resolve_request_country_code(flask.request)
        joke_lead_operations.create_lead(
          email=email_value,
          country_code=country_code,
          signup_source='lunchbox',
          group_id=joke_lead_operations.GROUP_SNICKERDOODLE_CLUB,
        )
        return flask.redirect(flask.url_for('web.lunchbox_thank_you'))
      except Exception as exc:  # pylint: disable=broad-except
        logger.error(
          f'Failed to create lunchbox lead: {exc}',
          extra={
            'json_fields': {
              'event': 'lunchbox_lead_failed',
              'email': email_value,
            }
          },
        )
        error_message = 'Unable to process your request. Please try again.'
        status_override = 500

  html = flask.render_template(
    'lunchbox.html',
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    error_message=error_message,
    email_value=email_value,
  )
  if error_message:
    return _html_no_store_response(html, status=status_override or 400)
  return _html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/lunchbox-thank-you')
def lunchbox_thank_you():
  """Thank you page after lead submission."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'lunchbox_thank_you.html',
    canonical_url=flask.url_for('web.lunchbox_thank_you', _external=True),
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return _html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/lunchbox-download-pdf')
def lunchbox_download_pdf():
  """Redirect helper that sends users to the lunchbox PDF download."""
  download_url = "/lunchbox/lunchbox_notes_animal_jokes.pdf"
  event_params = {
    'asset': 'lunchbox_notes_animal_jokes.pdf',
  }
  return _render_ga4_redirect_page(
    target_url=download_url,
    canonical_url=flask.url_for('web.lunchbox_download_pdf', _external=True),
    page_title='Lunchbox Notes Download',
    heading='Starting your download…',
    message="If it doesn't start automatically, use the button below.",
    link_text='Download the PDF',
    ga4_event_base_name='web_lunchbox_download',
    ga4_event_params=event_params,
    meta_pixel_event_name='CompleteRegistration',
  )


def _redirect_to_admin_dashboard() -> flask.Response:
  """Redirect helper that always points to the admin dashboard."""
  dashboard_path = flask.url_for('web.admin_dashboard')
  dashboard_url = auth_helpers.resolve_admin_redirect(flask.request,
                                                      dashboard_path,
                                                      dashboard_path)
  return flask.redirect(dashboard_url)


def _bucket_jokes_viewed(count: int) -> str:
  """Bucket joke view counts into ranges for charting."""
  safe_count = max(0, count)
  if safe_count == 0:
    return "0"
  if safe_count < 10:
    return "1-9"
  if safe_count < 100:
    lower = (safe_count // 10) * 10
    upper = lower + 9
    return f"{lower}-{upper}"
  lower = max(100, (safe_count // 50) * 50)
  upper = lower + 49
  return f"{lower}-{upper}"


def _rebucket_counts(counts: object) -> dict[str, int]:
  """Aggregate arbitrary bucket keys into the defined joke-count buckets."""
  if not isinstance(counts, dict):
    return {}

  aggregated: dict[str, int] = {}
  for raw_bucket, raw_count in counts.items():
    try:
      count_val = int(raw_count)
    except Exception:
      continue

    if isinstance(raw_bucket, str) and "-" in raw_bucket:
      bucket_label = raw_bucket
    else:
      try:
        numeric_bucket = int(raw_bucket)
      except Exception:
        continue
      bucket_label = _bucket_jokes_viewed(numeric_bucket)

    aggregated[bucket_label] = aggregated.get(bucket_label, 0) + count_val

  return aggregated


def _rebucket_matrix(matrix: object) -> dict[str, dict[str, int]]:
  """Aggregate a nested day->bucket map into the defined bucket ranges."""
  if not isinstance(matrix, dict):
    return {}

  rebucketed: dict[str, dict[str, int]] = {}
  for day, day_data in matrix.items():
    rebucketed[day] = _rebucket_counts(day_data)
  return rebucketed


def _bucket_label_sort_key(label: str) -> int:
  """Sort bucket labels by their numeric lower bound."""
  if isinstance(label, str) and "-" in label:
    lower = label.split("-", 1)[0]
    try:
      return int(lower)
    except Exception:
      return 0
  try:
    return int(label)
  except Exception:
    return 0


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
  hex_color = hex_color.lstrip('#')
  return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
  r, g, b = rgb
  return f'#{r:02x}{g:02x}{b:02x}'


_ANCHOR_COLORS = [
  '#7e57c2',  # Purple (start)
  '#3f51b5',  # Indigo
  '#2196f3',  # Blue
  '#26a69a',  # Teal
  '#66bb6a',  # Green
  '#ffeb3b',  # Yellow
  '#ff9800',  # Orange
  '#f44336',  # Red (end)
]
_ZERO_BUCKET_COLOR = '#9e9e9e'


def _color_at_position(position: float) -> str:
  """Return a color along the rainbow gradient (purple -> red)."""
  position = max(0.0, min(1.0, position))
  segment_count = len(_ANCHOR_COLORS) - 1
  if segment_count <= 0:
    return _ANCHOR_COLORS[0]

  scaled = position * segment_count
  idx = int(scaled)
  if idx >= segment_count:
    return _ANCHOR_COLORS[-1]

  local_t = scaled - idx
  start_rgb = _hex_to_rgb(_ANCHOR_COLORS[idx])
  end_rgb = _hex_to_rgb(_ANCHOR_COLORS[idx + 1])
  interp = tuple(
    round(start_rgb[c] + (end_rgb[c] - start_rgb[c]) * local_t)
    for c in range(3))
  return _rgb_to_hex(interp)


def _build_bucket_color_map(bucket_labels: list[str]) -> dict[str, str]:
  """Assign colors to buckets using a rainbow gradient."""
  color_map: dict[str, str] = {}
  non_zero_labels = [b for b in bucket_labels if b != "0"]
  total = len(non_zero_labels)

  for idx, bucket in enumerate(non_zero_labels):
    position = 0.0 if total <= 1 else idx / (total - 1)
    color_map[bucket] = _color_at_position(position)

  if "0" in bucket_labels:
    color_map["0"] = _ZERO_BUCKET_COLOR

  return color_map


def _bucket_days_used_label(day_value: str | int) -> str | None:
  """Bucket days-used into singles for <=7, weekly ranges for >=8."""
  try:
    day_int = int(day_value)
  except Exception:
    return None

  if day_int <= 0:
    return None
  if day_int <= 7:
    return str(day_int)
  start = ((day_int - 1) // 7) * 7 + 1
  end = start + 6
  return f"{start}-{end}"


def _rebucket_days_used(
    matrix: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
  """Aggregate retention matrix by day-used buckets (1..7 individual, then weekly)."""
  rebucketed: dict[str, dict[str, int]] = {}
  for day_label, buckets in (matrix or {}).items():
    target_label = _bucket_days_used_label(day_label)
    if not target_label:
      continue
    if target_label not in rebucketed:
      rebucketed[target_label] = {}
    for bucket_label, count in (buckets or {}).items():
      rebucketed[target_label][bucket_label] = (
        rebucketed[target_label].get(bucket_label, 0) + int(count or 0))
  return rebucketed


def _day_bucket_sort_key(label: str) -> int:
  """Sort day buckets by their numeric lower bound."""
  if isinstance(label, str) and "-" in label:
    lower = label.split("-", 1)[0]
    try:
      return int(lower)
    except Exception:
      return 0
  try:
    return int(label)
  except Exception:
    return 0


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


@web_bp.route('/admin/redirect-tester')
@auth_helpers.require_admin
def admin_redirect_tester():
  """Render the Amazon redirect testing interface."""
  redirect_items = _amazon_redirect_view_models()
  country_options = sorted(
    amazon_redirect.COUNTRY_TO_DOMAIN.items(),
    key=lambda item: item[0],
  )
  return flask.render_template(
    'admin/redirect_tester.html',
    redirect_items=redirect_items,
    country_options=country_options,
    site_name='Snickerdoodle',
  )


@web_bp.route('/admin/stats')
@auth_helpers.require_admin
def admin_stats():
  """Render the stats dashboard."""
  client = firestore.db()
  # Fetch last 30 days of stats
  docs = client.collection('joke_stats').order_by(
    '__name__', direction=firestore.Query.DESCENDING).limit(30).stream()

  stats_list = []
  for doc in docs:
    data = doc.to_dict()
    data['id'] = doc.id
    stats_list.append(data)

  # Sort chronological for DAU chart
  stats_list.reverse()

  # Normalize buckets for charts
  for stats in stats_list:
    stats['num_1d_users_by_jokes_viewed'] = _rebucket_counts(
      stats.get('num_1d_users_by_jokes_viewed'))
    stats['num_7d_users_by_jokes_viewed'] = _rebucket_counts(
      stats.get('num_7d_users_by_jokes_viewed'))
    stats['num_7d_users_by_days_used_by_jokes_viewed'] = _rebucket_matrix(
      stats.get('num_7d_users_by_days_used_by_jokes_viewed'))

  # Collect all buckets from both DAU and retention to keep colors consistent
  all_buckets: set[str] = set()
  for s in stats_list:
    all_buckets.update(s.get('num_1d_users_by_jokes_viewed', {}).keys())
    all_buckets.update(s.get('num_7d_users_by_jokes_viewed', {}).keys())
    for day_data in s.get('num_7d_users_by_days_used_by_jokes_viewed',
                          {}).values():
      all_buckets.update(day_data.keys())

  sorted_buckets = sorted(list(all_buckets), key=_bucket_label_sort_key)
  color_map = _build_bucket_color_map(sorted_buckets)

  # --- Prepare DAU Data ---
  dau_labels = [s['id'] for s in stats_list]

  dau_datasets = []
  for idx, bucket in enumerate(sorted_buckets):
    data_points = []
    for s in stats_list:
      val = s.get('num_1d_users_by_jokes_viewed', {}).get(bucket, 0)
      data_points.append(val)

    dau_datasets.append({
      'label': f'{bucket} jokes',
      'data': data_points,
      'backgroundColor': color_map.get(bucket, '#607d8b'),
      'stack': 'Stack 0',
      # Draw highest buckets first so they appear at the bottom of the stack.
      'order': -idx,
    })

  # --- Prepare Retention Data (from most recent stats doc only) ---
  latest_stats = stats_list[-1] if stats_list else {}
  retention_matrix_raw = latest_stats.get(
    'num_7d_users_by_days_used_by_jokes_viewed', {})
  retention_matrix = _rebucket_days_used(retention_matrix_raw)

  # Sort days used (labels) numerically
  retention_labels = sorted(retention_matrix.keys(), key=_day_bucket_sort_key)

  # Identify all unique joke buckets in the matrix
  retention_buckets = set()
  for day_data in retention_matrix.values():
    retention_buckets.update(day_data.keys())
  sorted_ret_buckets = sorted(list(retention_buckets),
                              key=_bucket_label_sort_key)

  retention_datasets = []
  for bucket in sorted_ret_buckets:
    data_points = []
    for day in retention_labels:
      day_data = retention_matrix.get(day, {})
      count = day_data.get(bucket, 0)
      total = sum(day_data.values())
      percentage = (count / total * 100) if total > 0 else 0
      data_points.append(percentage)

    retention_datasets.append({
      'label':
      f'{bucket} jokes',
      'data':
      data_points,
      'backgroundColor':
      color_map.get(bucket, '#607d8b'),
    })

  return flask.render_template(
    'admin/stats.html',
    site_name='Snickerdoodle',
    dau_data={
      'labels': dau_labels,
      'datasets': dau_datasets
    },
    retention_data={
      'labels': retention_labels,
      'datasets': retention_datasets
    },
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

    num_views = int(joke_data.get('num_viewed_users') or 0)
    num_saves = int(joke_data.get('num_saved_users') or 0)
    num_shares = int(joke_data.get('num_shared_users') or 0)
    popularity_score = float(joke_data.get('popularity_score') or 0.0)
    num_saved_users_fraction = float(
      joke_data.get('num_saved_users_fraction') or 0.0)

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
      'num_views':
      num_views,
      'num_saves':
      num_saves,
      'num_shares':
      num_shares,
      'popularity_score':
      popularity_score,
      'num_saved_users_fraction':
      num_saved_users_fraction,
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
    set_main_image_url=flask.url_for(
      'web.admin_set_main_joke_image_from_book_page'),
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


@web_bp.route('/admin/joke-books/set-main-image', methods=['POST'])
@auth_helpers.require_admin
def admin_set_main_joke_image_from_book_page():
  """Promote the selected book page image to the main joke image."""
  book_id = flask.request.form.get('joke_book_id')
  joke_id = flask.request.form.get('joke_id')
  target = flask.request.form.get('target')

  if not book_id or not joke_id:
    return flask.Response('joke_book_id and joke_id are required', 400)

  if target not in {'setup', 'punchline'}:
    return flask.Response('target must be setup or punchline', 400)

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
  metadata = metadata_doc.to_dict() if getattr(metadata_doc, 'exists',
                                               False) else {}

  page_field = ('book_page_setup_image_url'
                if target == 'setup' else 'book_page_punchline_image_url')
  page_url = metadata.get(page_field)
  if not page_url:
    return flask.Response('Book page image not found', 400)

  main_field = 'setup_image_url' if target == 'setup' else 'punchline_image_url'
  history_field = ('all_setup_image_urls'
                   if target == 'setup' else 'all_punchline_image_urls')
  upscaled_field = ('setup_image_url_upscaled'
                    if target == 'setup' else 'punchline_image_url_upscaled')

  joke_ref.update({
    main_field: page_url,
    history_field: ArrayUnion([page_url]),
    upscaled_field: None,
  })

  return flask.jsonify({
    'book_id': book_id,
    'joke_id': joke_id,
    main_field: page_url,
  })


@web_bp.route('/admin/joke-books/<book_id>/jokes/<joke_id>/refresh')
@auth_helpers.require_admin
def admin_joke_book_refresh(book_id: str, joke_id: str):
  """Return latest images and cost for a single joke in a book."""
  logger.info(f'Refreshing joke {joke_id} for book {book_id}')
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
    'num_views':
    int(joke_data.get('num_viewed_users') or 0),
    'num_saves':
    int(joke_data.get('num_saved_users') or 0),
    'num_shares':
    int(joke_data.get('num_shared_users') or 0),
    'popularity_score':
    float(joke_data.get('popularity_score') or 0.0),
    'num_saved_users_fraction':
    float(joke_data.get('num_saved_users_fraction') or 0.0),
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
