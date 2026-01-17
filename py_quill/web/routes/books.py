"""Book promo page route."""

from __future__ import annotations

import datetime

import flask
from common import amazon_redirect
from web.routes import web_bp
from web.routes.redirects import resolve_request_country_code
from web.utils import urls
from web.utils.responses import html_response


@web_bp.route('/books')
def books():
  """Render a simple book promo page."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year

  ref = flask.request.args.get('ref')
  is_download_redirect = ref == 'notes_download'
  if is_download_redirect:
    hero_title = (
      "Like the notes? There's a whole lot more where those came from!")
    hero_subtitle = (
      'The jokes are hand-picked favorites from our paperback book. Get the full collection of 36 illustrated jokes today.'
    )
  else:
    hero_title = 'Super Cute. Super Silly. Totally Screen-Free.'
    hero_subtitle = '36 pages of adorable animals and belly laughs, no charger required.'

  country_code = resolve_request_country_code(flask.request)
  redirect_config = amazon_redirect.AMAZON_REDIRECTS['book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source='web_book_page',
  )

  html = flask.render_template(
    'books.html',
    canonical_url=urls.canonical_url(flask.url_for('web.books')),
    amazon_url=amazon_url,
    hero_title=hero_title,
    hero_subtitle=hero_subtitle,
    show_success_banner=is_download_redirect,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)
