"""Amazon redirect routes and helpers."""

from __future__ import annotations

import flask
from common import amazon_redirect
from firebase_functions import logger
from web.routes import web_bp
from web.utils import analytics


def resolve_request_country_code(req: flask.Request) -> str:
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


def _log_amazon_redirect(
  redirect_key: str,
  requested_country: str,
  resolved_country: str,
  target_url: str,
  source: str | None = None,
) -> None:
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


def _handle_amazon_redirect(redirect_key: str) -> flask.Response:
  """Shared handler for public Amazon redirect endpoints."""
  config_entry = amazon_redirect.AMAZON_REDIRECTS.get(redirect_key)
  if not config_entry:
    return flask.Response('Redirect not found', status=404)

  requested_country = resolve_request_country_code(flask.request)
  source = flask.request.args.get('source') or "aa"

  target_url, resolved_country, resolved_asin = config_entry.resolve_target_url(
    requested_country,
    source,
  )
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

  return analytics.render_ga4_redirect_page(
    target_url=target_url,
    canonical_url=flask.request.url,
    page_title=config_entry.label,
    heading='Redirecting to Amazon…',
    message='Taking you to Amazon now.',
    link_text='Continue to Amazon',
    ga4_event_base_name='amazon_redirect',
    ga4_event_params=event_params,
  )


def redirect_endpoint_for_key(
    redirect_key: str) -> tuple[str | None, str | None]:
  """Return endpoint name and slug for a redirect key."""
  if redirect_key.startswith('review-'):
    slug = redirect_key.removeprefix('review-')
    return 'web.amazon_review_redirect', slug
  if redirect_key.startswith('book-'):
    slug = redirect_key.removeprefix('book-')
    return 'web.amazon_book_redirect', slug
  return None, None


def amazon_redirect_view_models() -> list[dict[str, str]]:
  """Return metadata for all configured Amazon redirects."""
  items: list[dict[str, str]] = []
  for key, config_entry in amazon_redirect.AMAZON_REDIRECTS.items():
    endpoint, slug = redirect_endpoint_for_key(key)
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


@web_bp.route('/review-<path:slug>')
def amazon_review_redirect(slug: str):
  """Redirect to an Amazon review page for supported slugs."""
  return _handle_amazon_redirect(f'review-{slug}')


@web_bp.route('/book-<path:slug>')
def amazon_book_redirect(slug: str):
  """Redirect to an Amazon product page for supported slugs."""
  return _handle_amazon_redirect(f'book-{slug}')
