"""About page route."""

from __future__ import annotations

import datetime

import flask

from common import amazon_redirect
from web.routes import web_bp
from web.routes.redirects import resolve_request_country_code
from web.utils import urls
from web.utils.responses import html_response


@web_bp.route('/about')
def about():
  """Render placeholder page for information about Snickerdoodle."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  country_code = resolve_request_country_code(flask.request)
  redirect_config = amazon_redirect.AMAZON_REDIRECTS['book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source='web_book_page',
  )
  html = flask.render_template(
    'about.html',
    canonical_url=urls.canonical_url(flask.url_for('web.about')),
    amazon_url=amazon_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return html_response(html, cache_seconds=600, cdn_seconds=3600)
