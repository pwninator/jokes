"""Public SEO routes (index, topics, about, sitemap)."""

from __future__ import annotations

import datetime
import zoneinfo

import flask
from firebase_functions import logger

from common import models
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
    canonical_url=urls.canonical_url(flask.url_for('web.index')),
    site_name='Snickerdoodle',
    now_year=datetime.datetime.now(datetime.timezone.utc).year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


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

  canonical_path = flask.url_for('web.topic_page', topic=topic)
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
    topic=topic,
    jokes=jokes,
    canonical_url=canonical_url,
    prev_url=prev_url,
    next_url=next_url,
    site_name='Snickerdoodle',
    now_year=now_year,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1800)


@web_bp.route('/about')
def about():
  """Render placeholder page for information about Snickerdoodle."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  html = flask.render_template(
    'about.html',
    canonical_url=urls.canonical_url(flask.url_for('web.about')),
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return html_response(html, cache_seconds=600, cdn_seconds=3600)


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
  urlset_parts.append(f'<loc>{base_url}/notes</loc>')
  urlset_parts.append(f'<lastmod>{now}</lastmod>')
  urlset_parts.append('<changefreq>weekly</changefreq>')
  urlset_parts.append('<priority>0.8</priority>')
  urlset_parts.append('</url>')
  for slug in sorted(notes_slugs):
    urlset_parts.append('<url>')
    urlset_parts.append(f'<loc>{base_url}/notes/{slug}</loc>')
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
