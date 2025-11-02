"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

import pytest
from common import models
from functions import util_fns
from functions.joke_auto_fns import MIN_VIEWS_FOR_FRACTIONS


@pytest.fixture(name='mock_get_all_punny_jokes')
def mock_get_all_punny_jokes_fixture():
  """Fixture to mock the firestore_service.get_all_punny_jokes function."""
  with patch('services.firestore.get_all_punny_jokes') as mock:
    yield mock


@pytest.fixture(name='mock_update_punny_joke')
def mock_update_punny_joke_fixture():
  """Fixture to mock the firestore_service.update_punny_joke function."""
  with patch('services.firestore.update_punny_joke') as mock:
    yield mock


def _create_fake_joke(
  joke_id: str,
  *,
  num_viewed_users: int,
  num_saved_users_fraction: float,
) -> models.PunnyJoke:
  """Creates a fake PunnyJoke object for testing."""
  return models.PunnyJoke(
    key=joke_id,
    setup_text=f"Setup for {joke_id}",
    punchline_text=f"Punchline for {joke_id}",
    num_viewed_users=num_viewed_users,
    num_saved_users_fraction=num_saved_users_fraction,
  )


def test_saved_fraction_migration_updates_low_view_joke(
  mock_get_all_punny_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Jokes with low views should be reset when the fraction is non-zero."""
  joke = _create_fake_joke(
    "j1",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS - 1,
    num_saved_users_fraction=0.4,
  )
  mock_get_all_punny_jokes.return_value = [joke]

  html_response = util_fns.run_saved_fraction_migration(
    dry_run=False,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_called_once_with(
    "j1", {"num_saved_users_fraction": 0.0})
  assert "Updated Jokes (1)" in html_response
  assert "Dry Run: False" in html_response


def test_saved_fraction_migration_dry_run(
  mock_get_all_punny_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Dry run should not write to Firestore but report planned updates."""
  joke = _create_fake_joke(
    "j1",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS - 1,
    num_saved_users_fraction=0.2,
  )
  mock_get_all_punny_jokes.return_value = [joke]

  html_response = util_fns.run_saved_fraction_migration(
    dry_run=True,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "Updated Jokes (1)" in html_response
  assert "Dry Run: True" in html_response


def test_saved_fraction_migration_skips_when_fraction_already_zero(
  mock_get_all_punny_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Jokes already at zero fraction should be skipped."""
  joke = _create_fake_joke(
    "j1",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS - 1,
    num_saved_users_fraction=0.0,
  )
  mock_get_all_punny_jokes.return_value = [joke]

  html_response = util_fns.run_saved_fraction_migration(
    dry_run=False,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "Updated Jokes (0)" in html_response
  assert "reason=already_zero" in html_response


def test_saved_fraction_migration_skips_when_above_threshold(
  mock_get_all_punny_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Jokes with enough views keep their existing fraction."""
  joke = _create_fake_joke(
    "j1",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS,
    num_saved_users_fraction=0.3,
  )
  mock_get_all_punny_jokes.return_value = [joke]

  html_response = util_fns.run_saved_fraction_migration(
    dry_run=False,
    max_jokes=0,
  )

  mock_update_punny_joke.assert_not_called()
  assert "Updated Jokes (0)" in html_response
  assert "reason=num_viewed_users>=threshold" in html_response


def test_saved_fraction_migration_respects_max_jokes(
  mock_get_all_punny_jokes: MagicMock,
  mock_update_punny_joke: MagicMock,
):
  """Migration should stop updating after reaching max_jokes."""
  joke1 = _create_fake_joke(
    "j1",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS - 1,
    num_saved_users_fraction=0.5,
  )
  joke2 = _create_fake_joke(
    "j2",
    num_viewed_users=MIN_VIEWS_FOR_FRACTIONS - 2,
    num_saved_users_fraction=0.6,
  )
  mock_get_all_punny_jokes.return_value = [joke1, joke2]

  html_response = util_fns.run_saved_fraction_migration(
    dry_run=False,
    max_jokes=1,
  )

  mock_update_punny_joke.assert_called_once_with(
    "j1", {"num_saved_users_fraction": 0.0})
  assert "Updated Jokes (1)" in html_response
