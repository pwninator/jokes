"""Tests for notes routes."""

from __future__ import annotations

from common import config, models
from services import cloud_storage
from web.app import app
from web.routes import notes as notes_routes
from web.utils import urls


def test_notes_page_renders_download_cards(monkeypatch):
  called_categories: list[str] = []
  base_category_ids = [
    category_id for category_id, _ in notes_routes._NOTES_CATEGORIES
  ]
  extra_categories = {"space": "Space", "ocean": "Ocean"}
  extra_category_ids = list(extra_categories.keys())

  def _fake_get_joke_sheets_by_category(category_id: str):
    called_categories.append(category_id)
    return [
      models.JokeSheet(
        key=f"{category_id}-low",
        joke_ids=["j1"],
        category_id=category_id,
        image_gcs_uri=
        f"gs://image-bucket/joke_notes_sheets/{category_id}-low.png",
        pdf_gcs_uri=f"gs://pdf-bucket/joke_notes_sheets/{category_id}-low.pdf",
        avg_saved_users_fraction=0.1,
      ),
      models.JokeSheet(
        key=f"{category_id}-high",
        joke_ids=["j2"],
        category_id=category_id,
        image_gcs_uri=
        f"gs://image-bucket/joke_notes_sheets/{category_id}-high.png",
        pdf_gcs_uri=f"gs://pdf-bucket/joke_notes_sheets/{category_id}-high.pdf",
        avg_saved_users_fraction=0.9,
      )
    ]

  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_by_category",
                      _fake_get_joke_sheets_by_category)
  monkeypatch.setattr(
    notes_routes.firestore,
    "get_all_joke_categories",
    lambda: [
      models.JokeCategory(display_name="Dogs", id="dogs", state="APPROVED"),
      models.JokeCategory(display_name="Cats", id="cats", state="APPROVED"),
      models.JokeCategory(
        display_name=extra_categories["space"],
        id="space",
        state="APPROVED",
      ),
      models.JokeCategory(
        display_name=extra_categories["ocean"],
        id="ocean",
        state="APPROVED",
      ),
    ],
  )

  with app.test_client() as client:
    resp = client.get('/notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  total_sheets = (len(base_category_ids) + len(extra_category_ids)) * 2
  expected_count = (total_sheets // 10) * 10
  assert f"{expected_count}+" in html
  assert html.count(
    '<a class="nav-cta text-button notes-download-card__cta"') == len(
      base_category_ids + extra_category_ids)
  assert html.count(
    'data-analytics-event="web_notes_download_click"') == len(
      base_category_ids)
  assert html.count(
    'data-analytics-event="web_notes_unlock_download_click"') == len(
      extra_category_ids)
  assert 'href="#lunchbox-form-title"' in html
  assert html.count(
    '<article class="notes-download-card"') == len(base_category_ids +
                                                   extra_category_ids)
  assert html.count(
    '<h3 class="notes-download-card__title') == len(base_category_ids +
                                                    extra_category_ids)
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'sendSignInLinkToEmail' in html
  assert config.FIREBASE_WEB_CONFIG['projectId'] in html
  assert urls.canonical_url('/notes') in html
  assert f'width="{notes_routes._NOTES_IMAGE_MAX_WIDTH}"' in html
  assert f'height="{notes_routes._NOTES_IMAGE_HEIGHT}"' in html
  for category_id, display_name in extra_categories.items():
    assert f"{display_name} (2 Packs)" in html

  for category_id in base_category_ids + extra_category_ids:
    assert f'data-analytics-label="{category_id}"' in html
    image_gcs_uri = (
      f"gs://image-bucket/joke_notes_sheets/{category_id}-high.png")
    pdf_gcs_uri = f"gs://pdf-bucket/joke_notes_sheets/{category_id}-high.pdf"
    expected_image_url = cloud_storage.get_public_image_cdn_url(
      image_gcs_uri,
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    assert expected_image_url in html
    expected_pdf_url = cloud_storage.get_public_cdn_url(pdf_gcs_uri)
    if category_id in base_category_ids:
      assert expected_pdf_url in html
    else:
      assert expected_pdf_url not in html

    low_image_url = cloud_storage.get_public_image_cdn_url(
      f"gs://image-bucket/joke_notes_sheets/{category_id}-low.png",
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    assert low_image_url not in html
    if category_id in base_category_ids:
      low_pdf_url = cloud_storage.get_public_cdn_url(
        f"gs://pdf-bucket/joke_notes_sheets/{category_id}-low.pdf")
      assert low_pdf_url not in html

  assert called_categories == base_category_ids + extra_category_ids
