"""Tests for the joke_book_fns module."""
import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

from common import models
from firebase_functions import https_fn
from functions import joke_book_fns
from PIL import Image


class DummyReq:
  """Dummy request class for testing."""

  def __init__(self,
               path="",
               args=None,
               method='GET',
               is_json=False,
               data=None,
               headers=None):
    self.path = path
    self.args = args or {}
    self.method = method
    self.is_json = is_json
    self.json = data or {}
    self.headers = headers or {}

  def get_json(self, silent=False):
    """Dummy get_json method."""
    if self.is_json:
      return {"data": self.json}
    if silent:
      return None
    raise TypeError("Request is not JSON")


@patch('functions.joke_book_fns.firestore')
def test_get_joke_book_returns_html(mock_firestore):
  """Test that get_joke_book returns a valid HTML page."""
  # Arrange
  joke_book_id = "test_book_123"

  # Mock Firestore snapshots
  mock_book_snapshot = MagicMock()
  mock_book_snapshot.exists = True
  mock_book_snapshot.to_dict.return_value = {
    "book_name": "My Test Joke Book",
    "jokes": ["joke1", "joke2"],
    "zip_url": "https://cdn.example.com/book.zip",
  }

  mock_joke1_snapshot = MagicMock()
  mock_joke1_snapshot.exists = True
  mock_joke1_snapshot.to_dict.return_value = {
    "setup_text": "test_setup1",
    "punchline_text": "test_punchline1",
    "setup_image_url_upscaled": "http://example.com/setup1-upscaled.png",
    "punchline_image_url_upscaled":
    "http://example.com/punchline1-upscaled.png",
  }

  mock_joke2_snapshot = MagicMock()
  mock_joke2_snapshot.exists = True
  mock_joke2_snapshot.to_dict.return_value = {
    "setup_text": "test_setup2",
    "punchline_text": "test_punchline2",
    "setup_image_url_upscaled": "http://example.com/setup2-upscaled.png",
    "punchline_image_url_upscaled":
    "http://example.com/punchline2-upscaled.png",
  }

  mock_meta1 = MagicMock()
  mock_meta1.exists = True
  mock_meta1.to_dict.return_value = {
    "book_page_setup_image_url": "http://example.com/page_setup1.tif",
    "book_page_punchline_image_url": "http://example.com/page_punchline1.tif",
  }

  mock_meta2 = MagicMock()
  mock_meta2.exists = True
  mock_meta2.to_dict.return_value = {
    "book_page_setup_image_url": "http://example.com/page_setup2.tif",
    "book_page_punchline_image_url": "http://example.com/page_punchline2.tif",
  }

  mock_db = MagicMock()
  mock_firestore.db.return_value = mock_db

  joke_books_collection = MagicMock()
  jokes_collection = MagicMock()

  def collection_side_effect(name):
    if name == "joke_books":
      return joke_books_collection
    if name == "jokes":
      return jokes_collection
    return MagicMock()

  mock_db.collection.side_effect = collection_side_effect

  # joke_books collection
  book_doc_ref = MagicMock()
  book_doc_ref.get.return_value = mock_book_snapshot
  joke_books_collection.document.return_value = book_doc_ref

  # jokes collection with nested metadata subcollection
  def jokes_document_side_effect(doc_id):
    joke_ref = MagicMock()
    if doc_id == "joke1":
      joke_ref.get.return_value = mock_joke1_snapshot
      metadata_collection = MagicMock()
      metadata_doc_ref = MagicMock()
      metadata_doc_ref.get.return_value = mock_meta1
      metadata_collection.document.return_value = metadata_doc_ref
      joke_ref.collection.return_value = metadata_collection
    elif doc_id == "joke2":
      joke_ref.get.return_value = mock_joke2_snapshot
      metadata_collection = MagicMock()
      metadata_doc_ref = MagicMock()
      metadata_doc_ref.get.return_value = mock_meta2
      metadata_collection.document.return_value = metadata_doc_ref
      joke_ref.collection.return_value = metadata_collection
    else:
      joke_not_found = MagicMock()
      joke_not_found.exists = False
      joke_ref.get.return_value = joke_not_found
    return joke_ref

  jokes_collection.document.side_effect = jokes_document_side_effect

  req = DummyReq(path=f"/joke-book/{joke_book_id}")

  # Act
  resp = joke_book_fns.get_joke_book(req)

  # Assert
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200
  assert resp.headers['Content-Type'] == 'text/html'

  html_content = resp.get_data(as_text=True)

  assert "<title>My Test Joke Book</title>" in html_content
  assert '<h1>My Test Joke Book</h1>' in html_content
  # Download link should point to the stored zip_url
  assert 'href="https://cdn.example.com/book.zip"' in html_content
  assert '<img src="http://example.com/page_setup1.tif"' in html_content
  assert '<img src="http://example.com/page_punchline1.tif"' in html_content
  assert '<img src="http://example.com/page_setup2.tif"' in html_content
  assert '<img src="http://example.com/page_punchline2.tif"' in html_content


