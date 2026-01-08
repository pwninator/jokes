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
  cache_entries = []
  for category_id, display_name in active_category_entries:
    category = models.JokeCategory(id=category_id,
                                   display_name=display_name,
                                   state="APPROVED")
    sheets = [
      models.JokeSheet(
        key=f"{category_id}-low",
        category_id=category_id,
        index=0,
        image_gcs_uri=
        f"gs://image-bucket/joke_notes_sheets/{category_id}-low.png",
        pdf_gcs_uri=f"gs://pdf-bucket/joke_notes_sheets/{category_id}-low.pdf",
      ),
      models.JokeSheet(
        key=f"{category_id}-high",
        category_id=category_id,
        index=1,
        image_gcs_uri=
        f"gs://image-bucket/joke_notes_sheets/{category_id}-high.png",
        pdf_gcs_uri=f"gs://pdf-bucket/joke_notes_sheets/{category_id}-high.pdf",
      ),
    ]
    cache_entries.append((category, sheets))

  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: cache_entries)

  with app.test_client() as client:
    resp = client.get('/printables/notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  total_sheets = len(active_category_ids) * 2
  expected_count = (total_sheets // 10) * 10
  assert f"{expected_count}+" in html
  assert html.count(
    '<a class="nav-cta text-button notes-card__cta button-full"') == len(
      active_category_ids)
  assert html.count(
    'data-analytics-event="web_notes_view_pack_click"') == len(
      active_category_ids)
  assert html.count('View Pack') == len(active_category_ids)
  assert html.count(
    '<article class="notes-card"') == len(active_category_ids)
  assert html.count(
    '<h3 class="notes-card__title') == len(active_category_ids)
  assert 'web_notes_unlock_download_click' not in html
  assert 'extra-notes-download-title' not in html
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'sendSignInLinkToEmail' in html
  assert config.FIREBASE_WEB_CONFIG['projectId'] in html
  assert urls.canonical_url('/printables/notes') in html
  assert f'width="{notes_routes._NOTES_IMAGE_MAX_WIDTH}"' in html
  assert f'height="{notes_routes._NOTES_IMAGE_HEIGHT}"' in html
  for _, display_name in active_category_entries:
    escaped_name = escape(display_name)
    assert f"{escaped_name} Pack</h3>" in html
  for category_id in active_category_ids:
    assert f'data-analytics-label="{category_id}"' in html
    category_slug = category_id.replace("_", "-")
    detail_url = f"/printables/notes/free-{category_slug}-jokes-1"
    assert detail_url in html
    image_gcs_uri = (
      f"gs://image-bucket/joke_notes_sheets/{category_id}-low.png")
    expected_image_url = cloud_storage.get_public_image_cdn_url(
      image_gcs_uri,
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    assert expected_image_url in html

    high_image_url = cloud_storage.get_public_image_cdn_url(
      f"gs://image-bucket/joke_notes_sheets/{category_id}-high.png",
      width=notes_routes._NOTES_IMAGE_MAX_WIDTH,
    )
    assert high_image_url not in html


def test_notes_page_skips_sheet_without_slug(monkeypatch):
  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: [])

  with app.test_client() as client:
    resp = client.get('/printables/notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "New printable joke notes are on the way. Check back soon." in html
  assert '<article class="notes-card"' not in html


def test_notes_legacy_redirects_to_printables():
  with app.test_client() as client:
    resp = client.get('/notes')

  assert resp.status_code == 301
  assert resp.headers["Location"].endswith('/printables/notes')


def test_notes_detail_legacy_redirects_to_printables():
  slug = "free-animals-jokes-1"
  with app.test_client() as client:
    resp = client.get(f"/notes/{slug}")

  assert resp.status_code == 301
  assert resp.headers["Location"].endswith(f"/printables/notes/{slug}")


def test_notes_all_legacy_redirects_to_printables():
  with app.test_client() as client:
    resp = client.get('/notes-all')

  assert resp.status_code == 301
  assert resp.headers["Location"].endswith('/printables/notes/all')


def test_notes_detail_renders_sheet(monkeypatch):
  category_id = "animals"
  slug = "free-animals-jokes-1"
  sheet_a = models.JokeSheet(
    key="a-sheet",
    category_id=category_id,
    index=0,
    image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-a.png",
    pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-a.pdf",
  )
  sheet_b = models.JokeSheet(
    key="b-sheet",
    category_id=category_id,
    index=1,
    image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-b.png",
    pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-b.pdf",
  )
  category = models.JokeCategory(display_name="Animals",
                                 id=category_id,
                                 state="APPROVED")
  cats = models.JokeCategory(display_name="Cats", id="cats", state="APPROVED")
  dogs = models.JokeCategory(display_name="Dogs", id="dogs", state="APPROVED")
  space = models.JokeCategory(display_name="Space",
                              id="space",
                              state="APPROVED")
  cats_sheet = models.JokeSheet(
    key="cats-sheet",
    category_id="cats",
    index=0,
    image_gcs_uri="gs://image-bucket/joke_notes_sheets/cats-a.png",
    pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/cats-a.pdf",
  )
  dogs_sheet = models.JokeSheet(
    key="dogs-sheet",
    category_id="dogs",
    index=0,
    image_gcs_uri="gs://image-bucket/joke_notes_sheets/dogs-a.png",
    pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/dogs-a.pdf",
  )
  space_sheet = models.JokeSheet(
    key="space-sheet",
    category_id="space",
    index=0,
    image_gcs_uri="gs://image-bucket/joke_notes_sheets/space-a.png",
    pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/space-a.pdf",
  )

  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: [
                        (category, [sheet_a, sheet_b]),
                        (cats, [cats_sheet]),
                        (dogs, [dogs_sheet]),
                        (space, [space_sheet]),
                      ])
  monkeypatch.setattr(notes_routes.random, "sample",
                      lambda population, k: population[:k])

  with app.test_client() as client:
    resp = client.get(f"/printables/notes/{slug}")

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Animals Joke Pack 1" in html
  assert "<title>Animals Joke Pack 1 (Free PDF)" in html
  assert urls.canonical_url(f"/printables/notes/{slug}") in html
  assert urls.canonical_url("/printables/notes") in html
  assert "Download Free PDF" in html
  assert "Want More Animals Joke Packs?" in html
  assert "You Might Also Like" in html
  assert "sendSignInLinkToEmail" in html
  assert html.count(
    'data-analytics-event="web_notes_view_pack_click"') == 3
  image_url = cloud_storage.get_public_image_cdn_url(
    sheet_a.image_gcs_uri,
    width=notes_routes._NOTES_DETAIL_IMAGE_MAX_WIDTH,
  )
  assert image_url in html
  pdf_url = cloud_storage.get_public_cdn_url(sheet_a.pdf_gcs_uri)
  assert pdf_url in html
  assert cloud_storage.get_public_cdn_url(sheet_b.pdf_gcs_uri) not in html
  assert "/printables/notes/free-cats-jokes-1" in html
  assert "/printables/notes/free-dogs-jokes-1" in html
  assert "/printables/notes/free-space-jokes-1" in html


def test_notes_detail_redirects_locked_pack_when_logged_out(monkeypatch):
  category_id = "animals"
  slug = "free-animals-jokes-2"
  category = models.JokeCategory(display_name="Animals",
                                 id=category_id,
                                 state="APPROVED")
  sheets = [
    models.JokeSheet(
      key="a-sheet",
      category_id=category_id,
      index=0,
      image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-a.png",
      pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-a.pdf",
    ),
    models.JokeSheet(
      key="b-sheet",
      category_id=category_id,
      index=1,
      image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-b.png",
      pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-b.pdf",
    ),
  ]
  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: [(category, sheets)])
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get(f"/printables/notes/{slug}")

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/printables/notes')


def test_notes_detail_allows_locked_pack_when_logged_in(monkeypatch):
  category_id = "animals"
  slug = "free-animals-jokes-2"
  category = models.JokeCategory(display_name="Animals",
                                 id=category_id,
                                 state="APPROVED")
  sheets = [
    models.JokeSheet(
      key="a-sheet",
      category_id=category_id,
      index=0,
      image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-a.png",
      pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-a.pdf",
    ),
    models.JokeSheet(
      key="b-sheet",
      category_id=category_id,
      index=1,
      image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-b.png",
      pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-b.pdf",
    ),
  ]
  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: [(category, sheets)])
  monkeypatch.setattr(auth_helpers, "verify_session",
                      lambda _req: ("user-123", {
                        "uid": "user-123"
                      }))

  with app.test_client() as client:
    resp = client.get(f"/printables/notes/{slug}")

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Animals Joke Pack 2" in html
  assert "Download Free PDF" in html
  assert "You Might Also Like" in html
  assert "Other Animals Joke Packs" in html
  assert "/printables/notes/free-animals-jokes-1" in html
  assert "sendSignInLinkToEmail" not in html


