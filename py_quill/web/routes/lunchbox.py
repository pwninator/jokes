"""Lunchbox lead capture routes."""

from __future__ import annotations

import datetime
import re

import flask
from firebase_functions import logger

from common import amazon_redirect, joke_lead_operations
from web.routes import web_bp
from web.routes.redirects import resolve_request_country_code
from web.utils import analytics
from web.utils import urls
from web.utils.responses import html_no_store_response, html_response

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@web_bp.route('/lunchbox', methods=['GET', 'POST'])
def lunchbox():
  """Render / handle the lunchbox lead capture page."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = urls.canonical_url(flask.url_for('web.lunchbox'))

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
        country_code = resolve_request_country_code(flask.request)
        _ = joke_lead_operations.create_lead(
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
    return html_no_store_response(html, status=status_override or 400)
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/lunchbox-thank-you')
def lunchbox_thank_you():
  """Thank you page after lead submission."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year

  # Resolve Amazon URL based on user's country
  country_code = resolve_request_country_code(flask.request)
  redirect_config = amazon_redirect.AMAZON_REDIRECTS_BY_SLUG[
    'book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source='lunchbox_thank_you',
  )

  html = flask.render_template(
    'lunchbox_thank_you.html',
    canonical_url=urls.canonical_url(flask.url_for('web.lunchbox_thank_you')),
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    amazon_url=amazon_url,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/lunchbox-download-pdf')
def lunchbox_download_pdf():
  """Redirect helper that sends users to the lunchbox PDF download."""
  download_url = "/lunchbox/lunchbox_notes_animal_jokes.pdf"
  event_params = {
    'asset': 'lunchbox_notes_animal_jokes.pdf',
  }
  return analytics.render_ga4_redirect_page(
    target_url=download_url,
    canonical_url=urls.canonical_url(
      flask.url_for('web.lunchbox_download_pdf')),
    page_title='Lunchbox Notes Download',
    heading='Starting your download…',
    message="If it doesn't start automatically, use the button below.",
    link_text='Download the PDF',
    ga4_event_base_name='web_lunchbox_download',
    ga4_event_params=event_params,
    meta_pixel_event_name='CompleteRegistration',
  )
