"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

import pytest
from common import models
from functions import util_fns
from services import search


@pytest.fixture
def mock_search_jokes():
  """Fixture to mock the search.search_jokes function."""
  with patch('services.search.search_jokes') as mock:
    yield mock


@pytest.fixture
def mock_get_punny_joke():
  """Fixture to mock the firestore_service.get_punny_joke function."""
  with patch('services.firestore.get_punny_joke') as mock:
    yield mock


@pytest.fixture
def mock_update_punny_joke():
  """Fixture to mock the firestore_service.update_punny_joke function."""
  with patch('services.firestore.update_punny_joke') as mock:
    yield mock


def _create_fake_joke(
  joke_id: str,
  setup_text: str,
  punchline_text: str,
  seasonal: str | None,
) -> models.PunnyJoke:
  """Creates a fake PunnyJoke object for testing."""
  return models.PunnyJoke(
    key=joke_id,
    setup_text=setup_text,
    punchline_text=punchline_text,
    seasonal=seasonal,
  )


def _create_fake_search_result(joke: models.PunnyJoke) -> search.JokeSearchResult:
  """Creates a fake SearchResult object for testing."""
  return search.JokeSearchResult(joke=joke, vector_distance=0.1)


def test_seasonal_migration_updates_joke(
  mock_search_jokes: MagicMock,
  mock_get_punny_joke: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Test that a joke's seasonal field is updated to 'Halloween'."""
  joke1 = _create_fake_joke("j1", "Why did the scarecrow win an award?",
                            "Because he was outstanding in his field.", None)
  search_results = [_create_fake_search_result(joke1)]
  mock_search_jokes.return_value = search_results
  mock_get_punny_joke.return_value = joke1

  html_response = util_fns.run_seasonal_migration(
    query="scarecrow",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  mock_search_jokes.assert_called_once_with(
    query="scarecrow",
    label="seasonal_migration",
    limit=1000,
    distance_threshold=0.5,
  )
  mock_get_punny_joke.assert_called_once_with("j1")
  mock_update_punny_joke.assert_called_once_with("j1", {"seasonal": "Halloween"})
  assert "j1" in html_response
  assert "Updated Jokes (1)" in html_response


def test_seasonal_migration_dry_run_does_not_update(
  mock_search_jokes: MagicMock,
  mock_get_punny_joke: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Test that dry_run=True prevents any writes."""
  joke1 = _create_fake_joke("j1", "What do you get when you drop a pumpkin?",
                            "A squash.", "Fall")
  search_results = [_create_fake_search_result(joke1)]
  mock_search_jokes.return_value = search_results
  mock_get_punny_joke.return_value = joke1

  html_response = util_fns.run_seasonal_migration(
    query="pumpkin",
    threshold=0.5,
    dry_run=True,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "j1" in html_response
  assert "Updated Jokes (1)" in html_response
  assert "Dry Run: True" in html_response


def test_seasonal_migration_skips_already_halloween(
  mock_search_jokes: MagicMock,
  mock_get_punny_joke: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Test that a joke with seasonal='Halloween' is skipped."""
  joke1 = _create_fake_joke("j1", "What's a ghost's favorite dessert?",
                            "I-scream.", "Halloween")
  search_results = [_create_fake_search_result(joke1)]
  mock_search_jokes.return_value = search_results
  mock_get_punny_joke.return_value = joke1

  html_response = util_fns.run_seasonal_migration(
    query="ghost",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "j1" in html_response
  assert "Skipped Jokes (already Halloween) (1)" in html_response
  assert "Updated Jokes (0)" in html_response


def test_seasonal_migration_respects_max_jokes(
  mock_search_jokes: MagicMock,
  mock_get_punny_joke: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Test that the migration processes no more than max_jokes."""
  joke1 = _create_fake_joke("j1", "Joke 1", "Punchline 1", None)
  joke2 = _create_fake_joke("j2", "Joke 2", "Punchline 2", "Christmas")
  search_results = [
    _create_fake_search_result(joke1),
    _create_fake_search_result(joke2)
  ]
  mock_search_jokes.return_value = search_results
  mock_get_punny_joke.side_effect = [joke1, joke2]

  html_response = util_fns.run_seasonal_migration(
    query="any",
    threshold=0.5,
    dry_run=False,
    max_jokes=1,
  )

  assert mock_update_punny_joke.call_count == 1
  assert "Updated Jokes (1)" in html_response


def test_seasonal_migration_handles_no_results(
  mock_search_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Test that the migration handles empty search results gracefully."""
  mock_search_jokes.return_value = []

  html_response = util_fns.run_seasonal_migration(
    query="nonexistent",
    threshold=0.5,
    dry_run=False,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "No jokes were updated." in html_response
  assert "No jokes were skipped." in html_response
