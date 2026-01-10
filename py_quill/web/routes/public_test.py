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

  # Act - test topic page only (index route moved to jokes.py)
  with app.test_client() as client:
    topic_resp = client.get('/jokes/dogs')

  # Assert
  assert topic_resp.status_code == 200
  topic_html = topic_resp.get_data(as_text=True)

  # GA4 present
  assert 'gtag/js?id=G-D2B7E8PXJJ' in topic_html
  assert "gtag('config', 'G-D2B7E8PXJJ')" in topic_html

  # Background palette variables present
  assert '--color-bg-outer: #e4d0ae;' in topic_html
  assert 'web_footer_privacy_click' in topic_html
  assert 'href="/privacy.html"' in topic_html
  assert 'target="_blank"' in topic_html
  assert 'rel="noopener noreferrer"' in topic_html

  # New header and favicon present
  assert '<header class="site-header">' in topic_html
  assert '<link rel="icon" type="image/png"' in topic_html


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
  assert 'addEventListener' in html
  # Verify dock/floating state classes are referenced
  assert 'site-header--docked' in html.lower()
  assert 'site-header--floating' in html.lower()
  assert 'site-header--visible' in html.lower()
  # Verify 1000px scroll threshold logic
  assert '1000' in html or 'float_scroll_threshold' in html.lower()
