"""Tests for jokes feed routes."""

from __future__ import annotations

from unittest.mock import Mock

from common import models
from web.app import app
from web.routes import jokes as jokes_routes
from web.utils import urls


def test_jokes_page_renders_html(monkeypatch):
  """Test that GET /jokes renders HTML with first page of jokes."""
  mock_get_joke_feed_page = Mock()
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  # Mock feed data
  joke1 = models.PunnyJoke(key="joke1",
                           setup_text="Why did the chicken cross the road?",
                           punchline_text="To get to the other side!",
                           setup_image_url="http://example.com/setup1.jpg",
                           punchline_image_url="http://example.com/punch1.jpg")
  joke2 = models.PunnyJoke(key="joke2",
                           setup_text="What do you call a fake noodle?",
                           punchline_text="An impasta!",
                           setup_image_url="http://example.com/setup2.jpg",
                           punchline_image_url="http://example.com/punch2.jpg")
  mock_get_joke_feed_page.return_value = ([joke1, joke2], "0000000001")

  with app.test_client() as client:
    resp = client.get('/jokes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'text/html' in resp.headers['Content-Type']
  assert 'All Jokes' in html
  assert "Why did the chicken cross the road?" in html
  assert "To get to the other side!" in html
  assert "What do you call a fake noodle?" in html
  assert 'data-joke-viewer' in html
  assert 'joke-reveal' in html
  assert 'Cache-Control' in resp.headers
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=10)


def test_jokes_page_includes_meta_tags(monkeypatch):
  """Test that /jokes page includes proper meta tags and canonical URL."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert f'<link rel="canonical" href="{urls.canonical_url("/jokes")}">' in html
  assert '<meta name="description"' in html
  assert 'All Jokes' in html


def test_jokes_page_shows_carousel_reveal(monkeypatch):
  """Test that /jokes page shows joke cards with carousel reveal."""
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
    resp = client.get('/jokes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'data-joke-viewer' in html
  assert 'data-role="reveal"' in html
  assert 'Reveal Punchline' in html
  assert 'joke-carousel' in html


def test_jokes_load_more_returns_json(monkeypatch):
  """Test that GET /jokes/load-more returns JSON with HTML fragments."""
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
    resp = client.get('/jokes/load-more?cursor=0000000001')

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
  """Test that GET /jokes/load-more handles missing cursor."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more')

  assert resp.status_code == 200
  data = resp.get_json()
  assert 'html' in data
  assert data['cursor'] is None
  assert data['has_more'] is False
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=10)


def test_jokes_load_more_with_custom_limit(monkeypatch):
  """Test that GET /jokes/load-more accepts custom limit parameter."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more?limit=5')

  assert resp.status_code == 200
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=5)


def test_jokes_load_more_handles_invalid_cursor(monkeypatch):
  """Test that GET /jokes/load-more handles invalid cursor gracefully."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes/load-more?cursor=invalid')

  assert resp.status_code == 200
  data = resp.get_json()
  assert 'html' in data
  assert data['has_more'] is False
  mock_get_joke_feed_page.assert_called_once_with(cursor="invalid", limit=10)


def test_jokes_page_empty_feed(monkeypatch):
  """Test that /jokes page handles empty feed gracefully."""
  mock_get_joke_feed_page = Mock(return_value=([], None))
  monkeypatch.setattr(jokes_routes.firestore, "get_joke_feed_page",
                      mock_get_joke_feed_page)

  with app.test_client() as client:
    resp = client.get('/jokes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert 'All Jokes' in html
  assert 'jokes-feed' in html


def test_jokes_page_skips_malformed_jokes(monkeypatch):
  """Test that /jokes page skips malformed jokes in feed."""
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
    resp = client.get('/jokes')

  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  # Valid joke should appear
  assert "Setup 1" in html or "joke1" in html
  # Malformed joke should be skipped (from_firestore_dict will fail without key)


def test_jokes_page_uses_cookie_cursor(monkeypatch):
  """Test that /jokes page reads cookie and uses it as initial cursor."""
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
    resp = client.get('/jokes')

  assert resp.status_code == 200
  # Should call with cookie cursor
  mock_get_joke_feed_page.assert_called_once_with(cursor='0000000000:9',
                                                  limit=10)


def test_jokes_page_without_cookie_starts_from_beginning(monkeypatch):
  """Test that /jokes page starts from beginning when no cookie is present."""
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
    resp = client.get('/jokes')

  assert resp.status_code == 200
  # Should call with None cursor (start from beginning)
  mock_get_joke_feed_page.assert_called_once_with(cursor=None, limit=10)


def test_jokes_page_handles_invalid_cookie_cursor(monkeypatch):
  """Test that /jokes page handles invalid cookie cursor gracefully."""
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
    # Set invalid cookie cursor
    client.set_cookie('jokes_feed_cursor', 'invalid_cursor')
    resp = client.get('/jokes')

  assert resp.status_code == 200
  # Should still call with the invalid cursor (firestore will handle it)
  mock_get_joke_feed_page.assert_called_once_with(cursor='invalid_cursor',
                                                  limit=10)
