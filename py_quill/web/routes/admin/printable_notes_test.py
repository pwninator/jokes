"""Tests for admin printable notes routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from functions import auth_helpers
from PIL import Image
from services import cloud_storage, firestore
from web.app import app
from web.routes.admin import printable_notes as printable_notes_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_printable_notes_page_loads(monkeypatch):
  """Test the printable notes page loads and renders."""
  _mock_admin_session(monkeypatch)

  # Mock get_joke_sheets_cache
  mock_category = Mock()
  mock_category.id = "animals"
  mock_category.display_name = "Animals"

  mock_sheet = Mock()
  mock_sheet.key = "sheet1"
  mock_sheet.image_gcs_uri = "gs://bucket/sheet1.png"
  mock_sheet.index = 0
  mock_sheet.display_index = 1

  mock_cache = [(mock_category, [mock_sheet])]
  monkeypatch.setattr(
    printable_notes_routes,
    "_get_joke_sheets_cache",
    lambda: mock_cache,
  )

  # Mock Firestore operations
  mock_sheet_doc = Mock()
  mock_sheet_doc.exists = True
  mock_sheet_doc.to_dict.return_value = {
    "joke_ids": ["joke1", "joke2"],
  }

  mock_db = Mock()
  mock_collection = Mock()
  mock_document = Mock()
  mock_document.get.return_value = mock_sheet_doc
  mock_collection.document.return_value = mock_document
  mock_db.collection.return_value = mock_collection
  monkeypatch.setattr(firestore, "db", lambda: mock_db)

  # Mock get_joke_category
  mock_full_category = Mock()
  mock_full_category.image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/category.png"
  monkeypatch.setattr(firestore, "get_joke_category",
                      lambda _: mock_full_category)

  # Mock get_punny_jokes
  mock_joke1 = Mock()
  mock_joke1.key = "joke1"
  mock_joke1.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_setup.png"
  mock_joke1.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_punchline.png"

  mock_joke2 = Mock()
  mock_joke2.key = "joke2"
  mock_joke2.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke2_setup.png"
  mock_joke2.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke2_punchline.png"

  monkeypatch.setattr(
    firestore,
    "get_punny_jokes",
    lambda _: [mock_joke1, mock_joke2],
  )

  # Mock cloud_storage functions
  monkeypatch.setattr(
    cloud_storage,
    "get_public_image_cdn_url",
    lambda uri, **kwargs:
    f"https://images.quillsstorybook.com/cdn-cgi/image/{uri}",
  )

  with app.test_client() as client:
    resp = client.get('/admin/printable-notes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Printable Notes" in html
  assert "Animals" in html


def test_admin_create_pin_image_success(monkeypatch):
  """Test creating a pin image successfully."""
  _mock_admin_session(monkeypatch)

  joke_ids = ["joke1", "joke2"]

  # Mock create_pinterest_pin_image
  mock_pin_image = Image.new('RGB', (1000, 1000), color='white')
  monkeypatch.setattr(
    printable_notes_routes.image_operations,
    "create_pinterest_pin_image",
    lambda *, joke_ids: mock_pin_image,
  )

  # Mock cloud_storage functions
  mock_gcs_uri = "gs://temp-bucket/pin_123.png"
  monkeypatch.setattr(
    cloud_storage,
    "get_gcs_uri",
    lambda bucket, base, ext: mock_gcs_uri,
  )
  monkeypatch.setattr(
    cloud_storage,
    "upload_bytes_to_gcs",
    lambda bytes, uri, content_type: uri,
  )
  monkeypatch.setattr(
    cloud_storage,
    "get_public_cdn_url",
    lambda uri: f"http://temp-bucket/pin_123.png",
  )

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={'joke_ids': joke_ids},
      content_type='application/json',
    )

  assert resp.status_code == 200
  data = resp.get_json()
  assert 'pin_url' in data
  assert data['pin_url'] == "http://temp-bucket/pin_123.png"


def test_admin_create_pin_image_missing_joke_ids(monkeypatch):
  """Test creating a pin image with missing joke_ids."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={},
      content_type='application/json',
    )

  assert resp.status_code == 400
  data = resp.get_json()
  assert 'error' in data
  assert 'joke_ids' in data['error']


def test_admin_create_pin_image_invalid_joke_ids(monkeypatch):
  """Test creating a pin image with invalid joke_ids."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={'joke_ids': 'not-a-list'},
      content_type='application/json',
    )

  assert resp.status_code == 400
  data = resp.get_json()
  assert 'error' in data


def test_admin_create_pin_image_too_many_joke_ids(monkeypatch):
  """Test creating a pin image with too many joke_ids."""
  _mock_admin_session(monkeypatch)

  joke_ids = ["j1", "j2", "j3", "j4", "j5", "j6"]

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={'joke_ids': joke_ids},
      content_type='application/json',
    )

  assert resp.status_code == 400
  data = resp.get_json()
  assert 'error' in data


def test_admin_create_pin_image_value_error(monkeypatch):
  """Test creating a pin image when ValueError is raised."""
  _mock_admin_session(monkeypatch)

  joke_ids = ["joke1"]

  # Mock create_pinterest_pin_image to raise ValueError
  monkeypatch.setattr(
    printable_notes_routes.image_operations,
    "create_pinterest_pin_image",
    lambda *, joke_ids:
    (_ for _ in ()).throw(ValueError(
      "Joke joke1 is missing setup or punchline image")),
  )

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={'joke_ids': joke_ids},
      content_type='application/json',
    )

  assert resp.status_code == 400
  data = resp.get_json()
  assert 'error' in data
  assert 'missing setup or punchline image' in data['error']


def test_admin_create_pin_image_unexpected_error(monkeypatch):
  """Test creating a pin image when an unexpected error occurs."""
  _mock_admin_session(monkeypatch)

  joke_ids = ["joke1"]

  # Mock create_pinterest_pin_image to raise unexpected error
  monkeypatch.setattr(
    printable_notes_routes.image_operations,
    "create_pinterest_pin_image",
    lambda *, joke_ids: (_ for _ in ()).throw(Exception("Unexpected error")),
  )

  with app.test_client() as client:
    resp = client.post(
      '/admin/create-pin',
      json={'joke_ids': joke_ids},
      content_type='application/json',
    )

  assert resp.status_code == 500
  data = resp.get_json()
  assert 'error' in data
  assert 'Failed to create pin image' in data['error']
