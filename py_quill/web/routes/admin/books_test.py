"""Tests for admin joke book routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

from google.cloud.firestore import ArrayUnion
from PIL import Image

from functions import auth_helpers
from services import firestore as firestore_service
from web.app import app
from web.routes.admin import admin_books as books_routes


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


def _make_image_bytes(format_name: str) -> bytes:
  image = Image.new('RGB', (2, 2), (255, 0, 0))
  buffer = BytesIO()
  image.save(buffer, format=format_name)
  return buffer.getvalue()


class _FakeSnapshot:

  def __init__(self, doc_id: str, data: dict | None, exists: bool = True):
    self.id = doc_id
    self._data = data
    self.exists = exists

  def to_dict(self):
    return self._data


class _FakeDocumentRef:

  def __init__(self,
               snapshot: _FakeSnapshot,
               subcollections: dict[str, "_FakeCollection"] | None = None):
    self._snapshot = snapshot
    self._subcollections = subcollections or {}

  def get(self):
    return self._snapshot

  def collection(self, name: str):
    return self._subcollections.get(name, _FakeCollection({}))


class _FakeCollection:

  def __init__(self, docs: dict[str, _FakeDocumentRef]):
    self._docs = docs

  def stream(self):
    return [doc.get() for doc in self._docs.values()]

  def document(self, doc_id: str):
    return self._docs.get(
      doc_id, _FakeDocumentRef(_FakeSnapshot(doc_id, None, exists=False)))


class _FakeFirestore:

  def __init__(self, books: dict[str, _FakeDocumentRef],
               jokes: dict[str, _FakeDocumentRef]):
    self._books = books
    self._jokes = jokes

  def collection(self, name: str):
    if name == "joke_books":
      return _FakeCollection(self._books)
    if name == "jokes":
      return _FakeCollection(self._jokes)
    return _FakeCollection({})


def test_admin_joke_books_links_to_detail(monkeypatch):
  """Admin list page links to the detail view."""
  _mock_admin_session(monkeypatch)
  book_doc = _FakeSnapshot("book-1", {
    "book_name": "Pirate Jokes",
    "jokes": ["joke-a", "joke-b"],
  })
  books = {"book-1": _FakeDocumentRef(book_doc)}
  fake_db = _FakeFirestore(books=books, jokes={})
  monkeypatch.setattr(firestore_service, "db", lambda: fake_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-books')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<a href="/admin/joke-books/book-1">' in html
  assert "Pirate Jokes" in html


def test_admin_joke_book_detail_renders_images_and_placeholders(monkeypatch):
  """Detail view shows 800px images and placeholders when missing."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(books_routes.utils, "is_emulator", lambda: False)

  setup_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=1024,format=auto,quality=75/path/setup.png")
  punchline_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
                   "width=1024,format=auto,quality=75/path/punchline.png")

  metadata_doc_one = _FakeDocumentRef(
    _FakeSnapshot(
      "metadata", {
        "book_page_setup_image_url":
        setup_url,
        "book_page_punchline_image_url":
        punchline_url,
        "book_page_ready":
        True,
        "all_book_page_setup_image_urls":
        [setup_url, "https://cdn/setup2.png"],
        "all_book_page_punchline_image_urls":
        [punchline_url, "https://cdn/punch2.png"],
      }))
  joke_one = _FakeDocumentRef(
    _FakeSnapshot(
      "joke-1", {
        "setup_text": "Setup one",
        "punchline_text": "Punch one",
        "generation_metadata": {
          "total_cost": 0.1234,
        },
      }), {"metadata": _FakeCollection({"metadata": metadata_doc_one})})

  metadata_doc_two = _FakeDocumentRef(_FakeSnapshot("metadata", {}))
  joke_two = _FakeDocumentRef(
    _FakeSnapshot(
      "joke-2", {
        "setup_text": "Setup two",
        "punchline_text": "Punch two",
        "generation_metadata": {
          "generations": [{
            "model_name": "gpt",
            "cost": 0.05
          }]
        },
      }), {"metadata": _FakeCollection({"metadata": metadata_doc_two})})

  books = {
    "book-42":
    _FakeDocumentRef(
      _FakeSnapshot(
        "book-42", {
          "book_name": "Space Llamas",
          "jokes": ["joke-1", "joke-2"],
          "zip_url": "https://example.com/book.zip",
        }))
  }
  jokes = {"joke-1": joke_one, "joke-2": joke_two}
  fake_db = _FakeFirestore(books=books, jokes=jokes)
  monkeypatch.setattr(firestore_service, "db", lambda: fake_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-books/book-42')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Space Llamas" in html
  assert 'class="book-id">book-42</code>' in html
  assert "joke-1" in html and "joke-2" in html
  assert 'width="800"' in html and 'height="800"' in html
  assert "width=800" in html  # width parameter in formatted CDN URL
  assert "format=png,quality=100/path/setup.png" in html
  assert "format=png,quality=100/path/punchline.png" in html
  assert "width=1024" not in html
  assert "No punchline image" in html
  assert "Download all pages" in html
  assert "Set as main joke image" in html
  assert "https://generate-joke-book-page-uqdkqas7gq-uc.a.run.app" in html
  assert "$0.1234" in html
  assert "$0.0500" in html
  assert "$0.1734" in html
  assert 'joke-edit-button' in html
  assert 'data-joke-data=' in html
  assert '--joke-card-max-width: 200px;' in html
  assert 'class="variant-tile"' in html
  assert "book_page_setup_image_url" in html
  assert "book_page_punchline_image_url" in html
  assert 'book-page-filter-toggle' in html
  assert 'data-book-page-ready="true"' in html
  assert 'data-book-page-ready="false"' in html
  assert 'aria-pressed="true"' in html
  assert 'aria-pressed="false"' in html
  assert "/admin/joke-books/update-page" in html
  assert "/admin/joke-books/set-main-image" in html


def test_admin_joke_book_refresh_includes_download_urls(monkeypatch):
  """Refresh endpoint returns download-ready CDN URLs."""
  _mock_admin_session(monkeypatch)

  setup_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=900,format=auto,quality=80/path/setup.png")
  metadata_doc = _FakeDocumentRef(
    _FakeSnapshot("metadata", {
      "book_page_setup_image_url": setup_url,
    }))
  joke = _FakeDocumentRef(
    _FakeSnapshot("joke-5", {"generation_metadata": {
      "total_cost": 0.2
    }}), {"metadata": _FakeCollection({"metadata": metadata_doc})})

  fake_db = _FakeFirestore(books={}, jokes={"joke-5": joke})
  monkeypatch.setattr(firestore_service, "db", lambda: fake_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-books/book-abc/jokes/joke-5/refresh')

  assert resp.status_code == 200
  data = resp.get_json()
  assert data["setup_image_download"].startswith(
    "https://images.quillsstorybook.com/cdn-cgi/image/")
  assert "format=png,quality=100/path/setup.png" in data[
    "setup_image_download"]
  assert "width=" not in data["setup_image_download"]
  assert data["punchline_image_download"] is None


def test_admin_joke_book_detail_uses_emulator_url_when_applicable(monkeypatch):
  """Detail view uses emulator Cloud Function URL when running locally."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(books_routes.utils, "is_emulator", lambda: True)

  books = {
    "book-local":
    _FakeDocumentRef(
      _FakeSnapshot("book-local", {
        "book_name": "Local Book",
        "jokes": ["joke-123"],
      }))
  }
  metadata_doc = _FakeDocumentRef(_FakeSnapshot("metadata", {}))
  joke = _FakeDocumentRef(
    _FakeSnapshot(
      "joke-123", {
        "setup_text": "Setup local",
        "punchline_text": "Punch local",
        "generation_metadata": {
          "total_cost": 1.0
        },
      }), {"metadata": _FakeCollection({"metadata": metadata_doc})})
  fake_db = _FakeFirestore(books=books, jokes={"joke-123": joke})
  monkeypatch.setattr(firestore_service, "db", lambda: fake_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-books/book-local')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "http://127.0.0.1:5001/storyteller-450807/us-central1/generate_joke_book_page" in html
  assert "$1.0000" in html


def test_admin_routes_allow_emulator_without_auth(monkeypatch):
  """When in emulator mode, admin routes bypass auth checks."""
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

  def _fail(_req):
    raise AssertionError("verify_session should not be called in emulator")

  monkeypatch.setattr(auth_helpers, "verify_session", _fail)
  fake_db = _FakeFirestore(books={}, jokes={})
  monkeypatch.setattr(firestore_service, "db", lambda: fake_db)

  with app.test_client() as client:
    resp = client.get('/admin/joke-books')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Joke Books" in html
  assert "No joke books found." in html


def test_admin_joke_book_upload_image_book_page(monkeypatch):
  """Test uploading a book page image updates metadata and variants."""
  _mock_admin_session(monkeypatch)

  mock_upload = Mock()
  monkeypatch.setattr(books_routes.cloud_storage, "upload_bytes_to_gcs",
                      mock_upload)

  mock_get_cdn = Mock(return_value="https://cdn/image.png")
  monkeypatch.setattr(books_routes.cloud_storage, "get_public_image_cdn_url",
                      mock_get_cdn)

  # Mock Firestore
  mock_metadata_ref = Mock()
  mock_metadata_ref.get.return_value = Mock(exists=True)

  mock_joke_ref = Mock()
  mock_joke_ref.collection.return_value.document.return_value = mock_metadata_ref

  mock_db = Mock()
  mock_db.collection.return_value.document.return_value = mock_joke_ref
  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  image_bytes = _make_image_bytes('JPEG')
  data = {
    'joke_id': 'joke-123',
    'joke_book_id': 'book-456',
    'target_field': 'book_page_setup_image_url',
    'file': (BytesIO(image_bytes), 'test.jpg'),
  }

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/upload-image',
                       data=data,
                       content_type='multipart/form-data')

  assert resp.status_code == 200
  assert resp.json['url'] == "https://cdn/image.png"

  # Verify Upload
  mock_upload.assert_called_once()
  args = mock_upload.call_args[0]
  uploaded_image = Image.open(BytesIO(args[0]))
  assert uploaded_image.format == 'PNG'
  assert "joke_books/book-456/joke-123/custom_setup_" in args[1]
  assert args[1].endswith(".png")
  assert args[2] == "image/png"

  # Verify Firestore Update
  mock_metadata_ref.update.assert_called_once()
  update_args = mock_metadata_ref.update.call_args[0][0]
  assert update_args['book_page_setup_image_url'] == "https://cdn/image.png"
  assert 'all_book_page_setup_image_urls' in update_args


def test_admin_joke_book_upload_image_main_joke(monkeypatch):
  """Test uploading a main joke image updates the joke doc."""
  _mock_admin_session(monkeypatch)

  mock_upload = Mock()
  monkeypatch.setattr(books_routes.cloud_storage, "upload_bytes_to_gcs",
                      mock_upload)

  mock_get_cdn = Mock(return_value="https://cdn/main-image.png")
  monkeypatch.setattr(books_routes.cloud_storage, "get_public_image_cdn_url",
                      mock_get_cdn)

  # Mock Firestore
  mock_joke_ref = Mock()
  mock_db = Mock()
  mock_db.collection.return_value.document.return_value = mock_joke_ref
  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  data = {
    'joke_id': 'joke-999',
    'target_field': 'punchline_image_url',
    'file': (BytesIO(_make_image_bytes('GIF')), 'punch.gif'),
  }

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/upload-image',
                       data=data,
                       content_type='multipart/form-data')

  assert resp.status_code == 200

  # Verify Upload
  mock_upload.assert_called_once()
  args = mock_upload.call_args[0]
  uploaded_image = Image.open(BytesIO(args[0]))
  assert uploaded_image.format == 'PNG'
  assert "jokes/joke-999/custom_punchline_" in args[1]
  assert args[1].endswith(".png")
  assert args[2] == "image/png"

  # Verify Firestore Update on Main Doc
  mock_joke_ref.update.assert_called_once_with(
    {'punchline_image_url': "https://cdn/main-image.png"})


def test_admin_joke_book_upload_invalid_input(monkeypatch):
  """Test invalid inputs return 400."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    # Missing file
    resp = client.post('/admin/joke-books/upload-image',
                       data={
                         'joke_id': '1',
                         'target_field': 'setup_image_url'
                       },
                       content_type='multipart/form-data')
    assert resp.status_code == 400
    assert b"Missing required fields" in resp.data

    # Invalid field
    resp = client.post('/admin/joke-books/upload-image',
                       data={
                         'joke_id': '1',
                         'target_field': 'hacker_field',
                         'file': (BytesIO(b""), 'test.png')
                       },
                       content_type='multipart/form-data')
    assert resp.status_code == 400
    assert b"Invalid target field" in resp.data

    # Invalid image file
    resp = client.post('/admin/joke-books/upload-image',
                       data={
                         'joke_id': '1',
                         'target_field': 'setup_image_url',
                         'file': (BytesIO(b"not an image"), 'test.txt')
                       },
                       content_type='multipart/form-data')
    assert resp.status_code == 400
    assert b"Invalid image file" in resp.data


def test_admin_update_joke_book_page_updates_metadata(monkeypatch):
  """Selecting a variant updates metadata with normalized history."""
  _mock_admin_session(monkeypatch)

  existing_meta = {
    'book_page_setup_image_url': 'https://old/setup.png',
    'book_page_punchline_image_url': 'https://old/punch.png',
  }
  metadata_doc = Mock()
  metadata_doc.exists = True
  metadata_doc.to_dict.return_value = existing_meta
  metadata_ref = Mock()
  metadata_ref.get.return_value = metadata_doc

  joke_ref = Mock()
  joke_ref.collection.return_value.document.return_value = metadata_ref

  book_doc = Mock()
  book_doc.exists = True
  book_doc.to_dict.return_value = {'jokes': ['joke-1']}
  book_ref = Mock()
  book_ref.get.return_value = book_doc

  joke_books_collection = Mock()
  joke_books_collection.document.return_value = book_ref
  jokes_collection = Mock()
  jokes_collection.document.return_value = joke_ref

  mock_db = Mock()

  def _collection(name):
    if name == 'joke_books':
      return joke_books_collection
    if name == 'jokes':
      return jokes_collection
    return Mock()

  mock_db.collection.side_effect = _collection
  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  updates = {
    'book_page_setup_image_url': 'https://cdn/new.png',
    'book_page_punchline_image_url': 'https://old/punch.png',
    'all_book_page_setup_image_urls': ['https://cdn/new.png'],
    'all_book_page_punchline_image_urls': ['https://old/punch.png'],
  }
  mock_prepare = Mock(return_value=updates)
  monkeypatch.setattr(books_routes.models.PunnyJoke,
                      "prepare_book_page_metadata_updates", mock_prepare)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/update-page',
                       data={
                         'joke_book_id': 'book-1',
                         'joke_id': 'joke-1',
                         'new_book_page_setup_image_url':
                         'https://cdn/new.png',
                       })

  assert resp.status_code == 200
  mock_prepare.assert_called_once_with(existing_meta, 'https://cdn/new.png',
                                       'https://old/punch.png')
  metadata_ref.set.assert_called_once_with(updates, merge=True)
  assert resp.json['book_page_setup_image_url'] == 'https://cdn/new.png'


def test_admin_update_joke_book_page_requires_new_url(monkeypatch):
  """Validation should fail when no new page URL is provided."""
  _mock_admin_session(monkeypatch)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/update-page',
                       data={
                         'joke_book_id': 'book-1',
                         'joke_id': 'joke-1',
                       })

  assert resp.status_code == 400
  assert b"Provide new_book_page_setup_image_url" in resp.data


