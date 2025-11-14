"""Tests for the joke_book_fns module."""
from io import BytesIO
from unittest.mock import MagicMock, patch
import zipfile

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
               data=None):
    self.path = path
    self.args = args or {}
    self.method = method
    self.is_json = is_json
    self.json = data or {}
    self.headers = {}

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
@patch('functions.joke_book_fns.image_operations.zip_joke_page_images')
@patch('functions.joke_book_fns.image_operations.create_book_pages')
@patch('functions.joke_book_fns.firestore')
def test_create_book_uses_top_jokes_when_joke_ids_missing(
    mock_firestore, mock_create_pages, mock_zip_pages, mock_get_user_id):
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
    20,
  )
  mock_zip_pages.assert_called_once_with(['j1', 'j2'])
  mock_doc_ref.set.assert_called_once_with({
    'book_name':
    'My Auto Book',
    'jokes': ['j1', 'j2'],
    'zip_url':
    'https://cdn.example.com/book.zip',
  })
  mock_create_pages.assert_any_call('j1', overwrite=True)
  mock_create_pages.assert_any_call('j2', overwrite=True)
  assert resp == {"data": {"book_id": "book123"}}
