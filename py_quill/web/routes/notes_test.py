"""Tests for notes routes."""

from __future__ import annotations

from common import models
from services import cloud_storage
from web.app import app
from web.routes import notes as notes_routes


def test_notes_page_renders_download_cards(monkeypatch):
  called_categories: list[str] = []

  def _fake_get_joke_sheets_by_category(category_id: str):
    called_categories.append(category_id)
    return [
      models.JokeSheet(
        key=f"{category_id}-1",
        joke_ids=["j1"],
        category_id=category_id,
        image_gcs_uri=
        f"gs://image-bucket/joke_notes_sheets/{category_id}.png",
        pdf_gcs_uri=f"gs://pdf-bucket/joke_notes_sheets/{category_id}.pdf",
      )
    ]

  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_by_category",
                      _fake_get_joke_sheets_by_category)

  with app.test_client() as client:
    resp = client.get('/notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Turn Lunchtime into Giggle Time!' in html
  assert html.count(
    '<a class="nav-cta text-button notes-download-card__cta"') == 3
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert f'width="{notes_routes._NOTES_IMAGE_MAX_WIDTH}"' in html
  assert f'height="{notes_routes._NOTES_IMAGE_HEIGHT}"' in html

  for category_id in ["dogs", "cats", "reptiles_and_dinosaurs"]:
    image_gcs_uri = f"gs://image-bucket/joke_notes_sheets/{category_id}.png"
    pdf_gcs_uri = f"gs://pdf-bucket/joke_notes_sheets/{category_id}.pdf"
    expected_image_url = cloud_storage.get_public_image_cdn_url(
      image_gcs_uri,
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    expected_pdf_url = cloud_storage.get_public_cdn_url(pdf_gcs_uri)
    assert expected_image_url in html
    assert expected_pdf_url in html

  assert called_categories == ["dogs", "cats", "reptiles_and_dinosaurs"]
