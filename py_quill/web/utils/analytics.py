"""GA4 + Meta Pixel tracking helpers for web redirect pages."""

from __future__ import annotations

import datetime
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

import flask
import requests
from firebase_functions import logger

from common import config
from web.utils.responses import html_no_store_response

GA4_MEASUREMENT_ID = "G-D2B7E8PXJJ"
_GA4_TIMEOUT_SECONDS = 1.0
_GA4_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_GA_COOKIE_CLIENT_ID_RE = re.compile(r"^\d+\.\d+$")


def ga4_client_id_for_request(req: flask.Request) -> str:
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


def submit_ga4_event_fire_and_forget(
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
      requests.post(
        url,
        params=params,
        json=payload,
        headers=headers,
        timeout=_GA4_TIMEOUT_SECONDS,
      )
    except Exception as exc:  # pylint: disable=broad-except
      logger.warn(f"Failed to send GA4 MP event '{event_name}': {exc}")

  future = _GA4_EXECUTOR.submit(_send)

  def _log_unexpected_error(fut) -> None:  # pragma: no cover
    try:
      fut.result()
    except Exception as exc:  # pylint: disable=broad-except
      logger.warn(f"Unexpected GA4 MP failure: {exc}")

  future.add_done_callback(_log_unexpected_error)


def render_ga4_redirect_page(
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

  client_id = ga4_client_id_for_request(flask.request)
  submit_ga4_event_fire_and_forget(
    measurement_id=GA4_MEASUREMENT_ID,
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
  return html_no_store_response(html, status=200)
