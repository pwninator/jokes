"""Notes downloads page."""

from __future__ import annotations

import datetime

import flask
from firebase_functions import logger
from common import config
from services import cloud_storage, firestore
from web.routes import web_bp
from web.utils.responses import html_response

_NOTES_CATEGORIES: list[tuple[str, str]] = [
  ("dogs", "Funny Dogs Pack"),
  ("cats", "Silly Cats Pack"),
  ("reptiles_and_dinosaurs", "Dinos & Reptiles Pack"),
]

_NOTES_IMAGE_MAX_WIDTH = 360
_NOTES_IMAGE_HEIGHT = int(round(_NOTES_IMAGE_MAX_WIDTH * (2550 / 3300)))


def _select_best_sheet(sheets):
  valid_sheets = [
    sheet for sheet in sheets if sheet.image_gcs_uri and sheet.pdf_gcs_uri
  ]
  if not valid_sheets:
    return None

  valid_sheets.sort(key=lambda sheet: (
    -(sheet.avg_saved_users_fraction or 0.0),
    sheet.key or "",
    sheet.joke_str or "",
  ))
  return valid_sheets[0]


@web_bp.route('/notes')
def notes():
  """Render the notes download page."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = flask.url_for('web.notes', _external=True)
  error_message = None
  email_value = ''
  total_sheet_count = 0
  counted_categories: set[str] = set()

  download_cards: list[dict[str, str]] = []
  for category_id, category_label in _NOTES_CATEGORIES:
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

    if category_id not in counted_categories:
      total_sheet_count += len(sheets)
      counted_categories.add(category_id)
    sheet = _select_best_sheet(sheets)
    if not sheet:
      continue
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

    download_cards.append({
      "category_id": category_id,
      "category_label": category_label,
      "image_url": image_url,
      "pdf_url": pdf_url,
    })

  extra_download_cards: list[dict[str, str]] = []
  category_ids = {category_id for category_id, _ in _NOTES_CATEGORIES}
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
  for category in active_categories:
    category_id = category.id or category.key
    if not category_id or category_id in category_ids:
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

    if category_id not in counted_categories:
      total_sheet_count += len(sheets)
      counted_categories.add(category_id)
    display_name = (category.display_name or "").strip()
    if not display_name:
      continue

    sheet = _select_best_sheet(sheets)
    if not sheet:
      continue

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

    extra_download_cards.append({
      "category_id": category_id,
      "display_name": display_name,
      "image_url": image_url,
      "sheet_count": len(sheets),
    })

  total_sheet_count = (total_sheet_count // 10) * 10
  email_link_url = f"http://{config.ADMIN_HOST}/notes"
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
    extra_download_cards=extra_download_cards,
    total_sheet_count=total_sheet_count,
    notes_image_width=_NOTES_IMAGE_MAX_WIDTH,
    notes_image_height=_NOTES_IMAGE_HEIGHT,
    firebase_config=config.FIREBASE_WEB_CONFIG,
    email_link_url=email_link_url,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)
