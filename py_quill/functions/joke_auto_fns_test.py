"""Tests for joke_auto_fns helper module."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, Mock

import pytest
from common import models
from functions import joke_auto_fns
from functions.joke_auto_fns import MIN_VIEWS_FOR_FRACTIONS
from services import firestore


@pytest.fixture(autouse=True, name='mock_logger')
def mock_logger_fixture(monkeypatch):
  """Silence firebase logger interactions during tests."""
  mock_log = Mock()
  monkeypatch.setattr('functions.joke_auto_fns.logger', mock_log)
  return mock_log


def _create_test_datetime(year=2024, month=1, day=20, hour=0, minute=0):
  """Create a test datetime in UTC timezone."""
  return datetime.datetime(year,
                           month,
                           day,
                           hour,
                           minute,
                           0,
                           tzinfo=datetime.timezone.utc)


def _setup_mock_db_and_batch(monkeypatch, docs):
  """Helper to set up mock Firestore db and batch."""
  mock_batch = MagicMock()
  mock_db = MagicMock()
  mock_db.collection.return_value.stream.return_value = docs
  mock_db.batch.return_value = mock_batch
  monkeypatch.setattr('functions.joke_auto_fns.firestore.db', lambda: mock_db)
  return mock_db, mock_batch


def _setup_decay_test_mocks(monkeypatch,
                            mock_sync=True,
                            mock_update_public=True):
  """Helper to set up common mocks for decay tests."""
  if mock_sync:
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
  if mock_update_public:
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
  monkeypatch.setattr(
    'common.joke_category_operations.refresh_category_caches',
    Mock(
      return_value={
        "categories_processed": 0,
        "categories_updated": 0,
        "categories_emptied": 0,
        "categories_failed": 0
      }))


class TestDecayRecentJokeStats:
  """Tests for the recent joke stats decay job."""

  def test_updates_counters_when_last_update_stale(self, monkeypatch):
    now_utc = _create_test_datetime()
    doc_ref = MagicMock(name='doc_ref')
    doc = MagicMock()
    doc.exists = True
    doc.reference = doc_ref
    doc.to_dict.return_value = {
      "num_viewed_users_recent": 100,
      "num_saved_users_recent": 50,
      "num_shared_users_recent": 10,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=22),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }

    mock_db, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    assert payload["num_viewed_users_recent"] == pytest.approx(90.0)
    assert payload["num_saved_users_recent"] == pytest.approx(45.0)
    assert payload["num_shared_users_recent"] == pytest.approx(9.0)
    assert payload["is_public"] is True
    assert payload[
      "last_recent_stats_update_time"] is firestore.SERVER_TIMESTAMP

  def test_skips_when_recently_updated(self, monkeypatch):
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 20,
      "num_viewed_users_recent": 80,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
      "state": models.JokeState.APPROVED.value,
      "is_public": False,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_not_called()

  def test_missing_recent_fields_are_skipped(self, monkeypatch):
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users_recent": None,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.APPROVED.value,
      "is_public": False,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    # Missing fields should not be included in payload
    assert "num_viewed_users_recent" not in payload
    assert "num_saved_users_recent" not in payload
    assert "num_shared_users_recent" not in payload
    assert "is_public" not in payload
    assert payload[
      "last_recent_stats_update_time"] is firestore.SERVER_TIMESTAMP

  def test_recent_update_still_updates_is_public_when_mismatch(
      self, monkeypatch):
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload == {"is_public": True}

  @pytest.mark.parametrize(
    "public_timestamp_offset,initial_is_public,expected_is_public",
    [
      (datetime.timedelta(hours=-1), False, True),  # Past timestamp
      (datetime.timedelta(hours=12), True, False),  # Future timestamp
    ])
  def test_daily_state_sets_is_public_based_on_public_timestamp(
      self, monkeypatch, public_timestamp_offset, initial_is_public,
      expected_is_public):
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users_recent": 10,
      "num_saved_users_recent": 5,
      "num_shared_users_recent": 2,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=1),
      "state": models.JokeState.DAILY.value,
      "public_timestamp": now_utc + public_timestamp_offset,
      "is_public": initial_is_public,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    _setup_decay_test_mocks(monkeypatch)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    assert payload["is_public"] == expected_is_public

  def test_http_endpoint_uses_current_time(self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr(
      'functions.joke_auto_fns._joke_daily_maintenance_internal', _capture)

    joke_auto_fns.joke_daily_maintenance_http(Mock())

    assert 'run_time' in captured
    assert captured['run_time'].tzinfo == datetime.timezone.utc

  def test_scheduler_invokes_decay_with_scheduled_time(self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr(
      'functions.joke_auto_fns._joke_daily_maintenance_internal', _capture)

    event = MagicMock()
    event.schedule_time = datetime.datetime(2024,
                                            1,
                                            20,
                                            0,
                                            0,
                                            tzinfo=datetime.timezone.utc)

    joke_auto_fns.joke_daily_maintenance_scheduler.__wrapped__(event)

    assert 'run_time' in captured
    assert captured['run_time'] == event.schedule_time

  def test_scheduler_falls_back_to_current_time_when_scheduled_time_none(
      self, monkeypatch):
    captured = {}

    def _capture(run_time):
      captured['run_time'] = run_time

    monkeypatch.setattr(
      'functions.joke_auto_fns._joke_daily_maintenance_internal', _capture)

    event = MagicMock()
    event.schedule_time = None

    joke_auto_fns.joke_daily_maintenance_scheduler.__wrapped__(event)

    assert 'run_time' in captured
    assert captured['run_time'].tzinfo == datetime.timezone.utc

  def test_http_endpoint_success(self, monkeypatch):
    mock_decay = Mock()
    mock_decay.return_value = {
      "jokes_decayed": 5,
      "public_updated": 3,
      "jokes_skipped": 2,
      "jokes_boosted": 1,
      "categories_processed": 4,
      "categories_updated": 2,
      "categories_emptied": 1,
      "categories_failed": 0
    }
    monkeypatch.setattr(
      'functions.joke_auto_fns._joke_daily_maintenance_internal', mock_decay)

    response = joke_auto_fns.joke_daily_maintenance_http(Mock())

    mock_decay.assert_called_once()
    assert response["data"][
      "message"] == "Daily maintenance completed successfully"
    assert "stats" in response["data"]
    assert response["data"]["stats"]["jokes_decayed"] == 5

  def test_http_endpoint_failure(self, monkeypatch):

    def _raise(run_time_utc):
      raise RuntimeError("boom")

    monkeypatch.setattr(
      'functions.joke_auto_fns._joke_daily_maintenance_internal', _raise)

    response = joke_auto_fns.joke_daily_maintenance_http(Mock())

    assert "boom" in response["data"]["error"]

  @pytest.mark.parametrize(
    "num_viewed_users,existing_fraction,random_value,expected_fraction",
    [
      (0, None, 0.02, 0.02),  # Zero views, no existing fraction
      (5, None, 0.015, 0.015),  # Below threshold, no existing fraction
      (8, 0.03, 0.01, 0.04),  # Below threshold, with existing fraction
      (9, None, 0.0125, 0.0125),  # Exactly 9 views
      (MIN_VIEWS_FOR_FRACTIONS, 0.05, None, None),  # At threshold - no boost
      (MIN_VIEWS_FOR_FRACTIONS + 10, 0.1, None,
       None),  # Above threshold - no boost
    ])
  def test_boost_fraction_behavior(self, monkeypatch, num_viewed_users,
                                   existing_fraction, random_value,
                                   expected_fraction):
    """Test fraction boost behavior for various view counts."""
    now_utc = _create_test_datetime()
    doc_data = {
      "num_viewed_users": num_viewed_users,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }
    if existing_fraction is not None:
      doc_data["num_saved_users_fraction"] = existing_fraction

    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = doc_data

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    mock_random = Mock(
      return_value=random_value if random_value is not None else 0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[
      1] if mock_batch.update.called else {}
    if expected_fraction is None:
      # No boost expected
      assert "num_saved_users_fraction" not in payload
      mock_random.assert_not_called()
    else:
      # Boost expected
      assert payload["num_saved_users_fraction"] == pytest.approx(
        expected_fraction)
      mock_random.assert_called_once_with(0.0, 0.02)

  def test_boost_handles_invalid_fraction_type(self, monkeypatch):
    """Test that invalid fraction types are treated as 0.0."""
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 3,
      "num_saved_users_fraction": "invalid",
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.01)

  def test_boost_handles_invalid_view_count_type(self, monkeypatch):
    """Test that invalid view count types are treated as 0."""
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": "invalid",
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.01)

  def test_boost_statistics_tracked(self, monkeypatch):
    """Test that boosted jokes are counted in statistics."""
    now_utc = _create_test_datetime()

    doc1 = MagicMock()
    doc1.exists = True
    doc1.reference = MagicMock()
    doc1.to_dict.return_value = {
      "num_viewed_users": 5,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    doc2 = MagicMock()
    doc2.exists = True
    doc2.reference = MagicMock()
    doc2.to_dict.return_value = {
      "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc1, doc2])
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())

    # Mock random.uniform
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    # Mock category refresh to return empty stats
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    result = joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    assert result["jokes_boosted"] == 1

  @pytest.mark.parametrize(
    "joke_docs,expected_joke_ids,should_be_called",
    [
      # Test with two PUBLISHED jokes
      ([
        ("joke1", models.JokeState.PUBLISHED, True, None),
        ("joke2", models.JokeState.PUBLISHED, True, None),
      ], {"joke1", "joke2"}, True),
      # Test with no public jokes (DRAFT)
      ([
        ("joke1", models.JokeState.DRAFT, False, None),
      ], set(), False),
      # Test with DAILY joke with past timestamp (should be included)
      (
        [
          ("daily-joke", models.JokeState.DAILY, False, -1),  # -1 hour
        ],
        {"daily-joke"},
        True),
      # Test with DAILY joke with future timestamp (should be excluded)
      (
        [
          ("future-daily-joke", models.JokeState.DAILY, False, 1),  # +1 hour
        ],
        set(),
        False),
      # Test with mixed public jokes (PUBLISHED + DAILY with past timestamp)
      (
        [
          ("published-joke", models.JokeState.PUBLISHED, True, None),
          ("daily-joke", models.JokeState.DAILY, False, -1),  # -1 hour
          ("draft-joke", models.JokeState.DRAFT, False,
           None),  # Should be excluded
        ],
        {"published-joke", "daily-joke"},
        True),
    ])
  def test_update_public_joke_ids_behavior(self, monkeypatch, joke_docs,
                                           expected_joke_ids,
                                           should_be_called):
    """Test update_public_joke_ids behavior for various joke states."""
    now_utc = _create_test_datetime()
    docs = []
    for joke_id, state, is_public, timestamp_offset_hours in joke_docs:
      doc = MagicMock()
      doc.exists = True
      doc.id = joke_id
      doc.reference = MagicMock()
      doc_data = {
        "state": state.value,
        "is_public": is_public,
        "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS,
        "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      }
      if timestamp_offset_hours is not None:
        doc_data["public_timestamp"] = now_utc + datetime.timedelta(
          hours=timestamp_offset_hours)
      doc.to_dict.return_value = doc_data
      docs.append(doc)

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, docs)
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    mock_update_public_joke_ids = Mock()
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids',
      mock_update_public_joke_ids)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    if should_be_called:
      mock_update_public_joke_ids.assert_called_once()
      call_args = mock_update_public_joke_ids.call_args[0][0]
      assert set(call_args) == expected_joke_ids
    else:
      mock_update_public_joke_ids.assert_not_called()

  @pytest.mark.parametrize(
    "update_type,doc_data,expected_is_public,expected_fraction_range",
    [
      # Test with is_public update
      (
        "is_public_update",
        {
          "is_public": False,  # Will be updated to True
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -22,  # hours
        },
        True,
        None),
      # Test without updates
      (
        "no_updates",
        {
          "is_public": True,  # Already correct
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -4,  # hours - recent
        },
        True,
        (0.5, 0.5)),
      # Test with fraction boost
      (
        "fraction_boost",
        {
          "is_public": True,
          "num_viewed_users": 10,  # Below threshold
          "num_saved_users": 5,
          "num_shared_users": 2,
          "num_saved_users_fraction": 0.3,  # Will be boosted
          "num_shared_users_fraction": 0.2,
          "popularity_score": 4.9,
          "last_recent_stats_update_time": -4,  # hours
        },
        True,
        (0.3, 0.32)),  # Range: 0.3 to 0.32
      # Test with decay
      (
        "decay",
        {
          "is_public": True,
          "num_viewed_users": 100,
          "num_saved_users": 50,
          "num_shared_users": 30,
          "num_viewed_users_recent": 100.0,
          "num_saved_users_recent": 50.0,
          "num_shared_users_recent": 30.0,
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.3,
          "popularity_score": 64.0,
          "last_recent_stats_update_time": -22,  # hours
        },
        True,
        (0.5, 0.5)),
    ])
  def test_syncs_joke_to_search_collection(self, monkeypatch, update_type,
                                           doc_data, expected_is_public,
                                           expected_fraction_range):
    """Test that jokes are synced to search collection with appropriate merged data."""
    now_utc = _create_test_datetime()
    doc = MagicMock()
    doc.exists = True
    doc.id = "joke1"
    doc.reference = MagicMock()

    # Build doc data with setup fields
    full_doc_data = {
      "setup_text": "Test setup",
      "punchline_text": "Test punchline",
      "state": models.JokeState.PUBLISHED.value,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
    }
    full_doc_data.update(doc_data)

    # Convert hours offset to timedelta
    if "last_recent_stats_update_time" in full_doc_data:
      hours_offset = full_doc_data.pop("last_recent_stats_update_time")
      full_doc_data["last_recent_stats_update_time"] = (
        now_utc + datetime.timedelta(hours=hours_offset))

    doc.to_dict.return_value = full_doc_data

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])
    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    # Mock random for boost test
    if update_type == "fraction_boost":
      mock_random = Mock(return_value=0.01)
      monkeypatch.setattr('functions.joke_auto_fns.random.uniform',
                          mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    # Verify sync was called
    mock_sync.assert_called_once()
    call_args = mock_sync.call_args
    joke = call_args.kwargs['joke']
    new_embedding = call_args.kwargs['new_embedding']

    # Verify joke data
    assert joke.key == "joke1"
    assert joke.is_public == expected_is_public
    assert new_embedding is None

    # Verify fraction if specified
    if expected_fraction_range:
      if expected_fraction_range[0] == expected_fraction_range[1]:
        # Exact value
        assert joke.num_saved_users_fraction == pytest.approx(
          expected_fraction_range[0])
      else:
        # Range
        assert joke.num_saved_users_fraction >= expected_fraction_range[0]
        assert joke.num_saved_users_fraction <= expected_fraction_range[1]

  def test_syncs_multiple_jokes_with_different_updates(self, monkeypatch):
    """Test that multiple jokes with different update scenarios are all synced."""
    now_utc = _create_test_datetime()

    # Joke 1: Has updates (is_public change)
    doc1 = MagicMock()
    doc1.exists = True
    doc1.id = "joke1"
    doc1.reference = MagicMock()
    doc1.to_dict.return_value = {
      "setup_text": "Test setup 1",
      "punchline_text": "Test punchline 1",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,  # Will be updated
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
    }

    # Joke 2: No updates (everything already correct)
    doc2 = MagicMock()
    doc2.exists = True
    doc2.id = "joke2"
    doc2.reference = MagicMock()
    doc2.to_dict.return_value = {
      "setup_text": "Test setup 2",
      "punchline_text": "Test punchline 2",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,  # Already correct
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc1, doc2])
    mock_sync = Mock()
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)

    # Verify sync was called twice (once for each joke)
    assert mock_sync.call_count == 2

    # Verify first joke has updated is_public
    call1 = mock_sync.call_args_list[0]
    joke1 = call1.kwargs['joke']
    assert joke1.key == "joke1"
    assert joke1.is_public is True  # Updated from False

    # Verify second joke has original data
    call2 = mock_sync.call_args_list[1]
    joke2 = call2.kwargs['joke']
    assert joke2.key == "joke2"
    assert joke2.is_public is True  # Original value

  def test_sync_handles_errors_gracefully(self, monkeypatch):
    """Test that sync errors don't crash the maintenance job."""
    now_utc = _create_test_datetime()

    doc = MagicMock()
    doc.exists = True
    doc.id = "joke1"
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "setup_text": "Test setup",
      "punchline_text": "Test punchline",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
      "public_timestamp": now_utc - datetime.timedelta(days=1),
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=4),
    }

    _, mock_batch = _setup_mock_db_and_batch(monkeypatch, [doc])

    # Mock sync to raise an exception
    mock_sync = Mock(side_effect=Exception("Sync failed"))
    monkeypatch.setattr(
      'common.joke_operations.sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'common.joke_category_operations.refresh_category_caches',
      Mock(
        return_value={
          "categories_processed": 0,
          "categories_updated": 0,
          "categories_emptied": 0,
          "categories_failed": 0
        }))

    # Should not raise exception
    joke_auto_fns._joke_daily_maintenance_internal(now_utc)

    # Verify sync was called
    mock_sync.assert_called_once()
    # Verify error was logged by checking the mocked logger
    mock_logger = joke_auto_fns.logger
    mock_logger.warn.assert_called()
    warn_call = str(mock_logger.warn.call_args)
    assert "Failed to sync joke joke1" in warn_call
    assert "Sync failed" in warn_call
