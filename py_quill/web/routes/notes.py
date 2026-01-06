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


def _select_best_sheet(sheets):
  sorted_sheets = _sorted_sheets(sheets)
  return sorted_sheets[0] if sorted_sheets else None


def _sorted_sheets(sheets):
  """Return valid sheets ordered by index (if set), then by quality signals.

  Ordering rules:
  - Only sheets with both image and PDF URIs are included.
  - Sheets with an integer index sort first, ascending by index.
  - Unindexed sheets sort after indexed ones, by avg_saved_users_fraction
    descending.
  - Ties fall back to sheet key and joke_str for deterministic ordering.
  """
  valid_sheets = [
    sheet for sheet in sheets if sheet.image_gcs_uri and sheet.pdf_gcs_uri
  ]
  valid_sheets.sort(key=lambda sheet: (
    0 if isinstance(sheet.index, int) else 1,
    sheet.index if isinstance(sheet.index, int) else 0,
    -(sheet.avg_saved_users_fraction or 0.0),
    sheet.key or "",
    sheet.joke_str or "",
  ))
  return valid_sheets


def _category_id(category):
  return category.id or getattr(category, "key", None)


def _category_label(category, category_id):
  display_name = (category.display_name or "").strip()
  if display_name:
    return display_name
  return category_id or ""


def _min_id_sheet(sheets):
  return min(sheets, key=lambda sheet: (sheet.key is None, sheet.key or ""))


def _total_sheet_count():
  total_sheet_count = 0
  counted_categories: set[str] = set()
  try:
    all_categories = firestore.get_all_joke_categories()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke categories: {exc}",
      extra={"json_fields": {
        "event": "notes_categories_fetch_failed",
      }},
    )
    return 0

  active_categories = [
    c for c in all_categories if c.state in ["APPROVED", "SEASONAL"]
  ]
  for category in active_categories:
    category_id = _category_id(category)
    if not category_id or category_id in counted_categories:
      continue
    try:
      sheets = firestore.get_joke_sheets_by_category(category_id)
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        f"Failed to fetch joke sheets for {category_id}: {exc}",
        extra={
          "json_fields": {
            "event": "notes_sheet_fetch_failed",
            "category_id": category_id,
          }
        },
      )
      continue
    total_sheet_count += len(sheets)
    counted_categories.add(category_id)

  return (total_sheet_count // 10) * 10


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
  total_sheet_count = 0
  counted_categories: set[str] = set()
  try:
    all_categories = firestore.get_all_joke_categories()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke categories: {exc}",
      extra={"json_fields": {
        "event": "notes_categories_fetch_failed",
      }},
    )
    all_categories = []

  active_categories = [
    c for c in all_categories if c.state in ["APPROVED", "SEASONAL"]
  ]
  category_entries = []
  for category in active_categories:
    category_id = _category_id(category)
    if not category_id:
      continue
    label = _category_label(category, category_id)
    if not label:
      continue
    category_entries.append({
      "category_id": category_id,
      "label": label,
    })

  download_cards: list[dict[str, str]] = []
  for entry in category_entries:
    category_id = entry["category_id"]
    category_label = entry["label"]
    try:
      sheets = firestore.get_joke_sheets_by_category(category_id)
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        f"Failed to fetch joke sheets for {category_id}: {exc}",
        extra={
          "json_fields": {
            "event": "notes_sheet_fetch_failed",
            "category_id": category_id,
          }
        },
      )
      continue

    sheets_with_slugs = [sheet for sheet in sheets if sheet.slug]
    if category_id not in counted_categories:
      total_sheet_count += len(sheets)
      counted_categories.add(category_id)
    sheet = _select_best_sheet(sheets_with_slugs)
    if not sheet:
      continue

    detail_url = flask.url_for('web.notes_detail', slug=sheet.slug)

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

  total_sheet_count = (total_sheet_count // 10) * 10
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

  canonical_slug = slug
  try:
    sheets = firestore.get_joke_sheets_by_category(category_id, index=index)
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke sheet for {category_id} index {index}: {exc}",
      extra={
        "json_fields": {
          "event": "notes_detail_sheet_fetch_failed",
          "category_id": category_id,
          "index": index,
        }
      },
    )
    return flask.redirect(flask.url_for('web.notes'))

  valid_sheets = [
    sheet for sheet in sheets if sheet.image_gcs_uri and sheet.pdf_gcs_uri
  ]
  if not valid_sheets:
    return flask.redirect(flask.url_for('web.notes'))

  sheet = _min_id_sheet(valid_sheets)
  if sheet.slug:
    canonical_slug = sheet.slug

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

  category = None
  try:
    category = firestore.get_joke_category(category_id)
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch category for {category_id}: {exc}",
      extra={
        "json_fields": {
          "event": "notes_detail_category_fetch_failed",
          "category_id": category_id,
        }
      },
    )

  category_label = _category_label(category, category_id) if category else (
    category_id or "")
  display_index = sheet.display_index or (index + 1)
  if display_index > 1:
    verification = auth_helpers.verify_session(flask.request)
    if not verification:
      return flask.redirect(flask.url_for('web.notes'))
  display_title = f"{category_label} Joke Pack {display_index}"
  page_title = f"{display_title} (Free PDF)"
  canonical_url = urls.canonical_url(
    flask.url_for('web.notes_detail', slug=canonical_slug))
  notes_continue_url = urls.canonical_url(flask.url_for('web.notes'))
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  total_sheet_count = _total_sheet_count()
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

  try:
    all_categories = firestore.get_all_joke_categories()
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(
      f"Failed to fetch joke categories: {exc}",
      extra={"json_fields": {
        "event": "notes_all_categories_fetch_failed",
      }},
    )
    all_categories = []

  active_categories = [
    c for c in all_categories if c.state in ["APPROVED", "SEASONAL"]
  ]
  category_entries = []
  for category in active_categories:
    category_id = _category_id(category)
    if not category_id:
      continue
    label = _category_label(category, category_id)
    if not label:
      continue
    category_entries.append({
      "category_id": category_id,
      "label": label,
    })

  category_entries.sort(key=lambda entry: entry["label"].casefold())

  categories = []
  for entry in category_entries:
    category_id = entry["category_id"]
    label = entry["label"]
    try:
      sheets = firestore.get_joke_sheets_by_category(category_id)
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        f"Failed to fetch joke sheets for {category_id}: {exc}",
        extra={
          "json_fields": {
            "event": "notes_sheet_fetch_failed",
            "category_id": category_id,
          }
        },
      )
      continue

    sorted_sheets = _sorted_sheets(sheets)
    sheet_cards = []
    for index, sheet in enumerate(sorted_sheets, start=1):
      try:
        pdf_url = cloud_storage.get_public_cdn_url(sheet.pdf_gcs_uri or "")
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

      sheet_cards.append({
        "title": f"Pack {index}",
        "image_url": image_url,
        "pdf_url": pdf_url,
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
