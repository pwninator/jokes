"""About page route."""

from __future__ import annotations

import datetime

import flask
from common import amazon_redirect
from web.routes import web_bp
from web.routes.redirects import (get_books_attribution_source,
                                  resolve_request_country_code)
from web.utils import urls
from web.utils.responses import html_response


@web_bp.route('/about')
def about():
  """Render placeholder page for information about Snickerdoodle."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  country_code = resolve_request_country_code(flask.request)
  attribution_source = get_books_attribution_source(
    flask.request, default_source='web_book_page')
  redirect_config = amazon_redirect.AMAZON_REDIRECTS_BY_SLUG[
    'book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source=attribution_source,
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