@patch('functions.joke_book_fns.firestore')
def test_get_joke_book_errors_when_book_pages_missing(mock_firestore):
  """get_joke_book should error if any joke is missing book page images."""
  joke_book_id = "test_book_missing_pages"

  mock_book_snapshot = MagicMock()
  mock_book_snapshot.exists = True
  mock_book_snapshot.to_dict.return_value = {
    "book_name": "Book With Missing Pages",
    "jokes": ["joke1"],
  }

  mock_joke_snapshot = MagicMock()
  mock_joke_snapshot.exists = True
  mock_joke_snapshot.to_dict.return_value = {
    "setup_text": "setup",
    "punchline_text": "punchline",
    "setup_image_url_upscaled": "http://example.com/setup-upscaled.png",
    "punchline_image_url_upscaled":
    "http://example.com/punchline-upscaled.png",
  }

  # Metadata exists but lacks book page URLs
  mock_meta = MagicMock()
  mock_meta.exists = True
  mock_meta.to_dict.return_value = {}

  mock_db = MagicMock()
  mock_firestore.db.return_value = mock_db

  joke_books_collection = MagicMock()
  jokes_collection = MagicMock()

  def collection_side_effect(name):
    if name == "joke_books":
      return joke_books_collection
    if name == "jokes":
      return jokes_collection
    return MagicMock()

  mock_db.collection.side_effect = collection_side_effect

  # joke_books collection
  book_doc_ref = MagicMock()
  book_doc_ref.get.return_value = mock_book_snapshot
  joke_books_collection.document.return_value = book_doc_ref

  # jokes collection with metadata missing book page URLs
  def jokes_document_side_effect(doc_id):
    joke_ref = MagicMock()
    if doc_id == "joke1":
      joke_ref.get.return_value = mock_joke_snapshot
      metadata_collection = MagicMock()
      metadata_doc_ref = MagicMock()
      metadata_doc_ref.get.return_value = mock_meta
      metadata_collection.document.return_value = metadata_doc_ref
      joke_ref.collection.return_value = metadata_collection
    else:
      joke_not_found = MagicMock()
      joke_not_found.exists = False
      joke_ref.get.return_value = joke_not_found
    return joke_ref

  jokes_collection.document.side_effect = jokes_document_side_effect

  req = DummyReq(path=f"/joke-book/{joke_book_id}")

  resp = joke_book_fns.get_joke_book(req)

  assert resp == {
    "data": {
      "error": "Joke joke1 does not have book page images",
    },
  }


@patch('functions.joke_book_fns.get_user_id', return_value='test-admin')
@patch('functions.joke_book_fns.image_operations.zip_joke_page_images_for_kdp')
@patch(
  'functions.joke_book_fns.image_operations.generate_and_populate_book_pages')
@patch('functions.joke_book_fns.firestore')
def test_create_book_uses_top_jokes_when_joke_ids_missing(
    mock_firestore, mock_generate_pages, mock_zip_pages, mock_get_user_id):
  """create_book should use top jokes when joke_ids is not provided."""
  # Arrange
  top_joke1 = MagicMock()
  top_joke1.key = "j1"
  top_joke2 = MagicMock()
  top_joke2.key = "j2"
  mock_firestore.get_top_jokes.return_value = [top_joke1, top_joke2]
  mock_zip_pages.return_value = 'https://cdn.example.com/book.zip'

  mock_collection = MagicMock()
  mock_doc_ref = MagicMock()
  mock_collection.document.return_value = mock_doc_ref
  mock_firestore.db.return_value.collection.return_value = mock_collection

  # Provide a deterministic doc id
  joke_book_fns.utils.create_timestamped_firestore_key = lambda user_id: "book123"

  req = DummyReq(
    path="/create_book",
    args={"book_name": "My Auto Book"},
    method="POST",
  )

  # Act
  resp = joke_book_fns.create_joke_book(req)

  # Assert
  mock_firestore.get_top_jokes.assert_called_once_with(
    'popularity_score_recent',
    joke_book_fns.NUM_TOP_JOKES_FOR_BOOKS,
  )
  mock_zip_pages.assert_called_once_with(['j1', 'j2'])
  mock_doc_ref.set.assert_called_once_with({
    'book_name':
    'My Auto Book',
    'jokes': ['j1', 'j2'],
    'zip_url':
    'https://cdn.example.com/book.zip',
  })
  mock_generate_pages.assert_any_call('j1', overwrite=True)
  mock_generate_pages.assert_any_call('j2', overwrite=True)
  assert resp == {"data": {"book_id": "book123"}}


