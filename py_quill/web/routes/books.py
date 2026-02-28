"""Book promo page route."""

from __future__ import annotations

import datetime

import flask
from common import amazon_redirect
from firebase_functions import logger
from services import firestore
from web.routes import web_bp
from web.routes.redirects import (get_books_attribution_source,
                                  resolve_request_country_code)
from web.utils import urls
from web.utils.responses import html_response

_BOOK_SAMPLE_JOKE_IDS = [
  'because_they_can_t_catch_it__why_didn_t_lions_like_fast_foo',
  'honey__i_m_home__what_did_the_bee_say_when_it_r',
  'the_mew_seum__where_did_the_kittens_go_for_t',
]


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
  attribution_source = get_books_attribution_source(
    flask.request, default_source='web_book_page')
  redirect_config = amazon_redirect.AMAZON_REDIRECTS_BY_SLUG[
    'book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source=attribution_source,
  )
  sample_jokes = []
  try:
    fetched_sample_jokes = firestore.get_punny_jokes(_BOOK_SAMPLE_JOKE_IDS)
    jokes_by_id = {joke.key: joke for joke in fetched_sample_jokes if joke.key}
    sample_jokes = [
      jokes_by_id[joke_id] for joke_id in _BOOK_SAMPLE_JOKE_IDS
      if joke_id in jokes_by_id
    ]
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f'Failed to fetch book sample jokes: {exc}')

  html = flask.render_template(
    'books.html',
    canonical_url=urls.canonical_url(flask.url_for('web.books')),
    amazon_url=amazon_url,
    hero_title=hero_title,
    hero_subtitle=hero_subtitle,
    sample_jokes=sample_jokes,
    show_success_banner=is_download_redirect,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)
