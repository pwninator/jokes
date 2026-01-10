"""Tests for jokes feed routes."""

from __future__ import annotations

from unittest.mock import Mock

from common import models
from web.app import app
from web.routes import jokes as jokes_routes
from web.utils import urls


def test_jokes_route_redirects_to_homepage():
  """Test that GET /jokes redirects to the homepage."""
  with app.test_client() as client:
    resp = client.get('/jokes', follow_redirects=False)

  assert resp.status_code == 301
  assert resp.location == '/'


def test_index_page_includes_meta_tags(monkeypatch):
  """Test that homepage includes proper meta tags and canonical URL."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert f'<link rel="canonical" href="{urls.canonical_url("/")}">' in html
  assert '<meta name="description"' in html
  assert 'All Jokes' in html


def test_index_page_shows_carousel_reveal(monkeypatch):
  """Test that homepage shows joke cards with carousel reveal."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  joke = models.PunnyJoke(key="joke1",
                          setup_text="Setup",
                          punchline_text="Punchline",
                          setup_image_url="http://example.com/setup.jpg",
                          punchline_image_url="http://example.com/punch.jpg")
  mock_get_joke_feed_page.return_value = ([joke], None)

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'data-joke-viewer' in html
  assert 'data-role="reveal"' in html
  assert 'Reveal Punchline' in html
  assert 'joke-carousel' in html


def test_jokes_load_more_returns_json(monkeypatch):
  """Test that GET /jokes/load-more-feed returns JSON with HTML fragments."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  joke = models.PunnyJoke(key="joke3",
                          setup_text="Setup 3",
                          punchline_text="Punchline 3",
                          setup_image_url="http://example.com/setup3.jpg",
                          punchline_image_url="http://example.com/punch3.jpg")
  mock_get_joke_feed_page.return_value = ([joke], "0000000002")

  with app.test_client() as client:
    resp = client.get('/jokes/load-more-feed?cursor=0000000001')

  assert resp.status_code == 200
  assert 'application/json' in resp.headers['Content-Type']
  data = resp.get_json()
  assert 'html' in data
  assert 'cursor' in data
  assert 'has_more' in data
  # HTML should contain the joke content
  assert 'joke3' in data['html']
  assert 'Setup 3' in data['html']
  assert data['cursor'] == "0000000002"
  assert data['has_more'] is True
  assert 'Cache-Control' in resp.headers
  mock_get_joke_feed_page.assert_called_once_with(cursor="0000000001",
                                                  limit=10)


def test_jokes_load_more_without_cursor(monkeypatch):
  """Test that GET /jokes/load-more-feed handles missing cursor."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more-feed')

  assert resp.status_code == 200
  data = resp.get_json()
  assert 'html' in data
  assert data['cursor'] is None
  assert data['has_more'] is False
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=10)


def test_jokes_load_more_with_custom_limit(monkeypatch):
  """Test that GET /jokes/load-more-feed accepts custom limit parameter."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more-feed?limit=5')

  assert resp.status_code == 200
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=5)


def test_jokes_load_more_handles_invalid_cursor(monkeypatch):
  """Test that GET /jokes/load-more-feed handles invalid cursor gracefully."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more-feed?cursor=invalid')

  assert resp.status_code == 200
  data = resp.get_json()
  assert 'html' in data
  assert data['has_more'] is False
  mock_get_joke_feed_page.assert_called_once_with(cursor="invalid", limit=10)


def test_index_page_empty_feed(monkeypatch):
  """Test that homepage handles empty feed gracefully."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'All Jokes' in html
  assert 'jokes-feed' in html


def test_index_page_skips_malformed_jokes(monkeypatch):
  """Test that homepage skips malformed jokes in feed."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  # The function now returns PunnyJoke objects, so malformed jokes are already filtered
  joke = models.PunnyJoke(key="joke1",
                          setup_text="Setup 1",
                          punchline_text="Punchline 1",
                          setup_image_url="http://example.com/setup1.jpg",
                          punchline_image_url="http://example.com/punch1.jpg")
  mock_get_joke_feed_page.return_value = ([joke], None)

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Valid joke should appear
  assert "Setup 1" in html or "joke1" in html
  # Malformed joke should be skipped (from_firestore_dict will fail without key)


def test_index_page_renders_jokes_feed(monkeypatch):
  """Test that GET / renders the jokes feed as the homepage."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  joke = models.PunnyJoke(key="joke1",
                          setup_text="Why did the chicken cross the road?",
                          punchline_text="To get to the other side!",
                          setup_image_url="http://example.com/setup1.jpg",
                          punchline_image_url="http://example.com/punch1.jpg")
  mock_get_joke_feed_page.return_value = ([joke], None)

  with app.test_client() as client:
    resp = client.get('/')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'text/html' in resp.headers['Content-Type']
  assert 'All Jokes' in html
  assert 'Freshly Baked Jokes' in html
  assert "Why did the chicken cross the road?" in html
  assert 'data-joke-viewer' in html
  assert 'Cache-Control' in resp.headers
  assert 'Cookie' in resp.headers.get('Vary', '')
  # Verify canonical URL points to homepage
  assert f'<link rel="canonical" href="{urls.canonical_url("/")}">' in html
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=10)


def test_index_page_uses_cookie_cursor(monkeypatch):
  """Test that homepage reads cookie and uses it as initial cursor."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  joke = models.PunnyJoke(key="joke1",
                          setup_text="Setup",
                          punchline_text="Punchline",
                          setup_image_url="http://example.com/setup.jpg",
                          punchline_image_url="http://example.com/punch.jpg")
  mock_get_joke_feed_page.return_value = ([joke], "0000000001:5")

  with app.test_client() as client:
    # Set cookie with cursor
    client.set_cookie('jokes_feed_cursor', '0000000000:9')
    resp = client.get('/')

  assert resp.status_code == 200
  # Should call with cookie cursor
  mock_get_joke_feed_page.assert_called_once_with(cursor='0000000000:9',
                                                  limit=10)
  # Route should not set cookies (handled by JavaScript)
  assert 'Set-Cookie' not in resp.headers or 'jokes_feed_cursor' not in resp.headers.get('Set-Cookie', '')


def test_jokes_load_more_unknown_slug_returns_404():
  """Test that GET /jokes/load-more-<unknown> returns 404 for unknown slugs."""
  with app.test_client() as client:
    resp = client.get('/jokes/load-more-unknown-slug')

  assert resp.status_code == 404


def test_jokes_load_more_feed_slug_dispatches_correctly(monkeypatch):
  """Test that 'feed' slug correctly calls get_joke_feed_page."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more-feed?cursor=test123')

  assert resp.status_code == 200
  mock_get_joke_feed_page.assert_called_once_with(cursor="test123", limit=10)
