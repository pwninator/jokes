"""Tests for the web_fns module."""
import datetime
from unittest.mock import Mock
from io import BytesIO
import pytest

from common import models
from functions import web_fns
from services import search


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(web_fns.auth_helpers, "verify_session", lambda _req:
                      ("uid123", {
                        "role": "admin"
                      }))


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


def test_lunchbox_get_renders_form():
  with web_fns.app.test_client() as client:
    resp = client.get('/lunchbox')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Header brand should be clickable.
  assert '<a class="brand"' in html
  # Nav should mark lunchbox link active.
  assert 'href="/lunchbox"' in html
  assert 'Printable Joke Notes' in html
  assert 'nav-link--active' in html
  # Copy may change; assert key hero heading scaffold exists.
  assert 'id="lunchbox-hero-title"' in html
  assert 'name="email"' in html
  # Submit CTA copy may change; assert the submit control exists.
  assert 'type="submit"' in html
  assert 'web_lunchbox_submit_click' in html


def test_lunchbox_post_stores_lead_and_redirects(monkeypatch):
  captured: dict[str, object] = {}

  def _fake_create_lead(**kwargs):
    captured["kwargs"] = kwargs
    return {
      "email": kwargs["email"],
    }

  monkeypatch.setattr(web_fns.joke_lead_operations, "create_lead",
                      _fake_create_lead)

  with web_fns.app.test_client() as client:
    resp = client.post('/lunchbox?country_override=DE',
                       data={
                         'email': 'Test@Example.com',
                       })

  assert resp.status_code == 302
  assert resp.headers["Location"].endswith('/lunchbox-thank-you')
  assert captured["kwargs"]["email"] == 'test@example.com'
  assert captured["kwargs"]["country_code"] == 'DE'
  assert captured["kwargs"]["signup_source"] == 'lunchbox'
  assert captured["kwargs"][
    "group_id"] == web_fns.joke_lead_operations.GROUP_SNICKERDOODLE_CLUB


def test_lunchbox_post_invalid_email_renders_error(monkeypatch):
  create_lead = Mock()
  monkeypatch.setattr(web_fns.joke_lead_operations, "create_lead", create_lead)

  with web_fns.app.test_client() as client:
    resp = client.post('/lunchbox', data={'email': 'not-an-email'})

  assert resp.status_code == 400
  html = resp.get_data(as_text=True)
  assert 'Please enter a valid email address.' in html
  create_lead.assert_not_called()


def test_lunchbox_post_mailerlite_failure_renders_error(monkeypatch):

  def _fail(**_kwargs):
    raise RuntimeError("MailerLite down")

  monkeypatch.setattr(web_fns.joke_lead_operations, "create_lead", _fail)

  with web_fns.app.test_client() as client:
    resp = client.post('/lunchbox?country_override=DE',
                       data={
                         'email': 'test@example.com',
                       })

  assert resp.status_code == 500
  html = resp.get_data(as_text=True)
  assert 'Unable to process your request. Please try again.' in html


def test_lunchbox_thank_you_renders():
  """Thank you page should render with correct Amazon URL."""
  with web_fns.app.test_client() as client:
    resp = client.get('/lunchbox-thank-you')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'High Five!' in html
  assert 'id="thankyou-title"' in html
  assert 'Get the Book on Amazon' in html
  assert 'web_lunchbox_thank_you' in html
  # Should contain an amazon.com URL (default US)
  assert 'href="https://www.amazon.com/dp/B0G7F82P65' in html


def test_lunchbox_thank_you_uses_country_specific_domain():
  """Thank you page should use country-specific Amazon domain."""
  with web_fns.app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'GB'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'www.amazon.co.uk' in html
  assert 'B0G7F82P65' in html  # Paperback ASIN


def test_lunchbox_thank_you_falls_back_to_ebook_for_unsupported_country():
  """Thank you page should use ebook for countries without paperback."""
  with web_fns.app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'BR'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'www.amazon.com.br' in html
  assert 'B0G9765J19' in html  # Ebook ASIN (fallback)


def test_lunchbox_thank_you_includes_attribution_tag():
  """Thank you page should include attribution for lunchbox_thank_you source."""
  with web_fns.app.test_client() as client:
    resp = client.get('/lunchbox-thank-you',
                      headers={'X-Appengine-Country': 'US'})

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Should contain the attribution tag configured for (B0G7F82P65, lunchbox_thank_you)
  assert 'maas=maas_adg_92547F51E50DB214BCBCD9D297E81344_afap_abs' in html
  assert 'ref_=aa_maas' in html
  assert 'tag=maas' in html