def test_prepare_book_page_metadata_updates_normalizes_cdn_urls():
  """URLs should be normalized to canonical CDN params and deduped."""
  prefix = ("https://images.quillsstorybook.com/cdn-cgi/image/"
            "width=1024,format=auto,quality=75/")
  thumb_prefix = ("https://images.quillsstorybook.com/cdn-cgi/image/"
                  "width=100,format=png,quality=70/")
  setup_a = f"{prefix}a.png"
  setup_b_thumb = f"{thumb_prefix}b.png"
  setup_b_canonical = f"{prefix}b.png"
  punch_a_thumb = f"{thumb_prefix}p1.png"
  punch_b = f"{prefix}p2.png"
  existing = {
    "book_page_setup_image_url": setup_a,
    "book_page_punchline_image_url": punch_b,
    "all_book_page_setup_image_urls": [setup_a, setup_b_thumb],
    "all_book_page_punchline_image_urls": [punch_a_thumb, punch_b],
  }
  updates = models.PunnyJoke.prepare_book_page_metadata_updates(
    existing,
    setup_b_thumb,
    punch_a_thumb,
    setup_prompt="setup-final-prompt",
    punchline_prompt="punch-final-prompt",
  )

  assert updates['book_page_setup_image_url'] == setup_b_canonical
  assert updates['book_page_punchline_image_url'] == punch_a_thumb.replace(
    thumb_prefix, prefix)
  assert set(
    updates['all_book_page_setup_image_urls']) == {setup_a, setup_b_canonical}
  assert set(updates['all_book_page_punchline_image_urls']) == {
    punch_b, punch_a_thumb.replace(thumb_prefix, prefix)
  }
  assert updates['book_page_setup_image_prompt'] == "setup-final-prompt"
  assert updates['book_page_punchline_image_prompt'] == "punch-final-prompt"


@patch('functions.joke_book_fns.image_operations.zip_joke_page_images_for_kdp')
@patch('functions.joke_book_fns.firestore')
def test_update_joke_book_zip_regenerates_and_updates(mock_firestore,
                                                      mock_zip_joke_pages):
  """update_joke_book_zip should regenerate the zip and persist the URL."""
  book_id = 'book123'
  joke_ids = ['j1', 'j2']

  mock_zip_joke_pages.return_value = 'https://cdn.example.com/new.zip'

  mock_book_snapshot = MagicMock()
  mock_book_snapshot.exists = True
  mock_book_snapshot.to_dict.return_value = {'jokes': joke_ids}

  mock_db = MagicMock()
  joke_books_collection = MagicMock()
  book_doc_ref = MagicMock()
  book_doc_ref.get.return_value = mock_book_snapshot
  joke_books_collection.document.return_value = book_doc_ref

  def collection_side_effect(name):
    if name == 'joke_books':
      return joke_books_collection
    return MagicMock()

  mock_db.collection.side_effect = collection_side_effect
  mock_firestore.db.return_value = mock_db

  req = DummyReq(
    path='/update_joke_book_zip',
    args={'joke_book_id': book_id},
    method='POST',
  )

  resp = joke_book_fns.update_joke_book_zip(req)

  mock_zip_joke_pages.assert_called_once_with(joke_ids)
  book_doc_ref.update.assert_called_once_with(
    {'zip_url': 'https://cdn.example.com/new.zip'})
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {
    'data': {
      'book_id': book_id,
      'zip_url': 'https://cdn.example.com/new.zip',
    }
  }


@patch('functions.joke_book_fns.firestore')
def test_update_joke_book_zip_errors_when_no_jokes(mock_firestore):
  """update_joke_book_zip should error if jokes list is empty."""
  book_id = 'book-empty'

  mock_book_snapshot = MagicMock()
  mock_book_snapshot.exists = True
  mock_book_snapshot.to_dict.return_value = {'jokes': []}

  mock_db = MagicMock()
  joke_books_collection = MagicMock()
  book_doc_ref = MagicMock()
  book_doc_ref.get.return_value = mock_book_snapshot
  joke_books_collection.document.return_value = book_doc_ref

  def collection_side_effect(name):
    if name == 'joke_books':
      return joke_books_collection
    return MagicMock()

  mock_db.collection.side_effect = collection_side_effect
  mock_firestore.db.return_value = mock_db

  req = DummyReq(
    path='/update_joke_book_zip',
    args={'joke_book_id': book_id},
    method='POST',
  )

  resp = joke_book_fns.update_joke_book_zip(req)

  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 400
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {'data': {'error': 'Joke book has no jokes to zip'}}


@patch(
  'functions.joke_book_fns.image_operations.generate_and_populate_book_pages')
def test_generate_joke_book_page_allows_base_image_source(mock_generate_pages):
  mock_generate_pages.return_value = (MagicMock(url='setup'), MagicMock(
    url='punch'))
  req = DummyReq(
    path='/generate_joke_book_page',
    args={
      'joke_id': 'j123',
      'base_image_source': 'book_page',
    },
    method='POST',
  )

  resp = joke_book_fns.generate_joke_book_page(req)

  mock_generate_pages.assert_called_once_with(
    'j123',
    overwrite=True,
    additional_setup_instructions=None,
    additional_punchline_instructions=None,
    base_image_source='book_page',
  )
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200


def test_generate_joke_book_page_rejects_invalid_base_image_source():
  req = DummyReq(
    path='/generate_joke_book_page',
    args={
      'joke_id': 'j123',
      'base_image_source': 'invalid',
    },
    method='POST',
  )

  resp = joke_book_fns.generate_joke_book_page(req)

  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 400
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {
    'data': {
      'error': 'Invalid base_image_source: invalid'
    }
  }
