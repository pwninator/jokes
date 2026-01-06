"""Notes downloads page."""

from __future__ import annotations

import datetime

import flask
from firebase_functions import logger
from common import config, models
from functions import auth_helpers
from services import cloud_storage, firestore
from web.routes import web_bp
from web.utils import urls
from web.utils.responses import html_no_store_response, html_response

_NOTES_IMAGE_MAX_WIDTH = 360
_NOTES_IMAGE_HEIGHT = int(round(_NOTES_IMAGE_MAX_WIDTH * (2550 / 3300)))
_NOTES_DETAIL_IMAGE_MAX_WIDTH = 1100
_NOTES_DETAIL_IMAGE_HEIGHT = int(
  round(_NOTES_DETAIL_IMAGE_MAX_WIDTH * (2550 / 3300)))


@web_bp.route('/notes')
def notes():
  """Render the notes download page."""
  verification = auth_helpers.verify_session(flask.request)
  if verification:
    return flask.redirect(flask.url_for('web.notes_all'))

  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = urls.canonical_url(flask.url_for('web.notes'))
  error_message = None
  email_value = ''
  cache_entries = _get_joke_sheets_cache()
  total_sheet_count = _total_sheet_count(cache_entries)

  download_cards: list[dict[str, str]] = []
  for category, sheets in cache_entries:
    category_id = category.id
    category_label = category.display_name
    if not category_id:
      continue
    if not sheets:
      continue
    sheet = sheets[0]
    if sheet.index is None:
      continue
    detail_url = flask.url_for(
      'web.notes_detail',
      slug=_cache_sheet_slug(category_id, sheet.index),
    )

    try:
      image_url = cloud_storage.get_public_image_cdn_url(
        sheet.image_gcs_uri or "",
        width=_NOTES_IMAGE_MAX_WIDTH,
      )
    except ValueError as exc:
      logger.error(
        f"Failed to build URLs for {category_id} sheet: {exc}",
        extra={
          "json_fields": {
            "event": "notes_sheet_url_failed",
            "category_id": category_id,
          }
        },
      )
      continue

    download_cards.append({
      "category_id": category_id,
      "category_label": category_label,
      "image_url": image_url,
      "detail_url": detail_url,
    })
  html = flask.render_template(
    'notes.html',
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    error_message=error_message,
    email_value=email_value,
    download_cards=download_cards,
    total_sheet_count=total_sheet_count,
    notes_image_width=_NOTES_IMAGE_MAX_WIDTH,
    notes_image_height=_NOTES_IMAGE_HEIGHT,
    firebase_config=config.FIREBASE_WEB_CONFIG,
    email_link_url=canonical_url,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/notes/<slug>')
def notes_detail(slug: str):
  """Render a joke sheet details page."""
  category_id, index = models.JokeSheet.parse_slug(slug)
  if not category_id or index is None:
    return flask.redirect(flask.url_for('web.notes'))

  cache_entries = _get_joke_sheets_cache()
  category = None
  sheets: list[models.JokeSheet] = []
  for entry_category, entry_sheets in cache_entries:
    if entry_category.id == category_id:
      category = entry_category
      sheets = entry_sheets
      break
  if not category:
    return flask.redirect(flask.url_for('web.notes'))

  if index < 0 or index >= len(sheets):
    return flask.redirect(flask.url_for('web.notes'))

  sheet = sheets[index]
  try:
    pdf_url = cloud_storage.get_public_cdn_url(sheet.pdf_gcs_uri or "")
    image_url = cloud_storage.get_public_image_cdn_url(
      sheet.image_gcs_uri or "",
      width=_NOTES_DETAIL_IMAGE_MAX_WIDTH,
    )
  except ValueError as exc:
    logger.error(
      f"Failed to build URLs for {category_id} sheet: {exc}",
      extra={
        "json_fields": {
          "event": "notes_detail_sheet_url_failed",
          "category_id": category_id,
          "index": index,
        }
      },
    )
    return flask.redirect(flask.url_for('web.notes'))

  category_label = category.display_name
  display_index = sheet.display_index or (index + 1)
  if display_index > 1:
    verification = auth_helpers.verify_session(flask.request)
    if not verification:
      return flask.redirect(flask.url_for('web.notes'))
  display_title = f"{category_label} Joke Pack {display_index}"
  page_title = f"{display_title} (Free PDF)"
  canonical_slug = _cache_sheet_slug(category_id, index)
  canonical_url = urls.canonical_url(
    flask.url_for('web.notes_detail', slug=canonical_slug))
  notes_continue_url = urls.canonical_url(flask.url_for('web.notes'))
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  total_sheet_count = _total_sheet_count(cache_entries)
  html = flask.render_template(
    'notes_detail.html',
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    category_id=category_id,
    category_label=category_label,
    sheet_index=index,
    sheet_display_index=display_index,
    sheet_slug=canonical_slug,
    display_title=display_title,
    page_title=page_title,
    image_url=image_url,
    pdf_url=pdf_url,
    notes_detail_image_width=_NOTES_DETAIL_IMAGE_MAX_WIDTH,
    notes_detail_image_height=_NOTES_DETAIL_IMAGE_HEIGHT,
    email_link_url=notes_continue_url,
    notes_hook_text=f"Want More {category_label} Joke Packs?",
    email_value='',
    error_message=None,
    total_sheet_count=total_sheet_count,
    firebase_config=config.FIREBASE_WEB_CONFIG,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)


@web_bp.route('/notes-all')
def notes_all():
  """Render the authenticated notes download page."""
  verification = auth_helpers.verify_session(flask.request)
  if not verification:
    return flask.redirect(flask.url_for('web.notes'))

  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = urls.canonical_url(flask.url_for('web.notes_all'))

  cache_entries = _get_joke_sheets_cache()
  cache_entries.sort(key=lambda entry: entry[0].display_name.casefold())

  categories = []
  for category, sorted_sheets in cache_entries:
    category_id = category.id
    label = category.display_name
    if not category_id:
      continue
    sheet_cards = []
    for index, sheet in enumerate(sorted_sheets, start=1):
      try:
        image_url = cloud_storage.get_public_image_cdn_url(
          sheet.image_gcs_uri or "",
          width=_NOTES_IMAGE_MAX_WIDTH,
        )
      except ValueError as exc:
        logger.error(
          f"Failed to build URLs for {category_id} sheet: {exc}",
          extra={
            "json_fields": {
              "event": "notes_sheet_url_failed",
              "category_id": category_id,
            }
          },
        )
        continue

      detail_url = flask.url_for(
        'web.notes_detail',
        slug=_cache_sheet_slug(category_id, sheet.index or index - 1),
      )
      sheet_cards.append({
        "title": f"Pack {index}",
        "image_url": image_url,
        "detail_url": detail_url,
        "sheet_key": sheet.key or "",
      })

    categories.append({
      "category_id": category_id,
      "label": label,
      "sheet_count": len(sheet_cards),
      "sheets": sheet_cards,
    })

  html = flask.render_template(
    'notes_all.html',
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    categories=categories,
    notes_image_width=_NOTES_IMAGE_MAX_WIDTH,
    notes_image_height=_NOTES_IMAGE_HEIGHT,
  )
  return html_no_store_response(html)


def _cache_sheet_slug(category_id: str, index: int) -> str:
  category_slug = category_id.replace("_", "-")
  return f"free-{category_slug}-jokes-{index + 1}"


def _get_joke_sheets_cache(
) -> list[tuple[models.JokeCategory, list[models.JokeSheet]]]:
  try:
    return firestore.get_joke_sheets_cache()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke sheets cache: {exc}",
      extra={"json_fields": {
        "event": "notes_cache_fetch_failed",
      }},
    )
    return []


def _total_sheet_count(
  cache_entries: list[tuple[models.JokeCategory, list[models.JokeSheet]]],
) -> int:
  total_sheet_count = sum(len(sheets) for _, sheets in cache_entries)
  return (total_sheet_count // 10) * 10
