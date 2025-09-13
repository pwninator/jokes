"""Tests for the web_fns module."""
from unittest.mock import Mock

from common import models
from functions import web_fns
from services import search


def test_topic_page_uses_batch_fetch(monkeypatch):
  """Topic page uses batched get_punny_jokes and renders content."""
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(web_fns.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  search_result = search.JokeSearchResult(joke=models.PunnyJoke(
    key="joke1", setup_text="s", punchline_text="p"),
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
  assert '/jokes/dogs' in xml


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

  search_result = search.JokeSearchResult(
    joke=models.PunnyJoke(key="j1",
                          setup_text="Setup one",
                          punchline_text="Punch one"),
    vector_distance=0.01,
  )
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
  assert '<summary>Reveal punchline</summary>' in html
  # Layout and image sizing
  assert '.topic-page .grid { grid-template-columns: 1fr;' in html
  assert 'aspect-ratio: 1 / 1' in html
  assert 'width="600" height="600"' in html
  # Cache headers present
  assert 'Cache-Control' in resp.headers


def test_index_page_renders_joke_of_the_day(monkeypatch):
  """Verify that the index page '/' renders the joke of the day."""
  # Arrange
  mock_get_daily_joke = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_daily_joke", mock_get_daily_joke)

  joke = models.PunnyJoke(
    key="joke123",
    setup_text="What do you call a fake noodle?",
    punchline_text="An Impasta!",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punchline.jpg",
  )
  mock_get_daily_joke.return_value = joke

  # Act
  with web_fns.app.test_client() as client:
    resp = client.get('/')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Today's Joke" in html
  assert "What do you call a fake noodle?" in html
  assert "An Impasta!" in html
  assert "Download on Google Play" in html
  assert 'Cache-Control' in resp.headers


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
  mock_get_daily_joke = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_daily_joke", mock_get_daily_joke)

  search_result = search.JokeSearchResult(
    joke=models.PunnyJoke(key="j3", setup_text="S", punchline_text="P"),
    vector_distance=0.03,
  )
  mock_search_jokes.return_value = [search_result]

  joke = models.PunnyJoke(
    key="j3",
    setup_text="S",
    punchline_text="P",
    setup_image_url="http://example.com/s3.jpg",
    punchline_image_url="http://example.com/p3.jpg",
  )
  mock_get_punny_jokes.return_value = [joke]
  daily_joke = models.PunnyJoke(
    key="daily1",
    setup_text="Daily setup",
    punchline_text="Daily punch",
    setup_image_url="http://example.com/d.jpg",
    punchline_image_url="http://example.com/pd.jpg",
  )
  mock_get_daily_joke.return_value = daily_joke

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

  # Background matches parchment color
  assert 'background: #f7f1e1' in topic_html
  assert 'background: #f7f1e1' in index_html
