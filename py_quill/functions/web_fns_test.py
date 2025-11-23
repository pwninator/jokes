"""Tests for the web_fns module."""
from unittest.mock import Mock

from common import models
from functions import web_fns
from services import search


def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(web_fns.auth_helpers,
                      "verify_session",
                      lambda _req: ("uid123", {
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
    return self._docs.get(doc_id,
                          _FakeDocumentRef(
                            _FakeSnapshot(doc_id, None, exists=False)))


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


def test_topic_page_uses_batch_fetch(monkeypatch):
  """Topic page uses batched get_punny_jokes and renders content."""
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  search_result = search.JokeSearchResult(joke_id="joke1",
                                          vector_distance=0.1)
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
  assert 'application/ld+json' in html
  assert "Why did the scarecrow win an award?" in html
  assert "Because he was outstanding in his field." in html
  mock_get_punny_jokes.assert_called_once_with(["joke1"])


def test_sitemap_returns_hardcoded_topics():
  with web_fns.app.test_client() as client:
    resp = client.get('/sitemap.xml')
  assert resp.status_code == 200
  xml = resp.get_data(as_text=True)
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

  search_result = search.JokeSearchResult(joke_id="j1",
                                          vector_distance=0.01)
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
  assert "Fan-Favorite Jokes" in html
  assert "Here are some of our most popular jokes, right from the app!" in html
  assert "What do you call a fake noodle?" in html
  assert "An Impasta!" in html
  assert 'data-analytics-event="web_index_joke_scroll_click"' in html
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

  setup_url = (
    "https://images.quillsstorybook.com/cdn-cgi/image/"
    "format=auto,quality=75/path/setup.png")
  punchline_url = (
    "https://images.quillsstorybook.com/cdn-cgi/image/"
    "format=auto,quality=75/path/punchline.png")

  metadata_doc_one = _FakeDocumentRef(
    _FakeSnapshot("metadata", {
      "book_page_setup_image_url": setup_url,
      "book_page_punchline_image_url": punchline_url,
    }))
  joke_one = _FakeDocumentRef(_FakeSnapshot("joke-1", {}), {
    "metadata": _FakeCollection({"metadata": metadata_doc_one})
  })

  metadata_doc_two = _FakeDocumentRef(_FakeSnapshot("metadata", {}))
  joke_two = _FakeDocumentRef(_FakeSnapshot("joke-2", {}), {
    "metadata": _FakeCollection({"metadata": metadata_doc_two})
  })

  books = {
    "book-42":
    _FakeDocumentRef(
      _FakeSnapshot("book-42", {
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
  assert 'width="600"' in html and 'height="600"' in html
  assert "width=600" in html  # width parameter in formatted CDN URL
  assert "No punchline image" in html
  assert "Download all pages" in html


def test_admin_routes_allow_emulator_without_auth(monkeypatch):
  """When in emulator mode, admin routes bypass auth checks."""
  monkeypatch.setattr(web_fns.auth_helpers.utils, "is_emulator",
                      lambda: True)

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
  monkeypatch.setattr(web_fns.firestore, "get_top_jokes",
                      mock_get_top_jokes)

  search_result = search.JokeSearchResult(joke_id="j3",
                                          vector_distance=0.03)
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
  assert 'data-analytics-event="web_index_play_store_click"' in topic_html
  assert 'data-analytics-label="header"' in topic_html
  assert 'data-analytics-event="web_index_play_store_click"' in index_html
  assert 'data-analytics-label="header"' in index_html

  # Background matches dark parchment color
  assert 'background: #121212' in topic_html
  assert 'background: #121212' in index_html
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
