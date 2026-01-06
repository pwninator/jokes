"""Tests for notes routes."""

from __future__ import annotations

from html import escape

from common import config, models
from functions import auth_helpers
from services import cloud_storage
from web.app import app
from web.routes import notes as notes_routes
from web.utils import urls


def test_notes_page_renders_download_cards(monkeypatch):
  called_categories: list[str] = []
  active_category_entries = [
    ("dogs", "Dogs"),
    ("cats", "Cats"),
    ("reptiles_and_dinosaurs", "Dinos & Reptiles"),
    ("space", "Space"),
    ("ocean", "Ocean"),
  ]
  active_category_ids = [
    category_id for category_id, _ in active_category_entries
  ]

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
      models.JokeCategory(
        display_name=display_name,
        id=category_id,
        state="APPROVED",
      ) for category_id, display_name in active_category_entries
    ] + [
      models.JokeCategory(
        display_name="Hidden",
        id="hidden",
        state="DRAFT",
      ),
    ],
  )

  with app.test_client() as client:
    resp = client.get('/notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  total_sheets = len(active_category_ids) * 2
  expected_count = (total_sheets // 10) * 10
  assert f"{expected_count}+" in html
  assert html.count(
    '<a class="nav-cta text-button notes-sampler-card__cta"') == len(
      active_category_ids)
  assert html.count(
    'data-analytics-event="web_notes_download_click"') == len(
      active_category_ids)
  assert html.count(
    '<article class="notes-sampler-card"') == len(active_category_ids)
  assert html.count(
    '<h3 class="notes-sampler-card__title') == len(active_category_ids)
  assert 'web_notes_unlock_download_click' not in html
  assert 'extra-notes-download-title' not in html
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'sendSignInLinkToEmail' in html
  assert config.FIREBASE_WEB_CONFIG['projectId'] in html
  assert urls.canonical_url('/notes') in html
  assert f'width="{notes_routes._NOTES_IMAGE_MAX_WIDTH}"' in html
  assert f'height="{notes_routes._NOTES_IMAGE_HEIGHT}"' in html
  for _, display_name in active_category_entries:
    escaped_name = escape(display_name)
    assert f"{escaped_name} Pack</h3>" in html
  for category_id in active_category_ids:
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
    assert expected_pdf_url in html

    low_image_url = cloud_storage.get_public_image_cdn_url(
      f"gs://image-bucket/joke_notes_sheets/{category_id}-low.png",
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    assert low_image_url not in html
    low_pdf_url = cloud_storage.get_public_cdn_url(
      f"gs://pdf-bucket/joke_notes_sheets/{category_id}-low.pdf")
    assert low_pdf_url not in html

  assert called_categories == active_category_ids


def test_notes_redirects_authenticated_user(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session",
                      lambda _req: ("user-123", {
                        "uid": "user-123"
                      }))

  with app.test_client() as client:
    resp = client.get('/notes')

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/notes-all')


def test_notes_all_redirects_logged_out_user(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get('/notes-all')

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/notes')


def test_notes_all_renders_categories_and_sheets(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session",
                      lambda _req: ("user-123", {
                        "uid": "user-123"
                      }))

  categories = [
    models.JokeCategory(display_name="Zany", id="zany", state="APPROVED"),
    models.JokeCategory(display_name="Animals", id="animals", state="APPROVED"),
    models.JokeCategory(display_name="Breezy", id="breezy", state="SEASONAL"),
  ]
  monkeypatch.setattr(notes_routes.firestore, "get_all_joke_categories",
                      lambda: categories)

  sheets_by_category = {
    "animals": [
      models.JokeSheet(
        key="animals-low",
        joke_ids=["j1"],
        category_id="animals",
        image_gcs_uri=
        "gs://image-bucket/joke_notes_sheets/animals-low.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-low.pdf",
        avg_saved_users_fraction=0.2,
      ),
      models.JokeSheet(
        key="animals-high",
        joke_ids=["j2"],
        category_id="animals",
        image_gcs_uri=
        "gs://image-bucket/joke_notes_sheets/animals-high.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-high.pdf",
        avg_saved_users_fraction=0.9,
      ),
      models.JokeSheet(
        key="animals-invalid",
        joke_ids=["j3"],
        category_id="animals",
        image_gcs_uri=None,
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-invalid.pdf",
        avg_saved_users_fraction=0.95,
      ),
    ],
    "breezy": [],
    "zany": [
      models.JokeSheet(
        key="zany-low",
        joke_ids=["j4"],
        category_id="zany",
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/zany-low.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/zany-low.pdf",
        avg_saved_users_fraction=0.1,
      ),
      models.JokeSheet(
        key="zany-high",
        joke_ids=["j5"],
        category_id="zany",
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/zany-high.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/zany-high.pdf",
        avg_saved_users_fraction=0.8,
      ),
    ],
  }

  def _fake_get_joke_sheets_by_category(category_id: str):
    return sheets_by_category.get(category_id, [])

  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_by_category",
                      _fake_get_joke_sheets_by_category)

  with app.test_client() as client:
    resp = client.get('/notes-all')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  animals_pos = html.find('notes-download-animals-title')
  breezy_pos = html.find('notes-download-breezy-title')
  zany_pos = html.find('notes-download-zany-title')
  assert animals_pos != -1
  assert breezy_pos != -1
  assert zany_pos != -1
  assert animals_pos < breezy_pos < zany_pos

  animals_high_pdf = cloud_storage.get_public_cdn_url(
    "gs://pdf-bucket/joke_notes_sheets/animals-high.pdf")
  animals_low_pdf = cloud_storage.get_public_cdn_url(
    "gs://pdf-bucket/joke_notes_sheets/animals-low.pdf")
  assert html.find(animals_high_pdf) < html.find(animals_low_pdf)
  assert "animals-invalid.pdf" not in html

  zany_high_pdf = cloud_storage.get_public_cdn_url(
    "gs://pdf-bucket/joke_notes_sheets/zany-high.pdf")
  zany_low_pdf = cloud_storage.get_public_cdn_url(
    "gs://pdf-bucket/joke_notes_sheets/zany-low.pdf")
  assert html.find(zany_high_pdf) < html.find(zany_low_pdf)
