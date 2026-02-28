"""Tests for admin joke book routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

from PIL import Image

from functions import auth_helpers
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


def test_admin_joke_books_links_to_detail(monkeypatch):
  """Admin list page links to the detail view."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    "list_joke_books",
    lambda: [
      books_routes.models.JokeBook(
        id='book-1',
        book_name='Pirate Jokes',
        jokes=['joke-a', 'joke-b'],
      )
    ],
  )

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

  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    "get_joke_book_detail_raw",
    lambda _book_id: (
      books_routes.models.JokeBook(
        id='book-42',
        book_name='Space Llamas',
        jokes=['joke-1', 'joke-2'],
        belongs_to_page_gcs_uri='gs://images.quillsstorybook.com/_joke_assets/book/belongs.png',
        zip_url='https://example.com/book.zip',
        paperback_pdf_url='https://example.com/book_paperback.pdf',
      ),
      [
        {
          'id': 'joke-1',
          'joke': {
            'setup_text': 'Setup one',
            'punchline_text': 'Punch one',
            'generation_metadata': {
              'total_cost': 0.1234,
            },
          },
          'metadata': {
            'book_page_setup_image_url':
            setup_url,
            'book_page_punchline_image_url':
            punchline_url,
            'book_page_ready':
            True,
            'all_book_page_setup_image_urls':
            [setup_url, 'https://cdn/setup2.png'],
            'all_book_page_punchline_image_urls':
            [punchline_url, 'https://cdn/punch2.png'],
          },
        },
        {
          'id': 'joke-2',
          'joke': {
            'setup_text': 'Setup two',
            'punchline_text': 'Punch two',
            'generation_metadata': {
              'generations': [{
                'model_name': 'gpt',
                'cost': 0.05,
              }]
            },
          },
          'metadata': {},
        },
      ],
    ),
  )

  with app.test_client() as client:
    resp = client.get('/admin/joke-books/book-42')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Space Llamas" in html
  assert 'class="book-id">book-42</code>' in html
  assert 'Belongs-to Page' in html
  assert '_joke_assets/book/belongs.png' in html
  assert 'Upload image' in html
  assert "joke-1" in html and "joke-2" in html
  assert 'width="800"' in html and 'height="800"' in html
  assert "width=800" in html  # width parameter in formatted CDN URL
  assert "format=png,quality=100/path/setup.png" in html
  assert "format=png,quality=100/path/punchline.png" in html
  assert "data-image-original" in html
  assert "No punchline image" in html
  assert "Download all pages" in html
  assert "Download paperback PDF" in html
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
  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    "get_joke_book",
    lambda _book_id: books_routes.models.JokeBook(id='book-abc',
                                                  jokes=['joke-5']),
  )
  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    "get_joke_with_metadata",
    lambda _joke_id: ({
      "generation_metadata": {
        "total_cost": 0.2
      }
    }, {
      "book_page_setup_image_url":
      ("https://images.quillsstorybook.com/cdn-cgi/image/"
       "width=900,format=auto,quality=80/path/setup.png")
    }),
  )

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
  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    "get_joke_book_detail_raw",
    lambda _book_id: (
      books_routes.models.JokeBook(
        id='book-local',
        book_name='Local Book',
        jokes=['joke-123'],
      ),
      [{
        'id': 'joke-123',
        'joke': {
          'setup_text': 'Setup local',
          'punchline_text': 'Punch local',
          'generation_metadata': {
            'total_cost': 1.0,
          },
        },
        'metadata': {},
      }],
    ),
  )

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
  monkeypatch.setattr(books_routes.joke_books_firestore, "list_joke_books",
                      lambda: [])

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

  mock_persist = Mock()
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      "persist_uploaded_joke_image", mock_persist)

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

  mock_persist.assert_called_once_with(
    joke_id='joke-123',
    book_id='book-456',
    target_field='book_page_setup_image_url',
    public_url='https://cdn/image.png',
  )


def test_admin_joke_book_upload_image_main_joke(monkeypatch):
  """Test uploading a main joke image updates the joke doc."""
  _mock_admin_session(monkeypatch)

  mock_upload = Mock()
  monkeypatch.setattr(books_routes.cloud_storage, "upload_bytes_to_gcs",
                      mock_upload)

  mock_get_cdn = Mock(return_value="https://cdn/main-image.png")
  monkeypatch.setattr(books_routes.cloud_storage, "get_public_image_cdn_url",
                      mock_get_cdn)

  mock_persist = Mock()
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      "persist_uploaded_joke_image", mock_persist)

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

  mock_persist.assert_called_once_with(
    joke_id='joke-999',
    book_id='manual',
    target_field='punchline_image_url',
    public_url='https://cdn/main-image.png',
  )