def test_lunchbox_download_pdf_renders(monkeypatch):
  calls = []

  def _mock_submit(**kwargs):
    calls.append(kwargs)

  monkeypatch.setattr(web_fns, "_submit_ga4_event_fire_and_forget",
                      _mock_submit)
  monkeypatch.setattr(web_fns.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  with web_fns.app.test_client() as client:
    client.set_cookie("_ga", "GA1.1.3333333333.4444444444")
    resp = client.get('/lunchbox-download-pdf')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<meta name="robots" content="noindex,nofollow">' in html
  assert "location.replace" in html
  assert 'lunchbox_notes_animal_jokes.pdf' in html
  assert 'web_lunchbox_download_client' in html
  assert 'CompleteRegistration' in html
  assert 'fbq' in html
  assert len(calls) == 1
  assert calls[0]["measurement_id"] == "G-D2B7E8PXJJ"
  assert calls[0]["client_id"] == "3333333333.4444444444"
  assert calls[0]["event_name"] == "web_lunchbox_download_server"
  assert calls[0]["event_params"]["asset"] == "lunchbox_notes_animal_jokes.pdf"


def test_topic_page_uses_batch_fetch(monkeypatch):
  """Topic page uses batched get_punny_jokes and renders content."""
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  search_result = search.JokeSearchResult(joke_id="joke1", vector_distance=0.1)
  mock_search_jokes.return_value = [search_result]

  joke = models.PunnyJoke(
    key="joke1",
    setup_text="Why did the scarecrow win an award?",
    punchline_text="Because he was outstanding in his field.",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punchline.jpg")
  mock_get_punny_jokes.return_value = [joke]

  with web_fns.app.test_client() as client:
    resp = client.get('/jokes/dogs')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Default header brand should be clickable on standard pages.
  assert '<a class="brand" href="' in html
  assert 'application/ld+json' in html
  assert "Why did the scarecrow win an award?" in html
  assert "Because he was outstanding in his field." in html
  mock_get_punny_jokes.assert_called_once_with(["joke1"])


def test_sitemap_returns_hardcoded_topics():
  with web_fns.app.test_client() as client:
    resp = client.get('/sitemap.xml')
  assert resp.status_code == 200
  xml = resp.get_data(as_text=True)
  assert 'https://snickerdoodlejokes.com/lunchbox' in xml
  assert 'https://snickerdoodlejokes.com/jokes/dogs' in xml


def test_topic_page_renders_with_json_ld_and_reveal(monkeypatch):
  """Verify /jokes/<topic> renders cards, details, and JSON-LD."""
  # Arrange
  # Mock search and firestore
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  search_result = search.JokeSearchResult(joke_id="j1", vector_distance=0.01)
  mock_search_jokes.return_value = [search_result]

  joke = models.PunnyJoke(
    key="j1",
    setup_text="Why did the dog cross the road?",
    punchline_text="To get to the barking lot.",
    setup_image_url="http://example.com/setup1.jpg",
    punchline_image_url="http://example.com/punch1.jpg",
  )
  mock_get_punny_jokes.return_value = [joke]

  # Act
  with web_fns.app.test_client() as client:
    resp = client.get('/jokes/dogs')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<h1>Dogs jokes</h1>' in html
  assert 'application/ld+json' in html
  assert 'FAQPage' in html
  assert '<details>' in html
  assert 'data-analytics-event="joke_reveal_toggle"' in html
  assert '<summary data-analytics-event="joke_reveal_toggle"' in html
  # Layout and image sizing
  assert '.topic-page .grid { grid-template-columns: 1fr;' in html
  assert 'aspect-ratio: 1 / 1' in html
  assert 'width="600" height="600"' in html
  assert 'href="/privacy.html"' in html
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'web_footer_privacy_click' in html
  # Cache headers present
  assert 'Cache-Control' in resp.headers


def test_index_page_renders_top_jokes(monkeypatch):
  """Verify that the index page '/' renders the top jokes."""
  # Arrange
  mock_get_top_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_top_jokes", mock_get_top_jokes)
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(web_fns.firestore, "get_daily_joke", mock_get_daily_joke)

  joke = models.PunnyJoke(
    key="joke123",
    setup_text="What do you call a fake noodle?",
    punchline_text="An Impasta!",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punchline.jpg",
  )
  mock_get_top_jokes.return_value = [joke]

  # Act
  with web_fns.app.test_client() as client:
    resp = client.get('/')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'href="/"' in html
  assert 'Home' in html
  assert 'href="/lunchbox"' in html
  assert 'Printable Joke Notes' in html
  # Nav should mark home link active.
  assert 'nav-link--active' in html
  # Header presence (accessible span) and section scaffolding instead of brittle copy.
  assert '<section class="favorites-section"' in html
  assert 'Fan Favorites from the Cookie Jar' in html
  assert 'class="favorites-grid"' in html
  assert "What do you call a fake noodle?" in html
  assert "An Impasta!" in html
  assert 'data-analytics-event="web_index_joke_reveal_click"' in html
  assert 'data-analytics-event="web_index_play_store_click"' in html
  assert 'data-analytics-label="joke_end_card"' in html
  # Badge alt text per template
  assert "Get it on Google Play" in html
  assert 'href="/privacy.html"' in html
  assert 'target="_blank"' in html
  assert 'rel="noopener noreferrer"' in html
  assert 'web_footer_privacy_click' in html
  assert 'Privacy Policy' in html
  assert 'Cache-Control' in resp.headers


def test_index_page_includes_nonempty_unique_meta_tags(monkeypatch):
  """Index page should render a single, non-empty set of SEO meta tags."""
  mock_get_top_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_top_jokes", mock_get_top_jokes)
  mock_get_daily_joke = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_daily_joke", mock_get_daily_joke)

  mock_get_top_jokes.return_value = [
    models.PunnyJoke(
      key="joke123",
      setup_text="What do you call a fake noodle?",
      punchline_text="An Impasta!",
      setup_image_url="http://example.com/setup.jpg",
      punchline_image_url="http://example.com/punchline.jpg",
    )
  ]
  mock_get_daily_joke.return_value = models.PunnyJoke(
    key="daily-1",
    setup_text="What is every parent's favorite Christmas song?",
    punchline_text="Silent Night.",
  )

  with web_fns.app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  assert html.count('<meta name="description"') == 1
  assert html.count('<meta property="og:description"') == 1
  assert html.count('<meta name="twitter:description"') == 1

  # We don't assert exact copy; just that it's non-empty and consistent across meta/OG/Twitter.
  assert 'content=""' not in html

  assert '<meta name="description"\n  content="' in html
  start = html.index('<meta name="description"\n  content="') + len(
    '<meta name="description"\n  content="')
  end = html.index('">', start)
  description = html[start:end]
  assert description.strip() != ''

  assert f'<meta property="og:description"\n  content="{description}">' in html
  assert f'<meta name="twitter:description"\n  content="{description}">' in html

  assert html.count('property="og:image"') == 1
  assert html.count('name="twitter:image"') == 1
  assert html.count('name="twitter:card"') == 1


def test_fetch_topic_jokes_sorts_by_popularity_then_distance(monkeypatch):
  """_fetch_topic_jokes orders by popularity desc, then vector distance asc."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  # Three results: A and B same popularity; B has smaller distance than A
  # C has higher popularity than both and should come first.
  mock_search_jokes.return_value = [
    search.JokeSearchResult(joke_id="A", vector_distance=0.20),
    search.JokeSearchResult(joke_id="B", vector_distance=0.10),
    search.JokeSearchResult(joke_id="C", vector_distance=0.30),
  ]

  # Populate num_saved_users_fraction when firestore objects are returned
  jA_fs = models.PunnyJoke(key="A",
                           setup_text="sa",
                           punchline_text="pa",
                           num_saved_users_fraction=0.5)
  jB_fs = models.PunnyJoke(key="B",
                           setup_text="sb",
                           punchline_text="pb",
                           num_saved_users_fraction=0.5)
  jC_fs = models.PunnyJoke(key="C",
                           setup_text="sc",
                           punchline_text="pc",
                           num_saved_users_fraction=0.8)
  mock_get_punny_jokes.return_value = [jA_fs, jB_fs, jC_fs]

  # Act
  ordered = web_fns._fetch_topic_jokes("dogs", limit=3)

  # Assert
  keys = [j.key for j in ordered]
  # C first (highest popularity), then B (tie pop, closer), then A
  assert keys == ["C", "B", "A"]


def test_admin_joke_books_links_to_detail(monkeypatch):
  """Admin list page links to the detail view."""
  _mock_admin_session(monkeypatch)
  book_doc = _FakeSnapshot("book-1", {
    "book_name": "Pirate Jokes",
    "jokes": ["joke-a", "joke-b"],
  })
  books = {"book-1": _FakeDocumentRef(book_doc)}
  fake_db = _FakeFirestore(books=books, jokes={})
  monkeypatch.setattr(web_fns.firestore, "db", lambda: fake_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/joke-books')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<a href="/admin/joke-books/book-1">' in html
  assert "Pirate Jokes" in html


def test_admin_joke_book_detail_renders_images_and_placeholders(monkeypatch):
  """Detail view shows 600px images and placeholders when missing."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(web_fns.utils, "is_emulator", lambda: False)

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
        "all_book_page_setup_image_urls":
        [setup_url, "https://cdn/setup2.png"],
        "all_book_page_punchline_image_urls":
        [punchline_url, "https://cdn/punch2.png"],
      }))
  joke_one = _FakeDocumentRef(
    _FakeSnapshot("joke-1", {"generation_metadata": {
      "total_cost": 0.1234,
    }}), {"metadata": _FakeCollection({"metadata": metadata_doc_one})})

  metadata_doc_two = _FakeDocumentRef(_FakeSnapshot("metadata", {}))
  joke_two = _FakeDocumentRef(
    _FakeSnapshot(
      "joke-2", {
        "generation_metadata": {
          "generations": [{
            "model_name": "gpt",
            "cost": 0.05
          }]
        }
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
  monkeypatch.setattr(web_fns.firestore, "db", lambda: fake_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/joke-books/book-42')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Space Llamas" in html
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
  assert 'class="variant-tile"' in html
  assert "book_page_setup_image_url" in html
  assert "book_page_punchline_image_url" in html
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
  monkeypatch.setattr(web_fns.firestore, "db", lambda: fake_db)

  with web_fns.app.test_client() as client:
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
  monkeypatch.setattr(web_fns.utils, "is_emulator", lambda: True)

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
    _FakeSnapshot("joke-123", {"generation_metadata": {
      "total_cost": 1.0
    }}), {"metadata": _FakeCollection({"metadata": metadata_doc})})
  fake_db = _FakeFirestore(books=books, jokes={"joke-123": joke})
  monkeypatch.setattr(web_fns.firestore, "db", lambda: fake_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/joke-books/book-local')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "http://127.0.0.1:5001/storyteller-450807/us-central1/generate_joke_book_page" in html
  assert "$1.0000" in html


def test_admin_routes_allow_emulator_without_auth(monkeypatch):
  """When in emulator mode, admin routes bypass auth checks."""
  monkeypatch.setattr(web_fns.auth_helpers.utils, "is_emulator", lambda: True)

  def _fail(_req):
    raise AssertionError("verify_session should not be called in emulator")

  monkeypatch.setattr(web_fns.auth_helpers, "verify_session", _fail)
  fake_db = _FakeFirestore(books={}, jokes={})
  monkeypatch.setattr(web_fns.firestore, "db", lambda: fake_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/joke-books')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Joke Books" in html
  assert "No joke books found." in html


def test_pages_include_ga4_tag_and_parchment_background(monkeypatch):
  """All pages should include GA4 and use the parchment background color."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)
  mock_get_top_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_top_jokes", mock_get_top_jokes)

  search_result = search.JokeSearchResult(joke_id="j3", vector_distance=0.03)
  mock_search_jokes.return_value = [search_result]

  joke = models.PunnyJoke(
    key="j3",
    setup_text="S",
    punchline_text="P",
    setup_image_url="http://example.com/s3.jpg",
    punchline_image_url="http://example.com/p3.jpg",
  )
  mock_get_punny_jokes.return_value = [joke]
  top_joke = models.PunnyJoke(
    key="top1",
    setup_text="Top setup",
    punchline_text="Top punch",
    setup_image_url="http://example.com/d.jpg",
    punchline_image_url="http://example.com/pd.jpg",
  )
  mock_get_top_jokes.return_value = [top_joke]

  # Act
  with web_fns.app.test_client() as client:
    topic_resp = client.get('/jokes/dogs')
    index_resp = client.get('/')

  # Assert
  assert topic_resp.status_code == 200
  assert index_resp.status_code == 200
  topic_html = topic_resp.get_data(as_text=True)
  index_html = index_resp.get_data(as_text=True)

  # GA4 present
  assert 'gtag/js?id=G-D2B7E8PXJJ' in topic_html
  assert "gtag('config', 'G-D2B7E8PXJJ')" in topic_html
  assert 'gtag/js?id=G-D2B7E8PXJJ' in index_html
  assert "gtag('config', 'G-D2B7E8PXJJ')" in index_html
  assert 'data-analytics-event="web_index_play_store_click"' in index_html

  # Background palette variables present
  assert '--color-bg-outer: #e4d0ae;' in topic_html
  assert '--color-bg-outer: #e4d0ae;' in index_html
  assert 'web_footer_privacy_click' in topic_html
  assert 'web_footer_privacy_click' in index_html
  assert 'href="/privacy.html"' in topic_html
  assert 'href="/privacy.html"' in index_html
  assert 'target="_blank"' in topic_html
  assert 'target="_blank"' in index_html
  assert 'rel="noopener noreferrer"' in topic_html
  assert 'rel="noopener noreferrer"' in index_html

  # New header and favicon present; old Dogs link removed
  assert '<header class="site-header">' in topic_html
  assert '<header class="site-header">' in index_html
  assert '<link rel="icon" type="image/png"' in index_html
  assert '<link rel="icon" type="image/png"' in topic_html
  assert '/jokes/dogs' not in index_html


def test_amazon_redirect_renders_intermediate_page(monkeypatch):
  """Amazon redirects should render an intermediate redirect page (not a 302)."""
  calls = []

  def _mock_submit(**kwargs):
    calls.append(kwargs)

  monkeypatch.setattr(web_fns, "_submit_ga4_event_fire_and_forget",
                      _mock_submit)
  monkeypatch.setattr(web_fns.config, "get_google_analytics_api_key",
                      lambda: "test-secret")
  with web_fns.app.test_client() as client:
    client.set_cookie("_ga", "GA1.1.1111111111.2222222222")
    resp = client.get('/book-animal-jokes?country_override=DE')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<meta name="robots" content="noindex,nofollow">' in html
  assert "amazon_redirect" in html
  assert "location.replace" in html
  assert "www.amazon.de" in html
  assert "B0G7F82P65" in html
  assert len(calls) == 1
  assert calls[0]["measurement_id"] == "G-D2B7E8PXJJ"
  assert calls[0]["client_id"] == "1111111111.2222222222"
  assert calls[0]["event_name"] == "amazon_redirect_server"
  assert calls[0]["event_params"]["redirect_key"] == "book-animal-jokes"


def test_amazon_redirect_falls_back_to_ebook_for_unsupported_country():
  """Product redirects should fall back to ebook ASIN for unsupported countries."""
  with web_fns.app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=BR')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "www.amazon.com.br" in html
  assert "B0G9765J19" in html


def test_amazon_redirect_adds_attribution_tag_for_source(monkeypatch):
  """Product redirects should include affiliate tags when configured."""
  monkeypatch.setattr(web_fns.amazon_redirect, "AMAZON_ATTRIBUTION_TAGS",
                      {("B0G7F82P65", "aae"): "ref_=aa&tag=tag-20"})

  with web_fns.app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=US&source=aae')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" in html
  assert "ref_=aa" in html


def test_amazon_redirect_defaults_source_to_aa(monkeypatch):
  """Product redirects should default source=aa when missing."""
  monkeypatch.setattr(web_fns.amazon_redirect, "AMAZON_ATTRIBUTION_TAGS",
                      {("B0G7F82P65", "aa"): "ref_=aa&tag=tag-20"})

  with web_fns.app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=US')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" in html
  assert "ref_=aa" in html


def test_amazon_redirect_uses_resolved_asin_for_attribution(monkeypatch):
  """Attribution tags should use the resolved ASIN (fallback included)."""
  monkeypatch.setattr(web_fns.amazon_redirect, "AMAZON_ATTRIBUTION_TAGS",
                      {("B0G9765J19", "aae"): "ref_=aa&tag=tag-ebook"})

  with web_fns.app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=BR&source=aae')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "B0G9765J19" in html
  assert "tag=tag-ebook" in html
  assert "ref_=aa" in html


def test_amazon_review_redirect_ignores_attribution_tags(monkeypatch):
  """Review redirects should never apply affiliate tags."""
  monkeypatch.setattr(web_fns.amazon_redirect, "AMAZON_ATTRIBUTION_TAGS",
                      {("B0G7F82P65", "aae"): "ref_=aa&tag=tag-20"})

  with web_fns.app.test_client() as client:
    resp = client.get('/review-animal-jokes?country_override=US&source=aae')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "tag=tag-20" not in html


def test_amazon_redirect_logs_warning_for_unknown_source(monkeypatch):
  """Unknown source codes should log a warning and skip tagging."""
  mock_logger = Mock()
  monkeypatch.setattr(web_fns.amazon_redirect, "logger", mock_logger)
  monkeypatch.setattr(web_fns.amazon_redirect, "AMAZON_ATTRIBUTION_TAGS", {})

  with web_fns.app.test_client() as client:
    resp = client.get('/book-animal-jokes?country_override=US&source=unknown')

  assert resp.status_code == 200
  mock_logger.warn.assert_called_once()


def test_admin_joke_book_upload_image_book_page(monkeypatch):
  """Test uploading a book page image updates metadata and variants."""
  _mock_admin_session(monkeypatch)

  mock_upload = Mock()
  monkeypatch.setattr(web_fns.cloud_storage, "upload_bytes_to_gcs",
                      mock_upload)

  mock_get_cdn = Mock(return_value="https://cdn/image.png")
  monkeypatch.setattr(web_fns.cloud_storage, "get_public_image_cdn_url",
                      mock_get_cdn)

  # Mock Firestore
  mock_metadata_ref = Mock()
  mock_metadata_ref.get.return_value = Mock(exists=True)

  mock_joke_ref = Mock()
  mock_joke_ref.collection.return_value.document.return_value = mock_metadata_ref

  mock_db = Mock()
  mock_db.collection.return_value.document.return_value = mock_joke_ref
  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  data = {
    'joke_id': 'joke-123',
    'joke_book_id': 'book-456',
    'target_field': 'book_page_setup_image_url',
    'file': (BytesIO(b"fake image content"), 'test.png'),
  }

  with web_fns.app.test_client() as client:
    resp = client.post('/admin/joke-books/upload-image',
                       data=data,
                       content_type='multipart/form-data')

  assert resp.status_code == 200
  assert resp.json['url'] == "https://cdn/image.png"

  # Verify Upload
  mock_upload.assert_called_once()
  args = mock_upload.call_args[0]
  assert args[0] == b"fake image content"
  assert "joke_books/book-456/joke-123/custom_setup_" in args[1]
  assert args[1].endswith(".png")

  # Verify Firestore Update
  mock_metadata_ref.update.assert_called_once()
  update_args = mock_metadata_ref.update.call_args[0][0]
  assert update_args['book_page_setup_image_url'] == "https://cdn/image.png"
  # Verify ArrayUnion was used (checking strictly might be hard with Mocks unless we check type)
  assert 'all_book_page_setup_image_urls' in update_args


def test_admin_joke_book_upload_image_main_joke(monkeypatch):
  """Test uploading a main joke image updates the joke doc."""
  _mock_admin_session(monkeypatch)

  mock_upload = Mock()
  monkeypatch.setattr(web_fns.cloud_storage, "upload_bytes_to_gcs",
                      mock_upload)

  mock_get_cdn = Mock(return_value="https://cdn/main-image.jpg")
  monkeypatch.setattr(web_fns.cloud_storage, "get_public_image_cdn_url",
                      mock_get_cdn)

  # Mock Firestore
  mock_joke_ref = Mock()
  mock_db = Mock()
  mock_db.collection.return_value.document.return_value = mock_joke_ref
  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  data = {
    'joke_id': 'joke-999',
    'target_field': 'punchline_image_url',
    'file': (BytesIO(b"content"), 'punch.jpg'),
  }

  with web_fns.app.test_client() as client:
    resp = client.post('/admin/joke-books/upload-image',
                       data=data,
                       content_type='multipart/form-data')

  assert resp.status_code == 200

  # Verify Upload
  mock_upload.assert_called_once()
  args = mock_upload.call_args[0]
  assert "jokes/joke-999/custom_punchline_" in args[1]

  # Verify Firestore Update on Main Doc
  mock_joke_ref.update.assert_called_once_with(
    {'punchline_image_url': "https://cdn/main-image.jpg"})


def test_admin_joke_book_upload_invalid_input(monkeypatch):
  """Test invalid inputs return 400."""
  _mock_admin_session(monkeypatch)

  with web_fns.app.test_client() as client:
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
  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  updates = {
    'book_page_setup_image_url': 'https://cdn/new.png',
    'book_page_punchline_image_url': 'https://old/punch.png',
    'all_book_page_setup_image_urls': ['https://cdn/new.png'],
    'all_book_page_punchline_image_urls': ['https://old/punch.png'],
  }
  mock_prepare = Mock(return_value=updates)
  monkeypatch.setattr(web_fns.models.PunnyJoke,
                      "prepare_book_page_metadata_updates", mock_prepare)

  with web_fns.app.test_client() as client:
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

  with web_fns.app.test_client() as client:
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
  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  with web_fns.app.test_client() as client:
    resp = client.post('/admin/joke-books/set-main-image',
                       data={
                         'joke_book_id': 'book-abc',
                         'joke_id': 'joke-77',
                         'target': 'setup',
                       })

  assert resp.status_code == 200
  update_args = joke_ref.update.call_args[0][0]
  assert update_args['setup_image_url'] == "https://cdn/book-setup.png"
  assert isinstance(update_args['all_setup_image_urls'], web_fns.ArrayUnion)
  assert update_args['setup_image_url_upscaled'] is None
  assert resp.get_json()['setup_image_url'] == "https://cdn/book-setup.png"


def test_admin_stats_page_loads(monkeypatch):
  """Test the stats page loads and renders charts with data."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(web_fns.auth_helpers.utils, "is_emulator", lambda: True)

  # Mock Firestore query
  mock_db = Mock()
  mock_collection = Mock()
  mock_query = Mock()

  # Setup mock stats docs
  doc1 = Mock()
  doc1.id = "20230101"
  doc1.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "10": 5,
      "20": 2
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "5": {
        "50": 3
      }
    }
  }

  doc2 = Mock()
  doc2.id = "20230102"
  doc2.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "10": 6,
      "20": 3
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "5": {
        "50": 4
      }
    }
  }

  # Mock query returning doc2 then doc1 (Desc order)
  mock_query.limit.return_value.stream.return_value = [doc2, doc1]
  mock_collection.order_by.return_value = mock_query
  mock_db.collection.return_value = mock_collection

  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/stats')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  # Check for canvas elements
  assert '<canvas id="dauChart"></canvas>' in html
  assert '<canvas id="retentionChart"></canvas>' in html

  # Check for data injection (basic check)
  assert 'dauData' in html
  assert 'retentionData' in html
  assert '20230101' in html
  assert '20230102' in html

  # Verify processing logic for Chart.js
  # We expect buckets 10-19 and 20-29 for DAU after bucketing
  assert '"label": "10-19 jokes"' in html
  assert '"label": "20-29 jokes"' in html


def test_bucket_jokes_viewed_ranges():
  """Ensure bucket ranges match the defined spec."""
  assert web_fns._bucket_jokes_viewed(0) == "0"
  assert web_fns._bucket_jokes_viewed(1) == "1-9"
  assert web_fns._bucket_jokes_viewed(9) == "1-9"
  assert web_fns._bucket_jokes_viewed(10) == "10-19"
  assert web_fns._bucket_jokes_viewed(99) == "90-99"
  assert web_fns._bucket_jokes_viewed(100) == "100-149"
  assert web_fns._bucket_jokes_viewed(149) == "100-149"
  assert web_fns._bucket_jokes_viewed(150) == "150-199"


def test_rebucket_counts_and_matrix():
  """Rebucket merges numeric and string buckets into defined ranges."""
  counts = {"1": 2, "5": 3, "10": 1, "101": 4, "bad": 9}
  rebucketed = web_fns._rebucket_counts(counts)
  assert rebucketed == {
    "1-9": 5,
    "10-19": 1,
    "100-149": 4,
  }

  matrix = {"2": counts}
  rebucketed_matrix = web_fns._rebucket_matrix(matrix)
  assert rebucketed_matrix == {"2": rebucketed}


def test_admin_stats_rebuckets_and_colors(monkeypatch):
  """Admin stats view rebuckets raw data and assigns gradient colors."""
  _mock_admin_session(monkeypatch)
  monkeypatch.setattr(web_fns.auth_helpers.utils, "is_emulator", lambda: True)

  captured: dict = {}

  def _fake_render(template_name, **context):
    captured["template"] = template_name
    captured.update(context)
    return "OK"

  monkeypatch.setattr(web_fns.flask, "render_template", _fake_render)

  # Mock Firestore query with raw (unbucketed) counts
  mock_db = Mock()
  mock_collection = Mock()
  mock_query = Mock()

  doc1 = Mock()
  doc1.id = "20230101"
  doc1.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "0": 1,
      "1": 2,
      "12": 3,
      "100": 4
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "2": {
        "1": 1,
        "12": 2,
        "150": 3
      },
      "9": {
        "1": 4
      },
      "15": {
        "12": 2
      },
    }
  }

  doc2 = Mock()
  doc2.id = "20230102"
  doc2.to_dict.return_value = {
    "num_1d_users_by_jokes_viewed": {
      "0": 1,
      "1": 2,
      "12": 3,
      "100": 4
    },
    "num_7d_users_by_days_used_by_jokes_viewed": {
      "2": {
        "1": 1,
        "12": 2,
        "150": 3
      },
      "9": {
        "1": 4
      },
      "15": {
        "12": 2
      },
    }
  }

  mock_query.limit.return_value.stream.return_value = [doc2, doc1]
  mock_collection.order_by.return_value = mock_query
  mock_db.collection.return_value = mock_collection
  monkeypatch.setattr(web_fns.firestore, "db", lambda: mock_db)

  with web_fns.app.test_client() as client:
    resp = client.get('/admin/stats')

  assert resp.status_code == 200
  assert captured["template"] == 'admin/stats.html'

  dau_data = captured["dau_data"]
  assert dau_data["labels"] == ["20230101", "20230102"]
  dau_labels = [ds["label"] for ds in dau_data["datasets"]]
  assert dau_labels == [
    "0 jokes", "1-9 jokes", "10-19 jokes", "100-149 jokes", "150-199 jokes"
  ]
  # Order places highest buckets at the bottom of the stack (most negative drawn first)
  orders = [ds["order"] for ds in dau_data["datasets"]]
  assert orders == [0, -1, -2, -3, -4]
  # Buckets aggregated chronologically (doc1 then doc2)
  assert dau_data["datasets"][0]["data"] == [1, 1]  # 0 bucket
  assert dau_data["datasets"][1]["data"] == [2, 2]  # 1-9 bucket
  assert dau_data["datasets"][2]["data"] == [3, 3]  # 10-19 bucket
  assert dau_data["datasets"][3]["data"] == [4, 4]  # 100-149 bucket
  assert dau_data["datasets"][4]["data"] == [0,
                                             0]  # 150-199 bucket (not in DAU)
  # Color map: zero bucket gray, others colored (not gray)
  assert dau_data["datasets"][0]["backgroundColor"] == "#9e9e9e"
  non_zero_colors = {ds["backgroundColor"] for ds in dau_data["datasets"][1:]}
  assert "#9e9e9e" not in non_zero_colors

  retention_data = captured["retention_data"]
  assert retention_data["labels"] == ["2", "8-14", "15-21"]
  retention_labels = [ds["label"] for ds in retention_data["datasets"]]
  assert retention_labels == ["1-9 jokes", "10-19 jokes", "150-199 jokes"]

  # Percentages: counts 1,2,3 => totals 6
  def _dataset(label):
    return next(d for d in retention_data["datasets"] if d["label"] == label)

  # Day 2: totals = 6 (1,2,3)
  assert _dataset("1-9 jokes")["data"][0] == pytest.approx(16.6666, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][0] == pytest.approx(33.3333, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][0] == pytest.approx(50.0, rel=1e-3)
  # Day 8-14: totals = 4 (all in 1-9)
  assert _dataset("1-9 jokes")["data"][1] == pytest.approx(100.0, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][1] == pytest.approx(0.0, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][1] == pytest.approx(0.0, rel=1e-3)
  # Day 15-21: totals = 2 (all in 10-19)
  assert _dataset("1-9 jokes")["data"][2] == pytest.approx(0.0, rel=1e-3)
  assert _dataset("10-19 jokes")["data"][2] == pytest.approx(100.0, rel=1e-3)
  assert _dataset("150-199 jokes")["data"][2] == pytest.approx(0.0, rel=1e-3)
