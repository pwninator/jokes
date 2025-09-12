"""Tests for the web_fns module."""
from unittest.mock import MagicMock, Mock

from common import models
from functions import util_fns, web_fns
from services import search


def test_search_page_with_query_returns_jokes(monkeypatch):
  """Test that the search page returns jokes when a query is provided."""
  # Arrange
  mock_search_jokes = Mock()
  monkeypatch.setattr(web_fns.search, "search_jokes", mock_search_jokes)

  mock_get_punny_joke = Mock()
  monkeypatch.setattr(web_fns.firestore, "get_punny_joke", mock_get_punny_joke)

  # Mock the search results
  search_result = search.JokeSearchResult(joke=models.PunnyJoke(
    key="joke1", setup_text="s", punchline_text="p"),
                                          vector_distance=0.1)
  mock_search_jokes.return_value = [search_result]

  # Mock the firestore joke
  joke = models.PunnyJoke(
    key="joke1",
    setup_text="Why did the scarecrow win an award?",
    punchline_text="Because he was outstanding in his field.",
    setup_image_url="http://example.com/setup.jpg",
    punchline_image_url="http://example.com/punchline.jpg")
  mock_get_punny_joke.return_value = joke

  # Act
  with web_fns.app.test_client() as client:
    resp = client.get('/search?query=scarecrow')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Jokes for 'scarecrow'" in html
  assert "Why did the scarecrow win an award?" in html
  assert "Because he was outstanding in his field." in html
  assert "<img src='http://example.com/setup.jpg' width='200'>" in html
  assert "<img src='http://example.com/punchline.jpg' width='200'>" in html
  mock_search_jokes.assert_called_once_with(query="scarecrow",
                                            label="web_search",
                                            limit=10,
                                            field_filters=[])
  mock_get_punny_joke.assert_called_once_with("joke1")


def test_search_page_no_query_returns_prompt(monkeypatch):
  """Test that the search page returns a prompt when no query is provided."""
  # Act
  with web_fns.app.test_client() as client:
    resp = client.get('/search')

  # Assert
  assert resp.status_code == 200
  html = resp.get_data(as_text=True)
  assert "Please provide a 'query' parameter in the URL." in html
