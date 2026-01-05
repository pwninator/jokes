"""Notes downloads page."""

from __future__ import annotations

import datetime

import flask
from firebase_functions import logger

from services import cloud_storage, firestore
from web.routes import web_bp
from web.utils.responses import html_response

_NOTES_CATEGORIES: list[tuple[str, str]] = [
  ("dogs", "Dogs"),
  ("cats", "Cats"),
  ("reptiles_and_dinosaurs", "Reptiles and Dinosaurs"),
]

_NOTES_IMAGE_MAX_WIDTH = 360
_NOTES_IMAGE_HEIGHT = int(round(_NOTES_IMAGE_MAX_WIDTH * (2550 / 3300)))


@web_bp.route('/notes')
def notes():
  """Render the notes download page."""
  now_year = datetime.datetime.now(datetime.timezone.utc).year
  canonical_url = flask.url_for('web.notes', _external=True)

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

    valid_sheets = [
      sheet for sheet in sheets if sheet.image_gcs_uri and sheet.pdf_gcs_uri
    ]
    if not valid_sheets:
      continue

    valid_sheets.sort(
      key=lambda sheet: (sheet.key or "", sheet.joke_str or ""))
    sheet = valid_sheets[0]
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

  html = flask.render_template(
    'notes.html',
    canonical_url=canonical_url,
    site_name='Snickerdoodle',
    now_year=now_year,
    prev_url=None,
    next_url=None,
    download_cards=download_cards,
    notes_image_width=_NOTES_IMAGE_MAX_WIDTH,
    notes_image_height=_NOTES_IMAGE_HEIGHT,
  )
  return html_response(html, cache_seconds=300, cdn_seconds=1200)
