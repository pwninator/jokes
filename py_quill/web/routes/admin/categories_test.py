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


def _mock_category_doc_stream(monkeypatch, docs):
  """Stub firestore.db() for category collection streaming."""

  class _Collection:

    def __init__(self, stream_docs):
      self._stream_docs = stream_docs

    def stream(self):
      return self._stream_docs

    def document(self, _doc_id):
      return Mock()

  class _Db:

    def __init__(self, stream_docs):
      self._stream_docs = stream_docs

    def collection(self, _name):
      return _Collection(self._stream_docs)

  monkeypatch.setattr(categories_routes.firestore, "db", lambda: _Db(docs))


def test_admin_create_category_calls_refresh(monkeypatch):
  """Creating a category should initialize the category cache."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="animals")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)
  mock_rebuild = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "rebuild_joke_categories_index", mock_rebuild)

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
  mock_rebuild.assert_called_once()


def test_admin_create_seasonal_category(monkeypatch):
  """Seasonal category creation should not require a search query."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="christmas")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)
  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)
  mock_rebuild = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "rebuild_joke_categories_index", mock_rebuild)

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
  mock_rebuild.assert_called_once()


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
  mock_rebuild = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "rebuild_joke_categories_index", mock_rebuild)

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
  mock_rebuild.assert_called_once()


def test_admin_create_category_allows_book_id_only(monkeypatch):
  """Book ID-only category creation should be allowed and initialize the cache."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="book_cat")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)
  mock_rebuild = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "rebuild_joke_categories_index", mock_rebuild)

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
  mock_rebuild.assert_called_once()


def test_admin_create_category_with_negative_tags(monkeypatch):
  """Creating a category with negative tags should parse and pass them."""
  _mock_admin_session(monkeypatch)

  mock_create = Mock(return_value="clean_food")
  monkeypatch.setattr(categories_routes.firestore, "create_joke_category",
                      mock_create)

  mock_refresh = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "refresh_single_category_cache", mock_refresh)
  mock_rebuild = Mock()
  monkeypatch.setattr(categories_routes.joke_category_operations,
                      "rebuild_joke_categories_index", mock_rebuild)

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
  mock_rebuild.assert_called_once()


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
                      lambda **_kwargs: [approved_category])
  monkeypatch.setattr(categories_routes.firestore,
                      "get_uncategorized_public_jokes",
                      lambda _cats: [uncategorized_joke])
  _mock_category_doc_stream(monkeypatch, [])

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


def test_admin_joke_categories_renders_lunchbox_pdf_link(monkeypatch):
  """The category page should show a lunchbox PDF link from the live doc."""
  _mock_admin_session(monkeypatch)

  category = models.JokeCategory(
    id="animals",
    display_name="Animals",
    joke_description_query="animals",
    state="APPROVED",
  )
  monkeypatch.setattr(categories_routes.firestore, "get_all_joke_categories",
                      lambda **_kwargs: [category])
  monkeypatch.setattr(categories_routes.firestore,
                      "get_uncategorized_public_jokes", lambda _cats: [])
  monkeypatch.setattr(categories_routes.utils, "joke_creation_big_url",
                      lambda: "https://bigapi.example.com")
  monkeypatch.setattr(
    categories_routes.cloud_storage, "get_public_cdn_url",
    lambda gcs_uri: f"https://cdn.example/{gcs_uri.split('/')[-1]}")

  live_doc = Mock()
  live_doc.exists = True
  live_doc.id = "animals"
  live_doc.to_dict.return_value = {
    "lunchbox_notes_branded_pdf_gcs_uri": "gs://bucket/animals_branded.pdf",
    "lunchbox_notes_unbranded_pdf_gcs_uri":
    "gs://bucket/animals_unbranded.pdf",
  }
  _mock_category_doc_stream(monkeypatch, [live_doc])

  with app.test_client() as client:
    resp = client.get('/admin/joke-categories')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Generate lunchbox notes" in html
  assert 'href="https://cdn.example/animals_branded.pdf"' in html
  assert 'href="https://cdn.example/animals_unbranded.pdf"' in html
  assert '"https://bigapi.example.com"' in html
  assert "lunchbox_note" in html


def test_admin_get_joke_category_live_returns_live_fields(monkeypatch):
  """Live endpoint should return full edit-form fields from the category doc."""
  _mock_admin_session(monkeypatch)

  mock_doc = Mock()
  mock_doc.exists = True
  mock_doc.to_dict.return_value = {
    "display_name": "Animals",
    "state": "APPROVED",
    "joke_description_query": "animals",
    "search_distance": 0.33,
    "seasonal_name": "Winter",
    "book_id": "book-123",
    "tags": ["cats", "dogs"],
    "negative_tags": ["nsfw"],
    "image_url": "https://cdn/cat.png",
    "image_description": "Cute animals",
    "joke_id_order": ["joke-1", "joke-2"],
  }

  mock_document = Mock()
  mock_document.get.return_value = mock_doc

  mock_collection = Mock()
  mock_collection.document.return_value = mock_document

  mock_db = Mock()
  mock_db.collection.return_value = mock_collection
  monkeypatch.setattr(categories_routes.firestore, "db", lambda: mock_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-categories/animals/live')

  assert resp.status_code == 200
  data = resp.get_json()
  assert data["category_id"] == "animals"
  assert data["display_name"] == "Animals"
  assert data["state"] == "APPROVED"
  assert data["joke_description_query"] == "animals"
  assert data["search_distance"] == 0.33
  assert data["seasonal_name"] == "Winter"
  assert data["book_id"] == "book-123"
  assert data["tags"] == ["cats", "dogs"]
  assert data["negative_tags"] == ["nsfw"]
  assert data["image_url"] == "https://cdn/cat.png"
  assert data["image_description"] == "Cute animals"
  assert data["joke_id_order"] == ["joke-1", "joke-2"]
