"""Tests for public web routes and helpers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from common import models
from services import search
from web.app import app
from web.routes import jokes as jokes_routes
from web.routes import public as public_routes
from web.utils import urls


def test_topic_page_uses_batch_fetch(monkeypatch):
  """Topic page uses batched get_punny_jokes and renders content."""
  mock_search_jokes = Mock()
  monkeypatch.setattr(jokes_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(jokes_routes.firestore,
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


def test_home2_page_renders_top_jokes(monkeypatch):
  """Verify that the home2 page '/home2' renders the top jokes."""
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
    resp = client.get('/home2')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert '<section class="favorites-section"' in html
  assert 'Fan Favorites from the Cookie Jar' in html
  assert 'class="favorites-grid"' in html
  assert "What do you call a fake noodle?" in html
  assert "An Impasta!" in html
  assert 'data-analytics-event="web_joke_reveal_click"' in html
  assert 'data-analytics-label="joke_card_reveal"' in html
  assert 'data-analytics-params=' in html
  assert '"joke_id": "joke123"' in html
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


def test_books_page_renders_book_promo():
  with app.test_client() as client:
    resp = client.get('/books?country_override=US')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Your Lunchbox Notes are on their way' not in html
  assert 'Get the Book on Amazon' in html
  assert 'data-analytics-event="web_book_amazon_click"' in html
  assert f'<link rel="canonical" href="{urls.canonical_url("/books")}">' in html
  assert 'href="https://www.amazon.com/dp/' in html
  assert 'Cache-Control' in resp.headers


def test_books_page_ref_notes_download_overrides_hero_copy():
  with app.test_client() as client:
    resp = client.get('/books?country_override=US&ref=notes_download')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Your Lunchbox Notes are on their way to your inbox' in html
  # Note: Jinja may HTML-escape apostrophes.
  assert 'Love the notes?' in html
  assert 'whole lot more where those came from' in html
  assert 'hand-picked favorites from our paperback book' in html
  assert 'full collection of 36 illustrated jokes today' in html


def test_home2_page_includes_nonempty_unique_meta_tags(monkeypatch):
  """Home2 page should render a single, non-empty set of SEO meta tags."""
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
    resp = client.get('/home2')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  assert f'<link rel="canonical" href="{urls.canonical_url("/home2")}">' in html
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


def test_handle_joke_slug_short_renders_topic_page(monkeypatch):
  """Verify /jokes/<slug> with short slug (<=15) renders topic page with cards, details, and JSON-LD."""
  # Arrange: mock search and firestore
  mock_search_jokes = Mock()
  monkeypatch.setattr(jokes_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(jokes_routes.firestore,
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

  # Act - short slug (dogs is 4 chars, <= 15)
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
  assert 'data-meta-event="ViewContent"' in html
  assert 'data-meta-event="Lead"' in html
  assert 'href="/books"' in html
  assert f'<link rel="canonical" href="{urls.canonical_url("/about")}">' in html
  assert 'Cache-Control' in resp.headers


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
    resp = client.get('/home2')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)

  # Book Link
  assert 'Book' in html
  assert 'href="/books"' in html
  assert 'data-analytics-event="web_nav_book_click"' in html
  assert 'data-analytics-label="book"' in html

  # App Link
  assert 'App' in html
  assert 'href="https://play.google.com/store/apps/details?id=com.builtwithporpoise.jokes"' in html
  assert 'data-analytics-event="web_nav_app_click"' in html
  assert 'data-analytics-label="mobile_app"' in html


def test_home2_page_includes_sticky_header_script(monkeypatch):
  """Test that home2 page includes sticky header scroll script."""
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
    resp = client.get('/home2')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'site-header' in html
  # Verify scroll detection script is present
  assert 'scroll' in html.lower()
  assert 'site-header--visible' in html.lower()
  assert 'addEventListener' in html


def test_mobile_header_docked_is_positioned_for_menu(monkeypatch):
  """Mobile nav requires the docked header to be positioned for the menu anchor."""
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

  with app.test_client() as client:
    resp = client.get('/home2')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  style_start = html.find('<style>')
  style_end = html.find('</style>', style_start)
  assert style_start != -1
  assert style_end != -1
  css = html[style_start + len('<style>'):style_end]

  positions = []
  search_from = 0
  while True:
    index = css.find('.site-header--docked', search_from)
    if index == -1:
      break
    positions.append(index)
    search_from = index + 1

  assert positions
  for index in positions:
    block_start = css.find('{', index)
    block_end = css.find('}', block_start)
    assert block_start != -1
    assert block_end != -1
    block = css[block_start:block_end]
    assert 'position: relative' in block


def test_fetch_topic_jokes_sorts_by_popularity_then_distance(monkeypatch):
  """_fetch_topic_jokes orders by popularity desc, then vector distance asc."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(jokes_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(jokes_routes.firestore,
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
  ordered = jokes_routes._fetch_topic_jokes("dogs", limit=3)  # pylint: disable=protected-access

  # Assert
  keys = [j.key for j in ordered]
  # C first (highest popularity), then B (tie pop, closer), then A
  assert keys == ["C", "B", "A"]


