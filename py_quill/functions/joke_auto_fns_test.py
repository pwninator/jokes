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


@pytest.fixture(name='mock_services')
def mock_services_fixture(monkeypatch):
  """Fixture that mocks external services using monkeypatch."""
  mock_firestore = Mock()
  mock_fcm = Mock()

  monkeypatch.setattr('functions.joke_auto_fns.firestore', mock_firestore)
  monkeypatch.setattr('functions.joke_auto_fns.firebase_cloud_messaging',
                      mock_fcm)

  return mock_firestore, mock_fcm


@pytest.fixture(name='mock_single_notification')
def mock_single_notification_fixture(monkeypatch):
  """Fixture that mocks _send_single_joke_notification function."""
  mock_send_single = Mock()
  monkeypatch.setattr('functions.joke_auto_fns._send_single_joke_notification',
                      mock_send_single)
  return mock_send_single


@pytest.fixture(autouse=True, name='mock_logger')
def mock_logger_fixture(monkeypatch):
  """Silence firebase logger interactions during tests."""
  mock_log = Mock()
  monkeypatch.setattr('functions.joke_auto_fns.logger', mock_log)
  return mock_log


class TestSendDailyJokeNotification:
  """Tests for send_daily_joke_notification function."""

  def test_valid_utc_datetime_sends_both_notifications(
      self, mock_single_notification):
    """It should send notifications for current and next day."""
    test_utc = datetime.datetime(2024,
                                 1,
                                 15,
                                 14,
                                 30,
                                 tzinfo=datetime.timezone.utc)

    joke_auto_fns._send_daily_joke_notification(now=test_utc,
                                                schedule_name="test_schedule")

    assert mock_single_notification.call_count == 2
    first_kwargs = mock_single_notification.call_args_list[0].kwargs
    second_kwargs = mock_single_notification.call_args_list[1].kwargs
    assert first_kwargs == {
      'schedule_name': "test_schedule",
      'joke_date': datetime.date(2024, 1, 15),
      'notification_hour': 2,
      'topic_suffix': "c",
    }
    assert second_kwargs == {
      'schedule_name': "test_schedule",
      'joke_date': datetime.date(2024, 1, 16),
      'notification_hour': 2,
      'topic_suffix': "n",
    }

  def test_invalid_timezone_raises_error(self):
    with pytest.raises(ValueError, match="timezone information"):
      joke_auto_fns._send_daily_joke_notification(
        now=datetime.datetime(2024, 1, 15, 14, 30))

  def test_9am_pst_sends_additional_notification(self,
                                                 mock_single_notification):
    pst_time = datetime.datetime(2024,
                                 1,
                                 15,
                                 9,
                                 0,
                                 tzinfo=datetime.timezone(
                                   datetime.timedelta(hours=-8)))

    joke_auto_fns._send_daily_joke_notification(now=pst_time,
                                                schedule_name="test_schedule")

    assert mock_single_notification.call_count == 3
    third_kwargs = mock_single_notification.call_args_list[2].kwargs
    assert third_kwargs['schedule_name'] == "test_schedule"
    assert third_kwargs['joke_date'] == datetime.date(2024, 1, 15)
    assert 'notification_hour' not in third_kwargs
    assert 'topic_suffix' not in third_kwargs

  def test_not_9am_pst_no_extra_notification(self, mock_single_notification):
    pst_time = datetime.datetime(2024,
                                 1,
                                 15,
                                 8,
                                 0,
                                 tzinfo=datetime.timezone(
                                   datetime.timedelta(hours=-8)))

    joke_auto_fns._send_daily_joke_notification(now=pst_time,
                                                schedule_name="test_schedule")

    assert mock_single_notification.call_count == 2


class TestSendSingleJokeNotification:
  """Tests for send_single_joke_notification function."""

  def test_joke_found_sends_notification(self, mock_services):
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test_joke",
                                 setup_text="s",
                                 punchline_text="p")
    mock_firestore.get_daily_jokes.return_value = [test_joke]

    joke_auto_fns._send_single_joke_notification(
      schedule_name="schedule",
      joke_date=datetime.date(2024, 1, 15),
      notification_hour=14,
      topic_suffix="c",
    )

    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "schedule_14c", test_joke)

  def test_joke_not_found_no_notification(self, mock_services):
    mock_firestore, mock_fcm = mock_services
    mock_firestore.get_daily_jokes.return_value = []

    joke_auto_fns._send_single_joke_notification(
      schedule_name="schedule",
      joke_date=datetime.date(2024, 1, 15),
      notification_hour=9,
      topic_suffix="n",
    )

    mock_fcm.send_punny_joke_notification.assert_not_called()


class TestNotifyAllJokeSchedules:
  """Tests for notify_all_joke_schedules helper."""

  def test_calls_notification_for_each_schedule(self, monkeypatch):
    schedules = ["daily_jokes", "holiday_jokes", "kids_jokes"]
    monkeypatch.setattr(
      'functions.joke_auto_fns.firestore.list_joke_schedules',
      lambda: schedules)
    calls = []
    monkeypatch.setattr(
      'functions.joke_auto_fns._send_daily_joke_notification',
      lambda now, schedule_name='daily_jokes': calls.append(
        (now, schedule_name)))

    scheduled_time = datetime.datetime(2024,
                                       1,
                                       15,
                                       14,
                                       30,
                                       tzinfo=datetime.timezone.utc)

    joke_auto_fns._notify_all_joke_schedules(scheduled_time)

    assert [c[1] for c in calls] == schedules


