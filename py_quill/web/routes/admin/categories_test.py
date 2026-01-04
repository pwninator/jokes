"""Tests for admin joke category routes."""

from __future__ import annotations

from unittest.mock import Mock

from functions import auth_helpers
from web.app import app
from web.routes.admin import categories as categories_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def test_admin_create_category_calls_refresh(monkeypatch):
  """Creating a category should initialize the category cache."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="animals")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'category_type': 'search',
        'display_name': 'Animals',
        'joke_description_query': 'animals',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/admin/joke-categories?created=1')

  mock_create.assert_called_once()
  _, kwargs = mock_create.call_args
  assert kwargs["display_name"] == "Animals"
  assert kwargs["state"] == "PROPOSED"
  assert kwargs["joke_description_query"] == "animals"
  assert kwargs["seasonal_name"] is None

  mock_refresh.assert_called_once()
  args, _ = mock_refresh.call_args
  assert args[0] == "animals"
  assert args[1]["state"] == "PROPOSED"
  assert args[1]["joke_description_query"] == "animals"
  assert args[1]["seasonal_name"] == ""


def test_admin_create_seasonal_category(monkeypatch):
  """Seasonal category creation should not require a search query."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="christmas")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)
  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'category_type': 'seasonal',
        'display_name': 'Christmas',
        'seasonal_name': 'Christmas',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/admin/joke-categories?created=1')

  _, kwargs = mock_create.call_args
  assert kwargs["display_name"] == "Christmas"
  assert kwargs["joke_description_query"] is None
  assert kwargs["seasonal_name"] == "Christmas"

  args, _ = mock_refresh.call_args
  assert args[0] == "christmas"
  assert args[1]["joke_description_query"] == ""
  assert args[1]["seasonal_name"] == "Christmas"


def test_admin_create_category_validates_required_fields(monkeypatch):
  """Missing inputs should redirect with an error code."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'category_type': 'search',
        'display_name': '',
        'joke_description_query': 'dogs',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith(
    '/admin/joke-categories?error=display_name_required')


def test_admin_update_category_sets_fields_and_refreshes_cache(monkeypatch):
  """Updating a category writes fields and refreshes the cached jokes."""
  _mock_admin_session(monkeypatch)

  mock_db = Mock()
  mock_doc = Mock()
  mock_collection = Mock()
  mock_collection.document.return_value = mock_doc
  mock_db.collection.return_value = mock_collection
  monkeypatch.setattr(categories_routes.firestore, "db", lambda: mock_db)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/animals/update',
      data={
        'display_name': 'Animals',
        'state': 'APPROVED',
        'category_type': 'search',
        'joke_description_query': 'animals',
        'seasonal_name': '',
        'image_url': 'https://cdn/cat.png',
        'image_description': 'Cute animals',
        'all_image_urls': 'https://a.png\nhttps://b.png\n',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith(
    '/admin/joke-categories?updated=animals')

  mock_db.collection.assert_called_with('joke_categories')
  mock_collection.document.assert_called_with('animals')
  mock_doc.set.assert_called_once()
  _, kwargs = mock_doc.set.call_args
  assert kwargs["merge"] is True

  args, _ = mock_refresh.call_args
  assert args[0] == 'animals'
  assert args[1]['state'] == 'APPROVED'
  assert args[1]['joke_description_query'] == 'animals'
  assert args[1]['seasonal_name'] == ''