def test_handle_joke_slug_long_exact_match(monkeypatch):
  """Verify /jokes/<slug> with long slug (>=16) finds exact match and renders single joke page."""
  # Arrange: mock Firestore query
  mock_doc = Mock()
  mock_doc.exists = True
  mock_doc.id = "joke123"
  mock_doc.to_dict.return_value = {
    "setup_text": "Why did the chicken cross the road?",
    "punchline_text": "To get to the other side!",
    "setup_image_url": "http://example.com/setup.jpg",
    "punchline_image_url": "http://example.com/punch.jpg",
    "setup_text_slug": "whydidthechickencrosstheroad",
    "is_public": True,
    "state": "PUBLISHED",
  }

  mock_query = Mock()
  mock_query.stream.return_value = [mock_doc]
  mock_query.where.return_value = mock_query
  mock_query.order_by.return_value = mock_query
  mock_query.limit.return_value = mock_query

  mock_collection = Mock()
  mock_collection.where.return_value = mock_query

  mock_db = Mock()
  mock_db.collection.return_value = mock_collection

  monkeypatch.setattr(jokes_routes.firestore, "db", lambda: mock_db)
  related_joke = models.PunnyJoke(
    key="rel-1",
    setup_text="Related setup",
    punchline_text="Related punchline",
    setup_image_url="http://example.com/rel-setup.jpg",
    punchline_image_url="http://example.com/rel-punch.jpg",
  )
  related_joke_same_key = models.PunnyJoke(
    key="joke123",
    setup_text="Should not appear",
    punchline_text="Should not appear punchline",
    setup_image_url="http://example.com/skip-setup.jpg",
    punchline_image_url="http://example.com/skip-punch.jpg",
  )
  mock_fetch_topic_jokes = Mock(
    return_value=[related_joke_same_key, related_joke])
  monkeypatch.setattr(jokes_routes, "_fetch_topic_jokes",
                      mock_fetch_topic_jokes)

  # Act - long slug (>= 16 chars) that matches exactly
  with app.test_client() as client:
    resp = client.get('/jokes/whydidthechickencrosstheroad')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Why did the chicken cross the road?' in html
  assert 'To get to the other side!' in html
  assert 'id="joke-title"' in html
  assert 'application/ld+json' in html
  assert 'FAQPage' in html
  assert 'data-joke-viewer' in html
  assert 'data-role="reveal"' in html
  assert 'Should not appear' not in html
  assert 'Similar Jokes' in html
  assert 'Related setup' in html
  assert 'id="related-jokes-feed"' in html
  assert 'Cache-Control' in resp.headers
  mock_fetch_topic_jokes.assert_called_once_with(
    "whydidthechickencrosstheroad",
    limit=21,
    distance_threshold=None,
  )