class TestDecayRecentJokeStats:
  """Tests for the recent joke stats decay job."""

  def test_updates_counters_when_last_update_stale(self, monkeypatch):
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
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

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch

    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    assert payload["num_viewed_users_recent"] == pytest.approx(90.0)
    assert payload["num_saved_users_recent"] == pytest.approx(45.0)
    assert payload["num_shared_users_recent"] == pytest.approx(9.0)
    assert payload["is_public"] is True
    assert payload[
      "last_recent_stats_update_time"] is firestore.SERVER_TIMESTAMP

  def test_skips_when_recently_updated(self, monkeypatch):
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
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

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_not_called()

  def test_missing_recent_fields_are_skipped(self, monkeypatch):
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users_recent": None,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.APPROVED.value,
      "is_public": False,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

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
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(hours=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload == {"is_public": True}

  def test_daily_state_sets_is_public_true_when_public_timestamp_past(
      self, monkeypatch):
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users_recent": 10,
      "num_saved_users_recent": 5,
      "num_shared_users_recent": 2,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=1),
      "state": models.JokeState.DAILY.value,
      "public_timestamp": now_utc - datetime.timedelta(hours=1),
      "is_public": False,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    assert payload["is_public"] is True

  def test_daily_state_sets_is_public_false_when_public_timestamp_future(
      self, monkeypatch):
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users_recent": 10,
      "num_saved_users_recent": 5,
      "num_shared_users_recent": 2,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=1),
      "state": models.JokeState.DAILY.value,
      "public_timestamp": now_utc + datetime.timedelta(hours=12),
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    payload = mock_batch.update.call_args.args[1]
    assert payload["is_public"] is False

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

  def test_boosts_fraction_when_views_below_threshold_field_not_set(
      self, monkeypatch):
    """Test that jokes with < MIN_VIEWS_FOR_FRACTIONS views get boosted when fraction field not set."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 5,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.015)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.015)
    mock_random.assert_called_once_with(0.0, 0.02)

  def test_boosts_fraction_when_views_below_threshold_field_set(
      self, monkeypatch):
    """Test that jokes with < MIN_VIEWS_FOR_FRACTIONS views get boosted when fraction field already set."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 8,
      "num_saved_users_fraction": 0.03,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.04)
    mock_random.assert_called_once_with(0.0, 0.02)

  def test_boosts_fraction_when_views_exactly_nine(self, monkeypatch):
    """Test that jokes with exactly 9 views get boosted."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 9,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.0125)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.0125)

  def test_no_boost_when_views_at_threshold(self, monkeypatch):
    """Test that jokes with exactly MIN_VIEWS_FOR_FRACTIONS views do not get boosted."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS,
      "num_saved_users_fraction": 0.05,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform - should not be called
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert "num_saved_users_fraction" not in payload
    mock_random.assert_not_called()

  def test_no_boost_when_views_above_threshold(self, monkeypatch):
    """Test that jokes with >= MIN_VIEWS_FOR_FRACTIONS views do not get boosted."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": MIN_VIEWS_FOR_FRACTIONS + 10,
      "num_saved_users_fraction": 0.1,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform - should not be called
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert "num_saved_users_fraction" not in payload
    mock_random.assert_not_called()

  def test_boost_with_zero_views(self, monkeypatch):
    """Test that jokes with 0 views get boosted."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": 0,
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.02)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.02)

  def test_boost_handles_invalid_fraction_type(self, monkeypatch):
    """Test that invalid fraction types are treated as 0.0."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
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

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.01)

  def test_boost_handles_invalid_view_count_type(self, monkeypatch):
    """Test that invalid view count types are treated as 0."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)
    doc = MagicMock()
    doc.exists = True
    doc.reference = MagicMock()
    doc.to_dict.return_value = {
      "num_viewed_users": "invalid",
      "last_recent_stats_update_time": now_utc - datetime.timedelta(days=2),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform to return a predictable value
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    mock_batch.update.assert_called_once()
    payload = mock_batch.update.call_args.args[1]
    assert payload["num_saved_users_fraction"] == pytest.approx(0.01)

  def test_boost_statistics_tracked(self, monkeypatch):
    """Test that boosted jokes are counted in statistics."""
    now_utc = datetime.datetime(2024,
                                1,
                                20,
                                0,
                                0,
                                tzinfo=datetime.timezone.utc)

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

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.stream.return_value = [doc1, doc2]
    mock_db.batch.return_value = mock_batch
    monkeypatch.setattr('functions.joke_auto_fns.firestore.db',
                        lambda: mock_db)

    # Mock random.uniform
    mock_random = Mock(return_value=0.01)
    monkeypatch.setattr('functions.joke_auto_fns.random.uniform', mock_random)

    # Mock category refresh to return empty stats
    mock_category_refresh = Mock(
      return_value={
        "categories_processed": 0,
        "categories_updated": 0,
        "categories_emptied": 0,
        "categories_failed": 0
      })
    monkeypatch.setattr('functions.joke_auto_fns._refresh_category_caches',
                        mock_category_refresh)

    result = joke_auto_fns._joke_daily_maintenance_internal(now_utc)  # pylint: disable=protected-access

    assert result["jokes_boosted"] == 1


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
  """Tests for syncing jokes to the search subcollection."""

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
    mock_main_collection = MagicMock()
    mock_joke_doc_ref = MagicMock()
    mock_search_sub_collection = MagicMock()
    mock_search_doc_ref = MagicMock()

    mock_db.collection.return_value = mock_main_collection
    mock_main_collection.document.return_value = mock_joke_doc_ref
    mock_joke_doc_ref.collection.return_value = mock_search_sub_collection
    mock_search_sub_collection.document.return_value = mock_search_doc_ref

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

    mock_search_doc_ref.get.side_effect = mock_get
    mock_search_doc_ref.set.side_effect = mock_set

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