def test_admin_joke_book_upload_belongs_to_page(monkeypatch):
  """Book-level belongs-to upload stores a GCS URI and returns a preview."""
  _mock_admin_session(monkeypatch)

  monkeypatch.setattr(
    books_routes.joke_books_firestore,
    'get_joke_book',
    lambda _book_id: books_routes.models.JokeBook(
      id='book-456',
      book_name='Space Llamas',
    ),
  )
  mock_upload = Mock()
  monkeypatch.setattr(books_routes.cloud_storage, 'upload_bytes_to_gcs',
                      mock_upload)
  monkeypatch.setattr(books_routes.cloud_storage, 'get_public_image_cdn_url',
                      Mock(return_value='https://cdn/belongs.png'))
  mock_update = Mock(
    return_value=books_routes.models.JokeBook(
      id='book-456',
      book_name='Space Llamas',
      belongs_to_page_gcs_uri=
      'gs://images.quillsstorybook.com/_joke_assets/book/uploaded.png',
    ))
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      'update_joke_book_belongs_to_page', mock_update)
  monkeypatch.setattr(
    books_routes.utils,
    'create_timestamped_firestore_key',
    lambda *args: '20260228_120000__belongs_to__space_llamas',
  )

  data = {
    'joke_book_id': 'book-456',
    'file': (BytesIO(_make_image_bytes('PNG')), 'belongs.png'),
  }

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/upload-belongs-to-page',
                       data=data,
                       content_type='multipart/form-data')

  assert resp.status_code == 200
  payload = resp.get_json()
  assert payload == {
    'belongs_to_page_gcs_uri':
    'gs://images.quillsstorybook.com/_joke_assets/book/uploaded.png',
    'preview_url':
    'https://cdn/belongs.png',
  }
  mock_upload.assert_called_once_with(
    _make_image_bytes('PNG'),
    ('gs://images.quillsstorybook.com/_joke_assets/book/'
     '20260228_120000__belongs_to__space_llamas.png'),
    'image/png',
  )
  mock_update.assert_called_once_with(
    'book-456',
    belongs_to_page_gcs_uri=
    ('gs://images.quillsstorybook.com/_joke_assets/book/'
     '20260228_120000__belongs_to__space_llamas.png'),
  )


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
  mock_update = Mock(return_value=('https://cdn/new.png',
                                   'https://old/punch.png'))
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      "update_book_page_selection", mock_update)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/update-page',
                       data={
                         'joke_book_id': 'book-1',
                         'joke_id': 'joke-1',
                         'new_book_page_setup_image_url':
                         'https://cdn/new.png',
                       })

  assert resp.status_code == 200
  mock_update.assert_called_once_with(
    book_id='book-1',
    joke_id='joke-1',
    new_setup_url='https://cdn/new.png',
    new_punchline_url=None,
    remove_setup_url=None,
    remove_punchline_url=None,
  )
  assert resp.json['book_page_setup_image_url'] == 'https://cdn/new.png'


def test_admin_update_joke_book_page_removes_variant(monkeypatch):
  """Deleting a variant prunes it from metadata history."""
  _mock_admin_session(monkeypatch)
  remove_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
                "width=1024,format=auto,quality=75/path/setup.png")
  mock_update = Mock(return_value=(
    "https://images.quillsstorybook.com/cdn-cgi/image/"
    "width=1024,format=auto,quality=75/path/setup2.png",
    None,
  ))
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      "update_book_page_selection", mock_update)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/update-page',
                       data={
                         'joke_book_id': 'book-1',
                         'joke_id': 'joke-1',
                         'remove_book_page_setup_image_url': remove_url,
                       })

  assert resp.status_code == 200
  mock_update.assert_called_once_with(
    book_id='book-1',
    joke_id='joke-1',
    new_setup_url=None,
    new_punchline_url=None,
    remove_setup_url=remove_url,
    remove_punchline_url=None,
  )
  assert resp.json['book_page_setup_image_url'].endswith('setup2.png')


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
  mock_promote = Mock(return_value="https://cdn/book-setup.png")
  monkeypatch.setattr(books_routes.joke_books_firestore,
                      "promote_book_page_image_to_main", mock_promote)

  with app.test_client() as client:
    resp = client.post('/admin/joke-books/set-main-image',
                       data={
                         'joke_book_id': 'book-abc',
                         'joke_id': 'joke-77',
                         'target': 'setup',
                       })

  assert resp.status_code == 200
  mock_promote.assert_called_once_with(
    book_id='book-abc',
    joke_id='joke-77',
    target='setup',
  )
  assert resp.get_json()['setup_image_url'] == "https://cdn/book-setup.png"