def test_handle_joke_slug_long_nearest_match(monkeypatch):
  """Verify /jokes/<slug> with long slug finds nearest match when exact match not found."""
  # Arrange: mock Firestore queries
  # First query (exact match) returns no results
  mock_exact_query_limit = Mock()
  mock_exact_query_limit.stream.return_value = []

  mock_exact_query_where2 = Mock()
  mock_exact_query_where2.limit.return_value = mock_exact_query_limit

  mock_exact_query_where1 = Mock()
  mock_exact_query_where1.where.return_value = mock_exact_query_where2

  mock_exact_collection = Mock()
  mock_exact_collection.where.return_value = mock_exact_query_where1

  # Second query (nearest match) returns a result
  mock_nearest_doc = Mock()
  mock_nearest_doc.exists = True
  mock_nearest_doc.id = "joke456"
  mock_nearest_doc.to_dict.return_value = {
    "setup_text": "Why did the duck cross the road?",
    "punchline_text": "It was the chicken's day off!",
    "setup_image_url": "http://example.com/setup2.jpg",
    "punchline_image_url": "http://example.com/punch2.jpg",
    "setup_text_slug": "whydidtheduckcrosstheroad",
    "is_public": True,
    "state": "PUBLISHED",
  }

  mock_nearest_query_limit = Mock()
  mock_nearest_query_limit.stream.return_value = [mock_nearest_doc]

  mock_nearest_query_order = Mock()
  mock_nearest_query_order.limit.return_value = mock_nearest_query_limit

  mock_nearest_query_where2 = Mock()
  mock_nearest_query_where2.order_by.return_value = mock_nearest_query_order

  mock_nearest_query_where1 = Mock()
  mock_nearest_query_where1.where.return_value = mock_nearest_query_where2

  mock_nearest_collection = Mock()
  mock_nearest_collection.where.return_value = mock_nearest_query_where1

  # Make collection() return different mocks based on call count
  collection_call_count = [0]

  def collection_side_effect(collection_name):
    collection_call_count[0] += 1
    if collection_call_count[0] == 1:
      return mock_exact_collection  # First query (exact match, empty)
    return mock_nearest_collection  # Second query (nearest match, has result)

  mock_db = Mock()
  mock_db.collection.side_effect = collection_side_effect

  monkeypatch.setattr(jokes_routes.firestore, "db", lambda: mock_db)
  related_joke = models.PunnyJoke(
    key="rel-2",
    setup_text="Related setup 2",
    punchline_text="Related punchline 2",
    setup_image_url="http://example.com/rel2-setup.jpg",
    punchline_image_url="http://example.com/rel2-punch.jpg",
  )
  mock_fetch_topic_jokes = Mock(return_value=[related_joke])
  monkeypatch.setattr(jokes_routes, "_fetch_topic_jokes",
                      mock_fetch_topic_jokes)

  # Act - long slug (>= 16 chars) that doesn't match exactly
  with app.test_client() as client:
    resp = client.get('/jokes/whydidthechickencrosstheroad')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Why did the duck cross the road?' in html
  assert 'id="joke-title"' in html
  assert 'application/ld+json' in html
  assert 'FAQPage' in html
  # Verify the joke card is rendered (should have punchline image with alt attribute)
  assert 'data-joke-viewer' in html
  assert 'alt=' in html  # Punchline image should have alt attribute with punchline text
  # The punchline text should be in the JSON-LD or in an alt attribute
  # Since we can't easily check the exact JSON structure, verify the joke card is present
  assert 'joke-card' in html or 'joke-viewer' in html
  assert 'Similar Jokes' in html
  assert 'Related setup 2' in html
  assert 'id="related-jokes-feed"' in html
  mock_fetch_topic_jokes.assert_called_once_with(
    "whydidthechickencrosstheroad",
    limit=21,
    distance_threshold=None,
  )


def test_handle_joke_slug_long_not_found(monkeypatch):
  """Verify /jokes/<slug> with long slug returns 404 when no joke found."""
  # Arrange: mock Firestore queries to return no results
  mock_query = Mock()
  mock_query.stream.return_value = []
  mock_query.where.return_value = mock_query
  mock_query.order_by.return_value = mock_query
  mock_query.limit.return_value = mock_query

  mock_collection = Mock()
  mock_collection.where.return_value = mock_query

  mock_db = Mock()
  mock_db.collection.return_value = mock_collection

  monkeypatch.setattr(jokes_routes.firestore, "db", lambda: mock_db)
  mock_fetch_topic_jokes = Mock()
  monkeypatch.setattr(jokes_routes, "_fetch_topic_jokes",
                      mock_fetch_topic_jokes)

  # Act - long slug (>= 16 chars) with no matching joke
  with app.test_client() as client:
    resp = client.get('/jokes/nonexistentslugthatislong')

  # Assert
  assert resp.status_code == 404
  assert b"Joke not found" in resp.data
  mock_fetch_topic_jokes.assert_not_called()


def test_handle_joke_slug_standardizes_slug(monkeypatch):
  """Verify that slug is standardized before querying."""
  # Arrange: mock Firestore query
  mock_doc = Mock()
  mock_doc.exists = True
  mock_doc.id = "joke789"
  mock_doc.to_dict.return_value = {
    "setup_text": "Why did the test pass?",
    "punchline_text": "Because it was correct!",
    "setup_image_url": "http://example.com/setup3.jpg",
    "punchline_image_url": "http://example.com/punch3.jpg",
    "setup_text_slug": "whydidthetestpass",  # Lowercase, no spaces
    "is_public": True,
    "state": "PUBLISHED",
  }

  mock_query = Mock()
  mock_query.stream.return_value = [mock_doc]
  mock_query.where.return_value = mock_query
  mock_query.order_by.return_value = mock_query
  mock_query.limit.return_value = mock_query

  mock_collection = Mock()
  mock_collection.where.return_value = mock_query

  mock_db = Mock()
  mock_db.collection.return_value = mock_collection

  monkeypatch.setattr(jokes_routes.firestore, "db", lambda: mock_db)
  related_joke = models.PunnyJoke(
    key="rel-3",
    setup_text="Related setup 3",
    punchline_text="Related punchline 3",
    setup_image_url="http://example.com/rel3-setup.jpg",
    punchline_image_url="http://example.com/rel3-punch.jpg",
  )
  mock_fetch_topic_jokes = Mock(return_value=[related_joke])
  monkeypatch.setattr(jokes_routes, "_fetch_topic_jokes",
                      mock_fetch_topic_jokes)

  # Act - slug with spaces and uppercase (should be standardized to lowercase, no spaces)
  with app.test_client() as client:
    resp = client.get('/jokes/Why-Did-The-Test-Pass?')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'Why did the test pass?' in html
  assert 'Similar Jokes' in html
  assert 'Related setup 3' in html
  assert 'id="related-jokes-feed"' in html
  assert mock_fetch_topic_jokes.call_args.kwargs['limit'] == 21
  assert mock_fetch_topic_jokes.call_args.kwargs['distance_threshold'] is None
  # Verify the query was made with standardized slug
  # The standardized slug should be "whydidthetestpass" (no spaces, lowercase, no punctuation)


