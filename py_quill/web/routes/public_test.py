"""Tests for public web routes and helpers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from common import models
from services import search
from web.app import app
from web.routes import public as public_routes
from web.utils import urls


def test_topic_page_uses_batch_fetch(monkeypatch):
  """Topic page uses batched get_punny_jokes and renders content."""
  mock_search_jokes = Mock()
  monkeypatch.setattr(public_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore,
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

  with app.test_client() as client:
    resp = client.get('/jokes/dogs')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Default header brand should be clickable on standard pages.
  assert '<a class="brand" href="' in html
  assert 'application/ld+json' in html
  assert "Why did the scarecrow win an award?" in html
  assert "Because he was outstanding in his field." in html
  mock_get_punny_jokes.assert_called_once_with(["joke1"])


def test_sitemap_returns_hardcoded_topics(monkeypatch):
  monkeypatch.setattr(
    public_routes.firestore,
    "get_joke_sheets_cache",
    lambda: [
      (
        models.JokeCategory(id="animals", display_name="Animals"),
        [
          models.JokeSheet(category_id="animals", index=0),
          models.JokeSheet(category_id="animals", index=1),
        ],
      ),
      (
        models.JokeCategory(id="space", display_name="Space"),
        [models.JokeSheet(category_id="space", index=0)],
      ),
    ],
  )
  with app.test_client() as client:
    resp = client.get('/sitemap.xml')
  assert resp.status_code == 200
  xml = resp.get_data(as_text=True)
  assert 'https://snickerdoodlejokes.com/printables/notes' in xml
  assert 'https://snickerdoodlejokes.com/printables/notes/free-animals-jokes-1' in xml
  assert 'https://snickerdoodlejokes.com/printables/notes/free-animals-jokes-2' in xml
  assert 'https://snickerdoodlejokes.com/printables/notes/free-space-jokes-1' in xml
  assert 'https://snickerdoodlejokes.com/jokes/dogs' in xml


def test_topic_page_renders_with_json_ld_and_reveal(monkeypatch):
  """Verify /jokes/<topic> renders cards, details, and JSON-LD."""
  # Arrange: mock search and firestore
  mock_search_jokes = Mock()
  monkeypatch.setattr(public_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore,
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
  with app.test_client() as client:
    resp = client.get('/jokes/dogs')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<h1>Dogs jokes</h1>' in html
  assert f'<link rel="canonical" href="{urls.canonical_url("/jokes/dogs")}">' in html
  assert 'application/ld+json' in html
  assert 'FAQPage' in html
  # Topic page uses carousel reveal style (default)
  assert 'data-joke-viewer' in html
  assert 'data-role="reveal"' in html
  assert 'Reveal punchline' in html
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
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)

  joke = models.PunnyJoke(
    key="joke123",
    setup_text="What do you call a fake noodle?",
    punchline_text="An Impasta!",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punchline.jpg",
  )
  mock_get_top_jokes.return_value = [joke]

  # Act
  with app.test_client() as client:
    resp = client.get('/')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'href="/"' in html
  assert 'Home' in html
  assert 'href="/printables/notes"' in html
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
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  mock_get_daily_joke = Mock()
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)

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

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  assert f'<link rel="canonical" href="{urls.canonical_url("/")}">' in html
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


def test_about_page_renders_family_story():
  """About page should render the family story and hero image."""
  with app.test_client() as client:
    resp = client.get('/about')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'id="about-title"' in html
  assert 'aria-labelledby="team-title"' in html
  assert 'aria-labelledby="mission-title"' in html
  assert 'class="hero-card"' in html
  assert 'class="notes-card-grid"' in html
  assert html.count('class="notes-card"') == 3
  assert 'href="/printables/notes"' in html
  assert 'family_kneel_meadow.png' in html
  assert 'width="480"' in html
  assert 'height="480"' in html
  assert 'loading="lazy"' in html
  assert 'maas_adg_67CA692EED615032D6E3E602791A40E5' in html
  assert f'<link rel="canonical" href="{urls.canonical_url("/about")}">' in html
  assert 'Cache-Control' in resp.headers


def test_fetch_topic_jokes_sorts_by_popularity_then_distance(monkeypatch):
  """_fetch_topic_jokes orders by popularity desc, then vector distance asc."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(public_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore,
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
  ordered = public_routes._fetch_topic_jokes("dogs", limit=3)  # pylint: disable=protected-access

  # Assert
  keys = [j.key for j in ordered]
  # C first (highest popularity), then B (tie pop, closer), then A
  assert keys == ["C", "B", "A"]


def test_pages_include_ga4_tag_and_parchment_background(monkeypatch):
  """All pages should include GA4 and use the parchment background color."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(public_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)
  mock_get_top_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)

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
  with app.test_client() as client:
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


def test_nav_includes_book_and_app_links(monkeypatch):
  """Navigation should include links to Book and App with analytics."""
  # Arrange
  mock_get_top_jokes = Mock(return_value=[
    models.PunnyJoke(key="j1", setup_text="s", punchline_text="p")
  ])
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)

  # Act
  with app.test_client() as client:
    resp = client.get('/')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  # Book Link
  assert 'Book' in html
  assert 'href="https://www.amazon.com/dp/' in html
  assert 'data-analytics-event="web_nav_book_click"' in html
  assert 'data-analytics-label="book"' in html
  # We check target="_blank" generally, but can be specific if needed.
  # The link structure is verified by the template, here we verify key attributes exist together.

  # App Link
  assert 'App' in html
  assert 'href="https://play.google.com/store/apps/details?id=com.builtwithporpoise.jokes"' in html
  assert 'data-analytics-event="web_nav_app_click"' in html
  assert 'data-analytics-label="mobile_app"' in html


def test_index_page_includes_sticky_header_script(monkeypatch):
  """Test that index page includes sticky header scroll script."""
  # Arrange: Mock dependencies
  joke = models.PunnyJoke(
    key="joke1",
    setup_text="Setup",
    punchline_text="Punchline",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punch.jpg",
  )
  mock_get_top_jokes = Mock(return_value=[joke])
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)

  # Act
  with app.test_client() as client:
    resp = client.get('/')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'site-header' in html
  # Verify scroll detection script is present
  assert 'scroll' in html.lower()
  assert 'site-header--visible' in html.lower()
  assert 'addEventListener' in html


def test_topic_page_includes_sticky_header_script(monkeypatch):
  """Test that topic page includes sticky header scroll script."""
  # Arrange: Mock dependencies
  mock_search_jokes = Mock(return_value=[])
  mock_get_punny_jokes = Mock(return_value=[])
  monkeypatch.setattr(public_routes.search, "search_jokes", mock_search_jokes)
  monkeypatch.setattr(public_routes.firestore,
                      "get_punny_jokes",
                      mock_get_punny_jokes,
                      raising=False)

  # Act
  with app.test_client() as client:
    resp = client.get('/jokes/dogs')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'site-header' in html
  # Verify scroll detection script is present
  assert 'scroll' in html.lower()
  assert 'site-header--visible' in html.lower()
  assert 'addEventListener' in html