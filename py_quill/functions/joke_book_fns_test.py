"""Tests for the joke_book_fns module."""
import json
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


@patch('functions.joke_book_fns.joke_books_firestore')
def test_get_joke_book_returns_html(mock_joke_books_firestore):
  """Test that get_joke_book returns a valid HTML page."""
  joke_book_id = "test_book_123"
  mock_joke_books_firestore.get_book_page_spread_urls.return_value = (
    models.JokeBook(
      id=joke_book_id,
      book_name="My Test Joke Book",
      jokes=["joke1", "joke2"],
      zip_url="https://cdn.example.com/book.zip",
      paperback_pdf_url="https://cdn.example.com/book_paperback.pdf",
    ),
    [
      "http://example.com/page_setup1.tif",
      "http://example.com/page_setup2.tif",
    ],
    [
      "http://example.com/page_punchline1.tif",
      "http://example.com/page_punchline2.tif",
    ],
  )

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
  assert 'href="https://cdn.example.com/book_paperback.pdf"' in html_content
  assert '<img src="http://example.com/page_setup1.tif"' in html_content
  assert '<img src="http://example.com/page_punchline1.tif"' in html_content
  assert '<img src="http://example.com/page_setup2.tif"' in html_content
  assert '<img src="http://example.com/page_punchline2.tif"' in html_content


@patch('functions.joke_book_fns.joke_books_firestore')
def test_get_joke_book_errors_when_book_pages_missing(
    mock_joke_books_firestore):
  """get_joke_book should error if any joke is missing book page images."""
  joke_book_id = "test_book_missing_pages"
  mock_joke_books_firestore.get_book_page_spread_urls.side_effect = ValueError(
    'Joke joke1 does not have book page images')

  req = DummyReq(path=f"/joke-book/{joke_book_id}")

  resp = joke_book_fns.get_joke_book(req)

  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 400
  data = json.loads(resp.get_data(as_text=True))
  assert data == {
    "data": {
      "error": "Joke joke1 does not have book page images",
    },
  }


@patch('functions.joke_book_fns.get_user_id', return_value='test-admin')
@patch(
  'functions.joke_book_fns.image_operations.generate_and_populate_book_pages')
@patch('functions.joke_book_fns.joke_books_firestore')
@patch('functions.joke_book_fns.firestore')
def test_create_book_uses_top_jokes_when_joke_ids_missing(
    mock_firestore, mock_joke_books_firestore, mock_generate_pages,
    mock_get_user_id):
  """create_book should use top jokes when joke_ids is not provided."""
  # Arrange
  top_joke1 = MagicMock()
  top_joke1.key = "j1"
  top_joke2 = MagicMock()
  top_joke2.key = "j2"
  mock_firestore.get_top_jokes.return_value = [top_joke1, top_joke2]
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
  created_book = mock_joke_books_firestore.create_joke_book.call_args.args[0]
  assert created_book.id == 'book123'
  assert created_book.book_name == 'My Auto Book'
  assert created_book.jokes == ['j1', 'j2']
  assert created_book.belongs_to_page_gcs_uri is None
  assert created_book.zip_url is None
  assert created_book.paperback_pdf_url is None
  mock_generate_pages.assert_any_call('j1', overwrite=True)
  mock_generate_pages.assert_any_call('j2', overwrite=True)
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200
  data = json.loads(resp.get_data(as_text=True))
  assert data == {"data": {"book_id": "book123"}}


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
  assert updates['book_page_ready'] is False
  assert updates['book_page_setup_image_prompt'] == "setup-final-prompt"
  assert updates['book_page_punchline_image_prompt'] == "punch-final-prompt"


@patch(
  'functions.joke_book_fns.image_operations.export_joke_page_files_for_kdp')
@patch('functions.joke_book_fns.joke_books_firestore')
def test_update_joke_book_files_regenerates_and_updates(
    mock_joke_books_firestore, mock_export_files):
  """update_joke_book_files should regenerate both export files and persist the URLs."""
  book_id = 'book123'
  joke_ids = ['j1', 'j2']

  mock_export_files.return_value = MagicMock(
    zip_url='https://cdn.example.com/new.zip',
    paperback_pdf_url='https://cdn.example.com/new_paperback.pdf',
  )

  mock_joke_books_firestore.get_joke_book.return_value = models.JokeBook(
    id=book_id,
    jokes=joke_ids,
    belongs_to_page_gcs_uri='gs://images/_joke_assets/book/page.png',
  )

  req = DummyReq(
    path='/update_joke_book_files',
    args={'joke_book_id': book_id},
    method='POST',
  )

  resp = joke_book_fns.update_joke_book_files(req)

  mock_export_files.assert_called_once_with(
    mock_joke_books_firestore.get_joke_book.return_value)
  mock_joke_books_firestore.update_joke_book_export_files.assert_called_once_with(
    book_id,
    zip_url='https://cdn.example.com/new.zip',
    paperback_pdf_url='https://cdn.example.com/new_paperback.pdf',
  )
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {
    'data': {
      'book_id': book_id,
      'zip_url': 'https://cdn.example.com/new.zip',
      'paperback_pdf_url': 'https://cdn.example.com/new_paperback.pdf',
    }
  }


@patch('functions.joke_book_fns.joke_books_firestore')
def test_update_joke_book_files_errors_when_no_jokes(
    mock_joke_books_firestore):
  """update_joke_book_files should error if jokes list is empty."""
  book_id = 'book-empty'
  mock_joke_books_firestore.get_joke_book.return_value = models.JokeBook(
    id=book_id,
    jokes=[],
  )

  req = DummyReq(
    path='/update_joke_book_files',
    args={'joke_book_id': book_id},
    method='POST',
  )

  resp = joke_book_fns.update_joke_book_files(req)

  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 400
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {'data': {'error': 'Joke book has no jokes to export'}}


@patch('functions.joke_book_fns.joke_books_firestore')
def test_update_joke_book_files_errors_when_belongs_to_page_missing(
    mock_joke_books_firestore):
  """update_joke_book_files should error if belongs-to page is missing."""
  book_id = 'book-missing-page'
  mock_joke_books_firestore.get_joke_book.return_value = models.JokeBook(
    id=book_id,
    jokes=['j1'],
  )

  req = DummyReq(
    path='/update_joke_book_files',
    args={'joke_book_id': book_id},
    method='POST',
  )

  resp = joke_book_fns.update_joke_book_files(req)

  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 400
  payload = json.loads(resp.get_data(as_text=True))
  assert payload == {
    'data': {
      'error': 'Joke book is missing belongs_to_page_gcs_uri'
    }
  }


@patch(
  'functions.joke_book_fns.image_operations.generate_and_populate_book_pages')
def test_generate_joke_book_page_allows_base_image_source(mock_generate_pages):
  mock_generate_pages.return_value = (MagicMock(url='setup'),
                                      MagicMock(url='punch'))
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
    additional_setup_instructions='',
    additional_punchline_instructions='',
    base_image_source='book_page',
    style_update=False,
    include_image_description=True,
  )
  assert isinstance(resp, https_fn.Response)
  assert resp.status_code == 200
  # Check for HTML content
  html_content = resp.get_data(as_text=True)
  assert "Joke Book Page - j123" in html_content


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
  assert payload == {'data': {'error': 'Invalid base_image_source: invalid'}}