def test_notes_detail_redirects_on_invalid_slug():
  with app.test_client() as client:
    resp = client.get('/printables/notes/not-a-slug')

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/printables/notes')


def test_notes_redirects_authenticated_user(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session",
                      lambda _req: ("user-123", {
                        "uid": "user-123"
                      }))

  with app.test_client() as client:
    resp = client.get('/printables/notes')

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/printables/notes/all')


def test_notes_all_redirects_logged_out_user(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req: None)

  with app.test_client() as client:
    resp = client.get('/printables/notes/all')

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/printables/notes')


def test_notes_all_renders_categories_and_sheets(monkeypatch):
  monkeypatch.setattr(auth_helpers, "verify_session",
                      lambda _req: ("user-123", {
                        "uid": "user-123"
                      }))

  animals = models.JokeCategory(display_name="Animals",
                                id="animals",
                                state="APPROVED")
  breezy = models.JokeCategory(display_name="Breezy",
                               id="breezy",
                               state="SEASONAL")
  zany = models.JokeCategory(display_name="Zany", id="zany", state="APPROVED")
  cache_entries = [
    (zany, [
      models.JokeSheet(
        key="zany-low",
        category_id="zany",
        index=0,
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/zany-low.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/zany-low.pdf",
      ),
      models.JokeSheet(
        key="zany-high",
        category_id="zany",
        index=1,
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/zany-high.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/zany-high.pdf",
      ),
    ]),
    (animals, [
      models.JokeSheet(
        key="animals-low",
        category_id="animals",
        index=0,
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-low.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-low.pdf",
      ),
      models.JokeSheet(
        key="animals-high",
        category_id="animals",
        index=1,
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/animals-high.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/animals-high.pdf",
      ),
    ]),
    (breezy, [
      models.JokeSheet(
        key="breezy-low",
        category_id="breezy",
        index=0,
        image_gcs_uri="gs://image-bucket/joke_notes_sheets/breezy-low.png",
        pdf_gcs_uri="gs://pdf-bucket/joke_notes_sheets/breezy-low.pdf",
      ),
    ]),
  ]
  monkeypatch.setattr(notes_routes.firestore, "get_joke_sheets_cache",
                      lambda: cache_entries)

  with app.test_client() as client:
    resp = client.get('/printables/notes/all')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  animals_pos = html.find('notes-download-animals-title')
  breezy_pos = html.find('notes-download-breezy-title')
  zany_pos = html.find('notes-download-zany-title')
  assert animals_pos != -1
  assert breezy_pos != -1
  assert zany_pos != -1
  assert animals_pos < breezy_pos < zany_pos

  animals_low_detail = "/printables/notes/free-animals-jokes-1"
  animals_high_detail = "/printables/notes/free-animals-jokes-2"
  assert html.find(animals_low_detail) < html.find(animals_high_detail)
  assert "/printables/notes/free-animals-jokes-3" not in html

  zany_low_detail = "/printables/notes/free-zany-jokes-1"
  zany_high_detail = "/printables/notes/free-zany-jokes-2"
  assert html.find(zany_low_detail) < html.find(zany_high_detail)
  assert html.count("View Pack") == 5
  assert html.count(
    'data-analytics-event="web_notes_view_pack_click"') == 5
