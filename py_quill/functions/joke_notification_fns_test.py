"""Tests for joke_notification_fns helper module."""

from __future__ import annotations

import datetime
from unittest.mock import Mock

import pytest
from common import models
from functions import joke_notification_fns


@pytest.fixture(name='mock_services')
def mock_services_fixture(monkeypatch):
  """Fixture that mocks external services using monkeypatch."""
  mock_firestore = Mock()
  mock_fcm = Mock()

  monkeypatch.setattr('functions.joke_notification_fns.firestore',
                      mock_firestore)
  monkeypatch.setattr(
    'functions.joke_notification_fns.firebase_cloud_messaging', mock_fcm)

  return mock_firestore, mock_fcm


@pytest.fixture(name='mock_single_notification')
def mock_single_notification_fixture(monkeypatch):
  """Fixture that mocks _send_single_joke_notification function."""
  mock_send_single = Mock()
  monkeypatch.setattr(
    'functions.joke_notification_fns._send_single_joke_notification',
    mock_send_single)
  return mock_send_single


@pytest.fixture(autouse=True, name='mock_logger')
def mock_logger_fixture(monkeypatch):
  """Silence firebase logger interactions during tests."""
  mock_log = Mock()
  monkeypatch.setattr('functions.joke_notification_fns.logger', mock_log)
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

    joke_notification_fns._send_daily_joke_notification(
      now=test_utc, schedule_name="test_schedule")

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
      joke_notification_fns._send_daily_joke_notification(
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

    joke_notification_fns._send_daily_joke_notification(
      now=pst_time, schedule_name="test_schedule")

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

    joke_notification_fns._send_daily_joke_notification(
      now=pst_time, schedule_name="test_schedule")

    assert mock_single_notification.call_count == 2


class TestSendSingleJokeNotification:
  """Tests for send_single_joke_notification function."""

  def test_joke_found_sends_notification(self, mock_services):
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test_joke",
                                 setup_text="s",
                                 punchline_text="p")
    mock_firestore.get_daily_jokes.return_value = [test_joke]

    joke_notification_fns._send_single_joke_notification(
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

    joke_notification_fns._send_single_joke_notification(
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
      'functions.joke_notification_fns.firestore.list_joke_schedules',
      lambda: schedules)
    calls = []
    monkeypatch.setattr(
      'functions.joke_notification_fns._send_daily_joke_notification',
      lambda now, schedule_name='daily_jokes': calls.append(
        (now, schedule_name)))

    scheduled_time = datetime.datetime(2024,
                                       1,
                                       15,
                                       14,
                                       30,
                                       tzinfo=datetime.timezone.utc)

    joke_notification_fns._notify_all_joke_schedules(scheduled_time)

    assert [c[1] for c in calls] == schedules
