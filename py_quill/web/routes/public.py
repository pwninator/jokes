"""Public SEO routes (index, topics, sitemap)."""

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

# Hard-coded topics list for sitemap generation
_WEB_TOPICS: list[str] = [
  'dogs',
  'cats',
  'pandas',
]


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


@web_bp.route('/home2')
def home2():
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
    canonical_url=urls.canonical_url(flask.url_for('web.home2')),
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


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


@web_bp.route('/jokes/<slug>')
def handle_joke_slug(slug: str):
  """Handle joke slug routes - topic pages for short slugs, single joke pages for long slugs."""
  if len(slug) <= 15:
    return load_joke_topic_page(slug)
  return load_single_joke_page(slug)


@web_bp.route('/sitemap.xml')
def sitemap():
  """Generate a simple sitemap for topics."""
  topics = _WEB_TOPICS
  notes_slugs: set[str] = set()
  try:
    notes_cache = firestore.get_joke_sheets_cache()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke sheets cache for sitemap: {exc}",
      extra={"json_fields": {
        "event": "sitemap_notes_cache_fetch_failed"
      }},
    )
    notes_cache = []
  for _, sheets in notes_cache:
    for sheet in sheets:
      slug = sheet.slug
      if slug:
        notes_slugs.add(slug)

  base_url = urls.public_base_url()
  urlset_parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ]
  now = datetime.datetime.now(
    datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  # Include key non-topic landing pages.
  urlset_parts.append('<url>')
  urlset_parts.append(f'<loc>{base_url}/printables/notes</loc>')
  urlset_parts.append(f'<lastmod>{now}</lastmod>')
  urlset_parts.append('<changefreq>weekly</changefreq>')
  urlset_parts.append('<priority>0.8</priority>')
  urlset_parts.append('</url>')
  for slug in sorted(notes_slugs):
    urlset_parts.append('<url>')
    urlset_parts.append(f'<loc>{base_url}/printables/notes/{slug}</loc>')
    urlset_parts.append(f'<lastmod>{now}</lastmod>')
    urlset_parts.append('<changefreq>weekly</changefreq>')
    urlset_parts.append('<priority>0.8</priority>')
    urlset_parts.append('</url>')
  for topic in topics:
    urlset_parts.append('<url>')
    urlset_parts.append(f'<loc>{base_url}/jokes/{topic}</loc>')
    urlset_parts.append(f'<lastmod>{now}</lastmod>')
    urlset_parts.append('<changefreq>daily</changefreq>')
    urlset_parts.append('<priority>0.3</priority>')
    urlset_parts.append('</url>')
  urlset_parts.append('</urlset>')
  xml = "".join(urlset_parts)

  resp = flask.make_response(xml, 200)
  resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
  resp.headers['Cache-Control'] = 'public, max-age=600, s-maxage=3600'
  return resp