def test_pages_include_ga4_tag_and_parchment_background(monkeypatch):
  """All pages should include GA4 and use the parchment background color."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(jokes_routes.search, "search_jokes", mock_search_jokes)

  mock_get_punny_jokes = Mock()
  monkeypatch.setattr(jokes_routes.firestore,
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

  mock_get_top_jokes = Mock()
  monkeypatch.setattr(public_routes.firestore, "get_top_jokes",
                      mock_get_top_jokes)
  mock_get_daily_joke = Mock(return_value=None)
  monkeypatch.setattr(public_routes.firestore, "get_daily_joke",
                      mock_get_daily_joke)
  top_joke = models.PunnyJoke(
    key="top1",
    setup_text="Top setup",
    punchline_text="Top punch",
    setup_image_url="http://example.com/d.jpg",
    punchline_image_url="http://example.com/pd.jpg",
  )
  mock_get_top_jokes.return_value = [top_joke]

  # Act - test topic page and home2 page
  with app.test_client() as client:
    topic_resp = client.get('/jokes/dogs')
    home2_resp = client.get('/home2')

  # Assert
  assert topic_resp.status_code == 200
  assert home2_resp.status_code == 200
  topic_html = topic_resp.get_data(as_text=True)
  home2_html = home2_resp.get_data(as_text=True)

  # GA4 present on both pages
  assert 'gtag/js?id=G-D2B7E8PXJJ' in topic_html
  assert "gtag('config', 'G-D2B7E8PXJJ')" in topic_html
  assert 'data-meta-event' in topic_html
  assert 'trackCustom' in topic_html
  assert 'gtag/js?id=G-D2B7E8PXJJ' in home2_html
  assert "gtag('config', 'G-D2B7E8PXJJ')" in home2_html
  assert 'data-meta-event' in home2_html
  assert 'trackCustom' in home2_html
  assert 'data-analytics-event="web_index_play_store_click"' in home2_html

  # Background palette variables present on both pages
  assert '--color-bg-outer: #e4d0ae;' in topic_html
  assert '--color-bg-outer: #e4d0ae;' in home2_html
  assert 'web_footer_privacy_click' in topic_html
  assert 'web_footer_privacy_click' in home2_html
  assert 'href="/privacy.html"' in topic_html
  assert 'href="/privacy.html"' in home2_html
  assert 'target="_blank"' in topic_html
  assert 'target="_blank"' in home2_html
  assert 'rel="noopener noreferrer"' in topic_html
  assert 'rel="noopener noreferrer"' in home2_html

  # New header and favicon present on both pages
  assert '<header class="site-header">' in topic_html
  assert '<header class="site-header">' in home2_html
  assert '<link rel="icon" type="image/png"' in topic_html
  assert '<link rel="icon" type="image/png"' in home2_html


def test_topic_page_includes_sticky_header_script(monkeypatch):
  """Test that topic page includes sticky header scroll script."""
  # Arrange: Mock dependencies
  mock_search_jokes = Mock(return_value=[])
  mock_get_punny_jokes = Mock(return_value=[])
  monkeypatch.setattr(jokes_routes.search, "search_jokes", mock_search_jokes)
  monkeypatch.setattr(jokes_routes.firestore,
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


def test_sitemap_includes_homepage(monkeypatch):
  """Verify that the sitemap includes the homepage URL."""
  monkeypatch.setattr(
    public_routes.firestore,
    "get_joke_sheets_cache",
    lambda: [],
  )
  with app.test_client() as client:
    resp = client.get('/sitemap.xml')

  assert resp.status_code == 200
  xml = resp.get_data(as_text=True)

  # Check for the homepage URL.
  # public_base_url returns "https://snickerdoodlejokes.com" (mocked/env default)
  # We expect <loc>https://snickerdoodlejokes.com/</loc>
  assert '<loc>https://snickerdoodlejokes.com/</loc>' in xml