def test_admin_set_main_image_from_book_page(monkeypatch):
  """Promoting a book page image updates the main joke document."""
  _mock_admin_session(monkeypatch)

  metadata_doc = Mock()
  metadata_doc.exists = True
  metadata_doc.to_dict.return_value = {
    'book_page_setup_image_url': 'https://cdn/book-setup.png',
    'book_page_punchline_image_url': 'https://cdn/book-punch.png',
  }
  metadata_ref = Mock()
  metadata_ref.get.return_value = metadata_doc

  joke_ref = Mock()
  joke_ref.collection.return_value.document.return_value = metadata_ref

  book_doc = Mock()
  book_doc.exists = True
  book_doc.to_dict.return_value = {'jokes': ['joke-77']}
  book_ref = Mock()
  book_ref.get.return_value = book_doc

  def _collection(name):
    collection = Mock()
    if name == 'joke_books':
      collection.document.return_value = book_ref
    elif name == 'jokes':
      collection.document.return_value = joke_ref
    return collection

  mock_db = Mock()
  mock_db.collection.side_effect = _collection
  monkeypatch.setattr(firestore_service, "db", lambda: mock_db)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/set-main-image',
                       data={
                         'joke_book_id': 'book-abc',
                         'joke_id': 'joke-77',
                         'target': 'setup',
                       })

  assert resp.status_code == 200
  update_args = joke_ref.update.call_args[0][0]
  assert update_args['setup_image_url'] == "https://cdn/book-setup.png"
  assert isinstance(update_args['all_setup_image_urls'], ArrayUnion)
  assert update_args['setup_image_url_upscaled'] is None
  assert resp.get_json()['setup_image_url'] == "https://cdn/book-setup.png"
