"""Tests for the joke_book_fns module."""
from unittest.mock import MagicMock, patch

from firebase_functions import https_fn
from functions import joke_book_fns


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
  }

  mock_joke1_snapshot = MagicMock()
  mock_joke1_snapshot.exists = True
  mock_joke1_snapshot.to_dict.return_value = {
    "setup_text": "test_setup1",
    "punchline_text": "test_punchline1",
    "setup_image_url_upscaled": "http://example.com/setup1.png",
    "punchline_image_url_upscaled": "http://example.com/punchline1.png",
  }

  mock_joke2_snapshot = MagicMock()
  mock_joke2_snapshot.exists = True
  mock_joke2_snapshot.to_dict.return_value = {
    "setup_text": "test_setup2",
    "punchline_text": "test_punchline2",
    "setup_image_url_upscaled": "http://example.com/setup2.png",
    "punchline_image_url_upscaled": "http://example.com/punchline2.png",
  }

  def get_doc_ref(doc_id):
    mock_ref = MagicMock()
    if doc_id == joke_book_id:
      mock_ref.get.return_value = mock_book_snapshot
    elif doc_id == "joke1":
      mock_ref.get.return_value = mock_joke1_snapshot
    elif doc_id == "joke2":
      mock_ref.get.return_value = mock_joke2_snapshot
    else:
      mock_not_found = MagicMock()
      mock_not_found.exists = False
      mock_ref.get.return_value = mock_not_found
    return mock_ref

  mock_firestore.db.return_value.collection.return_value.document.side_effect = get_doc_ref

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
  assert '<img src="http://example.com/setup1.png"' in html_content
  assert '<img src="http://example.com/punchline1.png"' in html_content
  assert '<img src="http://example.com/setup2.png"' in html_content
  assert '<img src="http://example.com/punchline2.png"' in html_content
