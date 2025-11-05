"""Tests for joke_auto_fns helper module."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, Mock

import pytest
from common import models
from functions import joke_auto_fns
from functions.joke_auto_fns import MIN_VIEWS_FOR_FRACTIONS
from google.cloud.firestore_v1.vector import Vector
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
  if mock_update_public:
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
  monkeypatch.setattr(
    'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())

    # Mock random.uniform
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    # Mock category refresh to return empty stats
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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
      'functions.joke_auto_fns._sync_joke_to_search_collection', mock_sync)
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.update_public_joke_ids', Mock())
    monkeypatch.setattr(
      'functions.joke_auto_fns._refresh_category_caches',
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


class TestOnJokeWrite:
  """Tests for the on_joke_write trigger."""

  @pytest.fixture(name='mock_get_joke_embedding')
  def mock_get_joke_embedding_fixture(self, monkeypatch):
    mock_embedding_fn = Mock(return_value=(Vector([1.0, 2.0, 3.0]),
                                           models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding",
                        mock_embedding_fn)
    return mock_embedding_fn

  @pytest.fixture(name='mock_firestore_service')
  def mock_firestore_service_fixture(self, monkeypatch):
    mock_firestore = Mock()
    mock_firestore.update_punny_joke = Mock()

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc_ref = MagicMock()
    mock_sub_collection = MagicMock()
    mock_sub_doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = False
    snapshot.to_dict.return_value = None

    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    mock_doc_ref.collection.return_value = mock_sub_collection
    mock_sub_collection.document.return_value = mock_sub_doc_ref
    mock_sub_doc_ref.get.return_value = snapshot

    monkeypatch.setattr(joke_auto_fns, "firestore", mock_firestore)
    mock_firestore.db = lambda: mock_db

    return mock_firestore

  def _create_event(self, before, after):
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()
    event.data.before = MagicMock() if before is not None else None
    event.data.after = MagicMock() if after is not None else None
    if before is not None:
      event.data.before.to_dict.return_value = before
    if after is not None:
      event.data.after.to_dict.return_value = after
    return event

  def test_new_joke_initializes_recent_counters_and_popularity(
      self, mock_get_joke_embedding, mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=4,
      num_shared_users=1,
      num_viewed_users=5,
      num_saved_users_fraction=0.0,
      num_shared_users_fraction=0.0,
    ).to_dict()

    event = self._create_event(before=None, after=after_joke)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    call_args = mock_firestore_service.update_punny_joke.call_args[0]
    update_data = call_args[1]
    assert update_data["num_viewed_users_recent"] == pytest.approx(5.0)
    assert update_data["num_saved_users_recent"] == pytest.approx(4.0)
    assert update_data["num_shared_users_recent"] == pytest.approx(1.0)
    assert update_data["popularity_score_recent"] == pytest.approx(25.0 / 5.0)
    assert "zzz_joke_text_embedding" in update_data

  def test_existing_recent_counters_coerced_to_float(self,
                                                     mock_get_joke_embedding,
                                                     mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=2,
      num_shared_users=1,
      num_viewed_users=4,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.25,
    ).to_dict()
    after_joke.update({
      "num_viewed_users_recent": 4,
      "num_saved_users_recent": 2,
      "num_shared_users_recent": 1,
    })

    event = self._create_event(before=after_joke, after=after_joke)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    update_data = mock_firestore_service.update_punny_joke.call_args[0][1]
    assert update_data["num_viewed_users_recent"] == pytest.approx(4.0)
    assert update_data["num_saved_users_recent"] == pytest.approx(2.0)
    assert update_data["num_shared_users_recent"] == pytest.approx(1.0)

  def test_draft_joke_skips_embedding(self, mock_get_joke_embedding,
                                      mock_firestore_service):
    draft_joke = models.PunnyJoke(key="joke1",
                                  setup_text="s",
                                  punchline_text="p",
                                  state=models.JokeState.DRAFT).to_dict()
    event = self._create_event(before=None, after=draft_joke)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_zero_views_keeps_fractions_unset(self, mock_get_joke_embedding,
                                            mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=3,
      num_shared_users=1,
      num_viewed_users=0,
      num_saved_users_fraction=0.0,
      num_shared_users_fraction=0.0,
    ).to_dict()

    event = self._create_event(before=None, after=after_joke)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    update_data = mock_firestore_service.update_punny_joke.call_args[0][1]
    assert "num_saved_users_fraction" not in update_data
    assert "num_shared_users_fraction" not in update_data


class TestOnJokeWriteSearchSync:
  """Tests for syncing jokes to the joke_search collection."""

  def _create_event(self, before, after):
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()
    event.data.before = MagicMock() if before else None
    event.data.after = MagicMock() if after else None
    if before:
      event.data.before.to_dict.return_value = before
    if after:
      event.data.after.to_dict.return_value = after
    return event

  def _setup_search_mocks(self, monkeypatch):
    mock_db = MagicMock()
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()

    def mock_collection(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_search_collection.document.return_value = mock_search_doc_ref

    search_doc_state = {"doc": None}

    def mock_get():
      snapshot = MagicMock()
      if search_doc_state["doc"] is None:
        snapshot.exists = False
        snapshot.to_dict.return_value = None
      else:
        snapshot.exists = True
        snapshot.to_dict.return_value = search_doc_state["doc"]
      return snapshot

    def mock_set(data, merge=False):
      if not merge or search_doc_state["doc"] is None:
        search_doc_state["doc"] = {}
      search_doc_state["doc"].update(data)

    def mock_delete():
      search_doc_state["doc"] = None

    mock_search_doc_ref.get.side_effect = mock_get
    mock_search_doc_ref.set.side_effect = mock_set
    mock_search_doc_ref.delete.side_effect = mock_delete

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_auto_fns, "firestore", mock_firestore)

    return mock_search_doc_ref, search_doc_state

  def test_new_joke_creates_search_doc(self, monkeypatch):
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Why did the scarecrow win an award?",
      punchline_text="Because he was outstanding in his field.",
      state=models.JokeState.UNREVIEWED,
      public_timestamp=joke_date,
      is_public=False,
    )

    event = self._create_event(before=None, after=after_joke.to_dict())

    mock_embedding = Mock(return_value=(Vector([1.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding", mock_embedding)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    synced = search_doc_state["doc"]
    assert synced is not None
    assert synced["text_embedding"] == Vector([1.0])
    assert synced["state"] == models.JokeState.UNREVIEWED.value
    assert synced["public_timestamp"] == joke_date
    assert synced["is_public"] is False

  def test_syncs_all_fields(self, monkeypatch):
    """Test that all search fields are synced correctly."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      public_timestamp=joke_date,
      is_public=True,
      num_viewed_users=100,
      num_saved_users=50,
      num_shared_users=30,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.3,
    )
    # popularity_score will be calculated: (50+30)^2 / 100 = 64.0
    after_joke.popularity_score = 64.0

    event = self._create_event(before=None, after=after_joke.to_dict())

    mock_embedding = Mock(return_value=(Vector([1.0, 2.0, 3.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding", mock_embedding)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    synced = search_doc_state["doc"]
    assert synced is not None
    assert synced["text_embedding"] == Vector([1.0, 2.0, 3.0])
    assert synced["state"] == models.JokeState.PUBLISHED.value
    assert synced["is_public"] is True
    assert synced["public_timestamp"] == joke_date
    assert synced["num_saved_users_fraction"] == 0.5
    assert synced["num_shared_users_fraction"] == 0.3
    assert synced["popularity_score"] == 64.0

  def test_updates_only_changed_fields(self, monkeypatch):
    """Test that only changed fields are updated in joke_search collection."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    # Set up existing search doc with some fields
    search_doc_state["doc"] = {
      "text_embedding": Vector([1.0, 2.0, 3.0]),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "public_timestamp": datetime.datetime.now(datetime.timezone.utc),
      "num_saved_users_fraction": 0.5,
      "num_shared_users_fraction": 0.3,
      "popularity_score": 10.5,
    }

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.DAILY,  # Changed
      public_timestamp=joke_date,
      is_public=False,  # Changed
      num_viewed_users=100,
      num_saved_users=50,
      num_shared_users=40,  # Changed from 30
      num_saved_users_fraction=0.5,  # Same
      num_shared_users_fraction=0.4,  # Changed
    )
    # popularity_score will be recalculated: (50+40)^2 / 100 = 81.0
    after_joke.popularity_score = 81.0

    # Create before_joke to simulate update (not new joke)
    before_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      is_public=True,
      num_shared_users_fraction=0.3,
    )

    event = self._create_event(before=before_joke.to_dict(),
                               after=after_joke.to_dict())

    # No new embedding provided, should use existing
    monkeypatch.setattr(
      joke_auto_fns, "_get_joke_embedding",
      Mock(return_value=(Vector([1.0, 2.0, 3.0]),
                         models.GenerationMetadata())))

    joke_auto_fns.on_joke_write.__wrapped__(event)

    synced = search_doc_state["doc"]
    assert synced["state"] == models.JokeState.DAILY.value
    assert synced["is_public"] is False
    assert synced["num_saved_users_fraction"] == 0.5  # Unchanged
    assert synced["num_shared_users_fraction"] == 0.4  # Updated
    assert synced["popularity_score"] == 81.0  # Recalculated

  def test_uses_existing_embedding_when_no_new_embedding(self, monkeypatch):
    """Test that existing embedding is used when no new embedding is provided."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    existing_embedding = Vector([5.0, 6.0, 7.0])
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      is_public=True,
      zzz_joke_text_embedding=existing_embedding,
    )

    # Create before_joke with same text to prevent embedding recalculation
    before_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
    )

    event = self._create_event(before=before_joke.to_dict(),
                               after=joke.to_dict())

    # No embedding calculation should happen since text didn't change
    mock_embedding = Mock(return_value=(Vector([1.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding", mock_embedding)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    synced = search_doc_state["doc"]
    assert synced is not None
    # Should use existing embedding from joke
    assert synced["text_embedding"] == existing_embedding
    # Should not call embedding generation since text didn't change
    mock_embedding.assert_not_called()

  def test_no_sync_when_joke_has_no_key(self, monkeypatch):
    """Test that sync is skipped when joke has no key after from_firestore_dict."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    # Create a joke dict without key, but event.params will have joke_id
    # The key will be set from event.params in from_firestore_dict
    # So we need to test the case where key is None after processing
    joke_data = {
      "setup_text": "Test setup",
      "punchline_text": "Test punchline",
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    # Mock from_firestore_dict to return joke with None key
    original_from_dict = models.PunnyJoke.from_firestore_dict

    def mock_from_dict(data, key):
      joke = original_from_dict(data, key)
      joke.key = None  # Force key to None
      return joke

    monkeypatch.setattr(models.PunnyJoke, "from_firestore_dict",
                        mock_from_dict)

    event = self._create_event(before=None, after=joke_data)

    mock_embedding = Mock(return_value=(Vector([1.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding", mock_embedding)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    # Should not create search doc when joke has no key
    assert search_doc_state["doc"] is None

  def test_syncs_is_public_when_changed(self, monkeypatch):
    """Test that is_public is synced when it changes from False to True."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    # Set up existing search doc with is_public=False
    search_doc_state["doc"] = {
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      public_timestamp=joke_date,
      is_public=True,  # Changed from False to True
    )

    event = self._create_event(before=None, after=after_joke.to_dict())

    mock_embedding = Mock(return_value=(Vector([1.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_auto_fns, "_get_joke_embedding", mock_embedding)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    synced = search_doc_state["doc"]
    assert synced["is_public"] is True

  def test_deletes_search_doc_when_joke_deleted(self, monkeypatch):
    """Test that search document is deleted when joke is deleted."""
    mock_search_doc_ref, search_doc_state = self._setup_search_mocks(
      monkeypatch)

    # Set up existing search doc
    search_doc_state["doc"] = {
      "text_embedding": Vector([1.0, 2.0, 3.0]),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    # Verify delete was called
    mock_search_doc_ref.delete.assert_called_once()
    # Verify search doc was cleared
    assert search_doc_state["doc"] is None

  def test_deletes_search_doc_when_not_exists(self, monkeypatch):
    """Test that deletion handles case when search doc doesn't exist."""
    mock_search_doc_ref, search_doc_state = self._setup_search_mocks(
      monkeypatch)

    # No existing search doc
    search_doc_state["doc"] = None

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_auto_fns.on_joke_write.__wrapped__(event)

    # Verify delete was not called (since doc doesn't exist)
    mock_search_doc_ref.delete.assert_not_called()


class TestOnJokeCategoryWrite:
  """Tests for the on_joke_category_write cloud function."""

  def _create_event(self, before_data, after_data, category_id="cat1"):
    event = MagicMock()
    event.params = {"category_id": category_id}
    event.data = MagicMock()
    event.data.before = MagicMock() if before_data is not None else None
    event.data.after = MagicMock() if after_data is not None else None
    if before_data is not None:
      event.data.before.to_dict.return_value = before_data
    if after_data is not None:
      event.data.after.to_dict.return_value = after_data
    return event

  def test_new_doc_with_image_description_generates_and_updates(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to not exist (new document)
    mock_doc.exists = False
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None,
                               after_data={"image_description": "desc"})

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once(
    )  # Should call get() to check if doc exists
    mock_doc.set.assert_called_once()  # Should call set() for new document
    args = mock_doc.set.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [mock_image.url]

  def test_existing_doc_with_image_description_generates_and_updates(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/new_image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to exist with existing data
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
      "image_url": "http://example.com/old_image.png",
      "all_image_urls": ["http://example.com/old_image.png"]
    }
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once(
    )  # Should call get() to check if doc exists
    mock_doc.update.assert_called_once(
    )  # Should call update() for existing document
    args = mock_doc.update.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [
      "http://example.com/old_image.png", "http://example.com/new_image.png"
    ]

  def test_existing_doc_without_all_image_urls_initializes_it(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/new_image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to exist but without all_image_urls field
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
      "image_url": "http://example.com/old_image.png"
      # No all_image_urls field
    }
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once()
    mock_doc.update.assert_called_once()
    args = mock_doc.update.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [
      "http://example.com/old_image.png", "http://example.com/new_image.png"
    ]

  def test_description_unchanged_does_nothing(self, monkeypatch):
    # Arrange
    mock_generate = MagicMock()
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "same"},
                               after_data={"image_description": "same"})

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()

  def test_missing_image_description_skips(self, monkeypatch):
    # Arrange
    mock_generate = MagicMock()
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None, after_data={})

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()

  @pytest.mark.parametrize(
    "before_data,after_data,should_refresh",
    [
      # Query change - should refresh
      ({
        "joke_description_query": "cats"
      }, {
        "joke_description_query": "dogs",
        "state": "APPROVED"
      }, True),
      # Seasonal name change - should refresh
      ({
        "seasonal_name": "Halloween"
      }, {
        "seasonal_name": "Christmas",
        "state": "APPROVED"
      }, True),
      # New doc with query - should refresh
      (None, {
        "joke_description_query": "animals",
        "state": "APPROVED"
      }, True),
      # Query and seasonal unchanged - should not refresh
      ({
        "joke_description_query": "cats",
        "seasonal_name": None
      }, {
        "joke_description_query": "cats",
        "seasonal_name": None,
        "image_description": "new description"
      }, False),
    ])
  def test_cache_refresh_behavior(self, monkeypatch, before_data, after_data,
                                  should_refresh):
    """Test that cache is refreshed when query/seasonal changes, not otherwise."""
    # Arrange
    mock_image_gen = MagicMock()
    monkeypatch.setattr(joke_auto_fns.image_generation, "generate_pun_image",
                        mock_image_gen)

    mock_db = MagicMock()
    monkeypatch.setattr(joke_auto_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    # Mock the cache refresh helper
    mock_refresh = MagicMock(return_value="updated")
    monkeypatch.setattr(joke_auto_fns, "_refresh_single_category_cache",
                        mock_refresh)

    event = self._create_event(before_data=before_data, after_data=after_data)

    # Act
    joke_auto_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    if should_refresh:
      mock_refresh.assert_called_once_with("cat1", event.data.after.to_dict())
    else:
      mock_refresh.assert_not_called()


class TestSearchCategoryJokesSorting:
  """Tests for _search_category_jokes sorting behavior."""

  def test_sorts_results_by_num_saved_users_fraction(self, monkeypatch):
    """Test that search results are sorted by num_saved_users_fraction in descending order."""

    # Arrange
    from services.search import JokeSearchResult
    results = [
      JokeSearchResult(joke_id="j1", vector_distance=0.1),
      JokeSearchResult(joke_id="j2", vector_distance=0.1),
      JokeSearchResult(joke_id="j3", vector_distance=0.1),
      JokeSearchResult(joke_id="j4", vector_distance=0.1),
    ]

    def fake_search_jokes(**kwargs):  # pylint: disable=unused-argument
      return results

    # Mock full jokes returned by firestore.get_punny_jokes
    # These should have the fresh num_saved_users_fraction values
    full_jokes = [
      models.PunnyJoke(
        key="j1",
        setup_text="Setup j1",
        punchline_text="Punchline j1",
        setup_image_url="https://example.com/j1-setup.jpg",
        punchline_image_url="https://example.com/j1-punchline.jpg",
        num_saved_users_fraction=0.1,
      ),
      models.PunnyJoke(
        key="j2",
        setup_text="Setup j2",
        punchline_text="Punchline j2",
        setup_image_url="https://example.com/j2-setup.jpg",
        punchline_image_url="https://example.com/j2-punchline.jpg",
        num_saved_users_fraction=0.5,
      ),
      models.PunnyJoke(
        key="j3",
        setup_text="Setup j3",
        punchline_text="Punchline j3",
        setup_image_url="https://example.com/j3-setup.jpg",
        punchline_image_url="https://example.com/j3-punchline.jpg",
        num_saved_users_fraction=0.0,
      ),
      models.PunnyJoke(
        key="j4",
        setup_text="Setup j4",
        punchline_text="Punchline j4",
        setup_image_url="https://example.com/j4-setup.jpg",
        punchline_image_url="https://example.com/j4-punchline.jpg",
        num_saved_users_fraction=0.3,
      ),
    ]

    def fake_get_punny_jokes(joke_ids):
      # Return jokes in the order requested (preserve order for testing)
      id_to_joke = {j.key: j for j in full_jokes}
      return [id_to_joke[jid] for jid in joke_ids if jid in id_to_joke]

    monkeypatch.setattr("py_quill.functions.joke_auto_fns.search.search_jokes",
                        fake_search_jokes)
    monkeypatch.setattr(
      "py_quill.functions.joke_auto_fns.firestore.get_punny_jokes",
      fake_get_punny_jokes)

    # Act
    jokes = joke_auto_fns._search_category_jokes("test query", "cat1")

    # Assert
    assert len(jokes) == 4
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[0]["setup"] == "Setup j2"
    assert jokes[0]["punchline"] == "Punchline j2"
    assert jokes[1]["joke_id"] == "j4"
    assert jokes[1]["setup"] == "Setup j4"
    assert jokes[2]["joke_id"] == "j1"
    assert jokes[2]["setup"] == "Setup j1"
    assert jokes[3]["joke_id"] == "j3"
    assert jokes[3]["setup"] == "Setup j3"


class TestQuerySeasonalCategoryJokesSorting:
  """Tests for _query_seasonal_category_jokes sorting behavior."""

  def test_sorts_docs_by_num_saved_users_fraction(self, monkeypatch):
    """Test that seasonal jokes are sorted by num_saved_users_fraction in descending order."""

    # Arrange
    class _MockDoc:

      def __init__(self, doc_id, fraction):
        self.id = doc_id
        self._fraction = fraction
        self._data = {
          "setup_text": f"Setup {doc_id}",
          "punchline_text": f"Punchline {doc_id}",
          "num_saved_users_fraction": fraction,
        }

      def to_dict(self):
        return self._data

    class _MockQuery:

      def __init__(self, docs):
        self._docs = docs

      def where(self, filter):  # pylint: disable=redefined-builtin
        return self

      def limit(self, limit):
        return self

      def stream(self):
        return iter(self._docs)

    class _MockCollection:

      def __init__(self, docs):
        self._docs = docs

      def collection(self, name):
        return self

      def where(self, filter):  # pylint: disable=redefined-builtin
        return _MockQuery(self._docs)

    docs = [
      _MockDoc("j1", 0.1),
      _MockDoc("j2", 0.5),
      _MockDoc("j3", 0.0),
      _MockDoc("j4", 0.3),
    ]

    mock_client = _MockCollection(docs)

    # Act
    jokes = joke_auto_fns._query_seasonal_category_jokes(
      mock_client, "Halloween")

    # Assert
    assert len(jokes) == 4
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[1]["joke_id"] == "j4"
    assert jokes[2]["joke_id"] == "j1"
    assert jokes[3]["joke_id"] == "j3"

  def test_handles_missing_fraction_field(self, monkeypatch):
    """Test that docs without num_saved_users_fraction are sorted last."""

    # Arrange
    class _MockDoc:

      def __init__(self, doc_id, fraction=None):
        self.id = doc_id
        self._data = {
          "setup_text": f"Setup {doc_id}",
          "punchline_text": f"Punchline {doc_id}",
        }
        if fraction is not None:
          self._data["num_saved_users_fraction"] = fraction

      def to_dict(self):
        return self._data

    class _MockQuery:

      def __init__(self, docs):
        self._docs = docs

      def where(self, filter):  # pylint: disable=redefined-builtin
        return self

      def limit(self, limit):
        return self

      def stream(self):
        return iter(self._docs)

    class _MockCollection:

      def __init__(self, docs):
        self._docs = docs

      def collection(self, name):
        return self

      def where(self, filter):  # pylint: disable=redefined-builtin
        return _MockQuery(self._docs)

    docs = [
      _MockDoc("j1", None),
      _MockDoc("j2", 0.2),
    ]

    mock_client = _MockCollection(docs)

    # Act
    jokes = joke_auto_fns._query_seasonal_category_jokes(
      mock_client, "Halloween")

    # Assert
    assert len(jokes) == 2
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[1]["joke_id"] == "j1"
