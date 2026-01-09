"""Tests for admin joke category routes."""

from __future__ import annotations

import html as html_lib
import re
from unittest.mock import Mock

from functions import auth_helpers
from common import models
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
        'display_name': 'Animals',
        'joke_description_query': 'animals',
        'search_distance': '0.25',
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
  assert kwargs["tags"] is None
  assert kwargs["search_distance"] == 0.25

  mock_refresh.assert_called_once()
  args, _ = mock_refresh.call_args
  assert args[0] == "animals"
  assert args[1]["state"] == "PROPOSED"
  assert args[1]["joke_description_query"] == "animals"
  assert args[1]["seasonal_name"] == ""
  assert args[1]["tags"] == []
  assert args[1]["search_distance"] == 0.25


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
  assert kwargs["tags"] is None
  assert kwargs.get("search_distance") is None

  args, _ = mock_refresh.call_args
  assert args[0] == "christmas"
  assert args[1]["joke_description_query"] == ""
  assert args[1]["seasonal_name"] == "Christmas"
  assert args[1]["tags"] == []


def test_admin_create_category_validates_required_fields(monkeypatch):
  """Missing inputs should redirect with an error code."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'display_name': '',
        'joke_description_query': 'dogs',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith(
    '/admin/joke-categories?error=display_name_required')


def test_admin_create_category_allows_tags_only(monkeypatch):
  """Tags-only category creation should be allowed and initialize the cache."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="food")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'display_name': 'Food',
        'tags': 'food, snacks, food',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/admin/joke-categories?created=1')

  _, kwargs = mock_create.call_args
  assert kwargs["display_name"] == "Food"
  assert kwargs["joke_description_query"] is None
  assert kwargs["seasonal_name"] is None
  assert kwargs["tags"] == ["food", "snacks"]
  assert kwargs.get("search_distance") is None

  args, _ = mock_refresh.call_args
  assert args[0] == "food"
  assert args[1]["tags"] == ["food", "snacks"]


def test_admin_create_category_allows_book_id_only(monkeypatch):
  """Book ID-only category creation should be allowed and initialize the cache."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="book_cat")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'display_name': 'Book Category',
        'book_id': 'book-123',
      },
    )

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/admin/joke-categories?created=1')

  _, kwargs = mock_create.call_args
  assert kwargs["display_name"] == "Book Category"
  assert kwargs["joke_description_query"] is None
  assert kwargs["seasonal_name"] is None
  assert kwargs["book_id"] == "book-123"
  assert kwargs["tags"] is None

  args, _ = mock_refresh.call_args
  assert args[0] == "book_cat"
  assert args[1]["book_id"] == "book-123"


def test_admin_create_category_with_negative_tags(monkeypatch):
  """Creating a category with negative tags should parse and pass them."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="clean_food")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)

  with app.test_client() as client:
    resp = client.post(
      '/admin/joke-categories/create',
      data={
        'display_name': 'Clean Food',
        'tags': 'food, healthy',
        'negative_tags': 'junk, oily',
      },
    )

  assert resp.status_code == 302

  _, kwargs = mock_create.call_args
  assert kwargs["tags"] == ["food", "healthy"]
  assert kwargs["negative_tags"] == ["junk", "oily"]

  args, _ = mock_refresh.call_args
  assert args[1]["tags"] == ["food", "healthy"]
  assert args[1]["negative_tags"] == ["junk", "oily"]


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
        'joke_description_query': 'animals',
        'search_distance': '0.30',
        'seasonal_name': '',
        'tags': 'cats, dogs',
        'negative_tags': 'nsfw, politics',
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
  payload, kwargs = mock_doc.set.call_args
  assert payload[0]["negative_tags"] == ["nsfw", "politics"]
  assert kwargs["merge"] is True

  args, _ = mock_refresh.call_args
  assert args[0] == 'animals'
  assert args[1]['state'] == 'APPROVED'
  assert args[1]['joke_description_query'] == 'animals'
  assert args[1]['seasonal_name'] == ''
  assert args[1]['search_distance'] == 0.30
  assert args[1]['tags'] == ['cats', 'dogs']
  assert args[1]['negative_tags'] == ['nsfw', 'politics']


def test_admin_update_category_with_book_id(monkeypatch):
  """Updating a category with book_id should write it and refresh cache."""
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
      '/admin/joke-categories/book_cat/update',
      data={
        'display_name': 'Book Category',
        'state': 'APPROVED',
        'book_id': 'book-456',
        'seasonal_name': '',
        'joke_description_query': '',
        'tags': '',
      },
    )

  assert resp.status_code == 302

  mock_doc.set.assert_called_once()
  payload, kwargs = mock_doc.set.call_args
  assert payload[0]["book_id"] == "book-456"
  assert kwargs["merge"] is True

  args, _ = mock_refresh.call_args
  assert args[0] == 'book_cat'
  assert args[1]['book_id'] == 'book-456'


def test_admin_joke_categories_renders_multiline_tooltip(monkeypatch):
  """The category page should render the joke hover tooltip with exact formatting."""
  _mock_admin_session(monkeypatch)

  approved_joke = models.PunnyJoke(
    key="joke-approved-1",
    setup_text="setup",
    punchline_text="punchline",
    seasonal=None,
    tags=["tag_a", "tag_b"],
  )
  approved_category = models.JokeCategory(
    id="animals",
    display_name="Animals",
    joke_description_query="animals",
    seasonal_name=None,
    state="APPROVED",
    jokes=[approved_joke],
  )

  uncategorized_joke = models.PunnyJoke(
    key="joke-uncat-1",
    setup_text="setup",
    punchline_text="punchline",
    seasonal="Winter",
    tags=["first_tag", "second_tag"],
  )

  monkeypatch.setattr(categories_routes.firestore, "get_all_joke_categories",
                      lambda fetch_cached_jokes: [approved_category])
  monkeypatch.setattr(categories_routes.firestore,
                      "get_uncategorized_public_jokes",
                      lambda _cats: [uncategorized_joke])

  with app.test_client() as client:
    resp = client.get('/admin/joke-categories')

  assert resp.status_code == 200
  html = resp.data.decode("utf-8")

  assert "Approved" in html
  assert "1 unique jokes" in html
  assert "Proposed" in html
  assert "0 unique jokes" in html
  assert "Rejected" in html
  assert "Uncategorized" in html

  def _decoded_title_for(joke_id: str) -> str:
    match = re.search(r'title="([^"]*' + re.escape(joke_id) + r'[^"]*)"', html)
    assert match, f"Missing title attribute for {joke_id}"
    raw = match.group(1)
    decoded = html_lib.unescape(raw)
    decoded = decoded.replace("&#13;", "\r").replace("&#10;", "\n")
    return decoded.replace("\r\n", "\n").replace("\r", "\n")

  assert _decoded_title_for("joke-approved-1") == (
    "joke-approved-1\n\nseasonal: None\n\ntags:\ntag_a\ntag_b")
  assert _decoded_title_for("joke-uncat-1") == (
    "joke-uncat-1\n\nseasonal: Winter\n\ntags:\nfirst_tag\nsecond_tag")
