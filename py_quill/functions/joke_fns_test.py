"""Tests for the joke_fns module."""
import datetime
import zoneinfo
from unittest.mock import MagicMock, Mock

import pytest
from common import models
from functions import joke_fns
from google.cloud.firestore_v1.vector import Vector


class DummyReq:
  """Dummy request class for testing."""

  def __init__(self,
               is_json=True,
               data=None,
               args=None,
               headers=None,
               path="",
               method='POST'):
    self.is_json = is_json
    self._data = data or {}
    self.args = args or {}
    self.headers = headers or {}
    self.path = path
    self.method = method

  def get_json(self):
    """Dummy request class for testing."""
    return {"data": self._data}


def test_create_joke_sets_admin_owner_and_draft(monkeypatch):
  """Test that the create_joke function sets the admin owner and draft state."""
  # Arrange
  # Force unauthenticated
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: None)

  saved = None

  def fake_upsert(joke):
    nonlocal saved
    saved = joke
    joke.key = "key123"
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(data={
    "setup_text": "s",
    "punchline_text": "p",
    "admin_owned": True,
  })

  # Act
  resp = joke_fns.create_joke(req)

  # Assert
  assert saved is not None
  assert saved.owner_user_id == "ADMIN"
  assert saved.state == models.JokeState.DRAFT
  assert resp["data"]["joke_data"]["state"] == "DRAFT"
  assert resp["data"]["joke_data"]["key"] == "key123"


def test_create_joke_sets_user_owner_when_not_admin(monkeypatch):
  """Test that the create_joke function sets the user owner when not admin."""
  # Arrange
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: "user1")

  saved = None

  def fake_upsert(joke):
    nonlocal saved
    saved = joke
    joke.key = "key123"
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(data={
    "setup_text": "s",
    "punchline_text": "p",
    "admin_owned": False,
  })

  # Act
  joke_fns.create_joke(req)

  # Assert
  assert saved is not None
  assert saved.owner_user_id == "user1"
  assert saved.state == models.JokeState.DRAFT


def test_populate_joke_sets_state_unreviewed_and_persists(monkeypatch):
  """Test that populate_joke sets state to UNREVIEWED and saves it."""
  # Arrange
  monkeypatch.setattr(joke_fns,
                      "get_user_id",
                      lambda req, allow_unauthenticated=True: "user1")

  # Return a basic joke from internal populate and simulate internal save to UNREVIEWED
  def fake_populate_internal(**kwargs):
    joke_id = kwargs.get("joke_id", "jk123")
    j = models.PunnyJoke(key=joke_id, setup_text="s", punchline_text="p")
    # Simulate internal logic that sets to UNREVIEWED and persists
    j.state = models.JokeState.UNREVIEWED
    joke_fns.firestore.upsert_punny_joke(j)
    return j

  monkeypatch.setattr(joke_fns, "_populate_joke_internal",
                      fake_populate_internal)

  captured = {"saved": None}

  def fake_upsert(joke):
    captured["saved"] = joke
    return joke

  monkeypatch.setattr(joke_fns.firestore, "upsert_punny_joke", fake_upsert)

  req = DummyReq(
    data={
      "joke_id": "jk123",
      "image_quality": "medium",
      "images_only": False,
      "overwrite": True,
    })

  # Act
  resp = joke_fns.populate_joke(req)

  # Assert - state should be UNREVIEWED and persisted
  assert captured["saved"] is not None
  assert captured["saved"].state == models.JokeState.UNREVIEWED
  assert resp["data"]["joke_data"]["state"] == "UNREVIEWED"
  assert resp["data"]["joke_data"]["key"] == "jk123"


def test_search_jokes_applies_public_only_filter_by_default(monkeypatch):
  """Test that search_jokes applies the public_only filter by default."""
  captured = {}

  def fake_search_jokes(query=None,
                        field_filters=None,
                        limit=None,
                        distance_measure=None,
                        distance_threshold=None,
                        label=None,
                        **kwargs):  # pylint: disable=unused-argument
    captured['filters'] = list(field_filters or [])
    captured['label'] = label
    return []

  monkeypatch.setattr(joke_fns.search, 'search_jokes', fake_search_jokes)

  req = DummyReq(is_json=True,
                 data={
                   'search_query': 'cats',
                   'label': 'test_label'
                 })

  _ = joke_fns.search_jokes(req)

  assert 'filters' in captured
  filters = captured['filters']
  assert len(filters) == 1
  field, op, value = filters[0]
  assert field == 'public_timestamp'
  assert op == '<='
  assert isinstance(value, datetime.datetime)
  assert value.tzinfo == zoneinfo.ZoneInfo("America/Los_Angeles")
  assert captured['label'] == 'test_label'


def test_search_jokes_omits_filter_when_public_only_false(monkeypatch):
  """Test that search_jokes omits the public_only filter when public_only is False."""
  captured = {}

  def fake_search_jokes(query=None,
                        field_filters=None,
                        limit=None,
                        distance_measure=None,
                        distance_threshold=None,
                        label=None,
                        **kwargs):  # pylint: disable=unused-argument
    captured['filters'] = list(field_filters or [])
    captured['label'] = label
    return []

  monkeypatch.setattr(joke_fns.search, 'search_jokes', fake_search_jokes)

  req = DummyReq(is_json=True,
                 data={
                   'search_query': 'dogs',
                   'public_only': False
                 })

  _ = joke_fns.search_jokes(req)

  assert 'filters' in captured
  assert captured['filters'] == []
  assert captured['label'] == 'unknown'


@pytest.fixture(name="mock_services")
def mock_services_fixture(monkeypatch):
  """Fixture that mocks external services using monkeypatch."""
  mock_firestore = Mock()
  mock_fcm = Mock()

  monkeypatch.setattr('functions.joke_fns.firestore', mock_firestore)
  monkeypatch.setattr('functions.joke_fns.firebase_cloud_messaging', mock_fcm)

  return mock_firestore, mock_fcm


@pytest.fixture(name="mock_single_notification")
def mock_single_notification_fixture(monkeypatch):
  """Fixture that mocks send_single_joke_notification function."""
  mock_send_single = Mock()
  monkeypatch.setattr('functions.joke_fns.send_single_joke_notification',
                      mock_send_single)
  return mock_send_single


class TestSendDailyJokeNotification:
  """Tests for send_daily_joke_notification function."""

  def test_valid_utc_datetime_sends_both_notifications(
      self, mock_single_notification):
    """Test that valid UTC datetime sends both current and next date notifications."""
    # Arrange
    test_utc = datetime.datetime(2024,
                                 1,
                                 15,
                                 14,
                                 30,
                                 tzinfo=datetime.timezone.utc)

    # Act
    joke_fns.send_daily_joke_notification(now=test_utc,
                                          schedule_name="test_schedule")

    # Assert - should call send_single_joke_notification twice
    assert mock_single_notification.call_count == 2

    # First call should be for current date (UTC-12: 2024-01-15 02:30)
    first_call = mock_single_notification.call_args_list[0]
    assert first_call[1]['schedule_name'] == "test_schedule"
    assert first_call[1]['joke_date'] == datetime.date(
      2024, 1, 15)  # Current date in UTC-12
    assert first_call[1]['notification_hour'] == 2  # 14:30 UTC = 02:30 UTC-12
    assert first_call[1]['topic_suffix'] == "c"

    # Second call should be for next date
    second_call = mock_single_notification.call_args_list[1]
    assert second_call[1]['schedule_name'] == "test_schedule"
    assert second_call[1]['joke_date'] == datetime.date(2024, 1,
                                                        16)  # Next date
    assert second_call[1]['notification_hour'] == 2
    assert second_call[1]['topic_suffix'] == "n"

  def test_utc_minus_12_date_boundary_crossing(self, mock_single_notification):
    """Test date calculation when UTC-12 crosses to previous day."""
    # Arrange - early UTC time that becomes previous day in UTC-12
    test_utc = datetime.datetime(2024,
                                 1,
                                 15,
                                 5,
                                 0,
                                 tzinfo=datetime.timezone.utc)  # 5:00 UTC
    # UTC-12 would be 2024-01-14 17:00 (previous day)

    # Act
    joke_fns.send_daily_joke_notification(now=test_utc)

    # Assert - dates should be adjusted for UTC-12
    first_call = mock_single_notification.call_args_list[0]
    second_call = mock_single_notification.call_args_list[1]

    assert first_call[1]['joke_date'] == datetime.date(
      2024, 1, 14)  # Previous day in UTC-12
    assert first_call[1]['notification_hour'] == 17  # 5:00 UTC = 17:00 UTC-12
    assert second_call[1]['joke_date'] == datetime.date(
      2024, 1, 15)  # Current day in UTC-12

  def test_invalid_timezone_raises_error(self):
    """Test that naive datetime (no timezone) raises ValueError."""
    # Arrange - naive datetime (no timezone)
    naive_dt = datetime.datetime(2024, 1, 15, 14, 30)

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="now must have timezone information, got naive datetime"):
      joke_fns.send_daily_joke_notification(now=naive_dt)

  def test_different_timezone_converts_correctly(self,
                                                 mock_single_notification):
    """Test that different timezone is converted to UTC correctly."""
    # Arrange - EST timezone (UTC-5)
    est_tz = datetime.timezone(datetime.timedelta(hours=-5))
    est_dt = datetime.datetime(2024, 1, 15, 9, 30,
                               tzinfo=est_tz)  # 9:30 EST = 14:30 UTC

    # Act
    joke_fns.send_daily_joke_notification(now=est_dt)

    # Assert - should calculate correctly from EST to UTC to UTC-12
    first_call = mock_single_notification.call_args_list[0]
    assert first_call[1]['joke_date'] == datetime.date(
      2024, 1, 15)  # Current date in UTC-12
    assert first_call[1]['notification_hour'] == 2  # 14:30 UTC = 02:30 UTC-12

  def test_utc_timezone_still_works(self, mock_single_notification):
    """Test that UTC timezone still works as before."""
    # Arrange - UTC timezone
    test_utc = datetime.datetime(2024,
                                 1,
                                 15,
                                 14,
                                 30,
                                 tzinfo=datetime.timezone.utc)

    # Act
    joke_fns.send_daily_joke_notification(now=test_utc,
                                          schedule_name="test_schedule")

    # Assert - should work exactly as before
    assert mock_single_notification.call_count == 2
    first_call = mock_single_notification.call_args_list[0]
    assert first_call[1]['notification_hour'] == 2  # 14:30 UTC = 02:30 UTC-12

  def test_pacific_timezone_converts_correctly(self, mock_single_notification):
    """Test that Pacific timezone (original timezone) converts correctly."""
    # Arrange - Pacific timezone (UTC-8, like America/Los_Angeles)
    pacific_tz = datetime.timezone(datetime.timedelta(hours=-8))
    pacific_dt = datetime.datetime(2024, 1, 15, 6, 30,
                                   tzinfo=pacific_tz)  # 6:30 PST = 14:30 UTC

    # Act
    joke_fns.send_daily_joke_notification(now=pacific_dt)

    # Assert - should calculate correctly from PST to UTC to UTC-12
    first_call = mock_single_notification.call_args_list[0]
    assert first_call[1]['joke_date'] == datetime.date(
      2024, 1, 15)  # Current date in UTC-12
    assert first_call[1]['notification_hour'] == 2  # 14:30 UTC = 02:30 UTC-12

  def test_uses_default_schedule_name(self, mock_single_notification):
    """Test that default schedule name is used when none provided."""
    test_utc = datetime.datetime(2024,
                                 1,
                                 15,
                                 14,
                                 30,
                                 tzinfo=datetime.timezone.utc)

    # Act
    joke_fns.send_daily_joke_notification(now=test_utc)

    # Assert - should use default schedule name
    first_call = mock_single_notification.call_args_list[0]
    assert first_call[1]['schedule_name'] == "daily_jokes"

  def test_9am_pst_sends_additional_notification(self,
                                                 mock_single_notification):
    """Test that at 9am PST, an additional notification is sent with just the schedule name."""
    # Arrange - 9am PST (17:00 UTC)
    pst_tz = datetime.timezone(datetime.timedelta(hours=-8))
    pst_9am = datetime.datetime(2024, 1, 15, 9, 0, tzinfo=pst_tz)

    # Act
    joke_fns.send_daily_joke_notification(now=pst_9am,
                                          schedule_name="test_schedule")

    # Assert - should call send_single_joke_notification 3 times (2 regular + 1 for 9am PST)
    assert mock_single_notification.call_count == 3

    # Third call should be the 9am PST notification
    third_call = mock_single_notification.call_args_list[2]
    assert third_call[1]['schedule_name'] == "test_schedule"
    assert third_call[1]['joke_date'] == datetime.date(2024, 1, 15)  # PST date
    # notification_hour and topic_suffix should not be present (optional params)
    assert 'notification_hour' not in third_call[1] or third_call[1][
      'notification_hour'] is None
    assert 'topic_suffix' not in third_call[1] or third_call[1][
      'topic_suffix'] is None

  def test_not_9am_pst_no_additional_notification(self,
                                                  mock_single_notification):
    """Test that when it's not 9am PST, no additional notification is sent."""
    # Arrange - 8am PST (16:00 UTC)
    pst_tz = datetime.timezone(datetime.timedelta(hours=-8))
    pst_8am = datetime.datetime(2024, 1, 15, 8, 0, tzinfo=pst_tz)

    # Act
    joke_fns.send_daily_joke_notification(now=pst_8am,
                                          schedule_name="test_schedule")

    # Assert - should only call send_single_joke_notification 2 times (regular notifications only)
    assert mock_single_notification.call_count == 2

  def test_9am_pst_different_timezone_input(self, mock_single_notification):
    """Test that 9am PST is detected correctly even when input timezone is different."""
    # Arrange - UTC time that corresponds to 9am PST (17:00 UTC)
    utc_17 = datetime.datetime(2024,
                               1,
                               15,
                               17,
                               0,
                               tzinfo=datetime.timezone.utc)

    # Act
    joke_fns.send_daily_joke_notification(now=utc_17,
                                          schedule_name="test_schedule")

    # Assert - should call send_single_joke_notification 3 times (2 regular + 1 for 9am PST)
    assert mock_single_notification.call_count == 3

    # Third call should be the 9am PST notification
    third_call = mock_single_notification.call_args_list[2]
    assert third_call[1]['schedule_name'] == "test_schedule"
    assert third_call[1]['joke_date'] == datetime.date(2024, 1, 15)  # PST date


class TestSendSingleJokeNotification:
  """Tests for send_single_joke_notification function."""

  def test_joke_found_sends_notification(self, mock_services):
    """Test that when joke is found, notification is sent."""
    # Arrange
    mock_firestore, mock_fcm = mock_services

    test_joke = models.PunnyJoke(
      key="test_joke_id",
      setup_text="Why did the chicken cross the road?",
      punchline_text="To get to the other side!",
    )
    mock_firestore.get_daily_joke.return_value = test_joke

    test_date = datetime.date(2024, 1, 15)

    # Act
    joke_fns.send_single_joke_notification(schedule_name="test_schedule",
                                           joke_date=test_date,
                                           notification_hour=14,
                                           topic_suffix="c")

    # Assert
    mock_firestore.get_daily_joke.assert_called_once_with(
      "test_schedule", test_date)
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "test_schedule_14c", test_joke)

  def test_joke_not_found_no_notification_sent(self, mock_services):
    """Test that when joke is not found, no notification is sent and message is logged."""
    # Arrange
    mock_firestore, mock_fcm = mock_services
    mock_firestore.get_daily_joke.return_value = None

    test_date = datetime.date(2024, 1, 15)

    # Act
    joke_fns.send_single_joke_notification(schedule_name="test_schedule",
                                           joke_date=test_date,
                                           notification_hour=9,
                                           topic_suffix="n")

    # Assert
    mock_firestore.get_daily_joke.assert_called_once_with(
      "test_schedule", test_date)
    mock_fcm.send_punny_joke_notification.assert_not_called()

  def test_topic_name_formation(self, mock_services):
    """Test that topic names are formed correctly."""
    # Arrange
    mock_firestore, mock_fcm = mock_services

    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    test_cases = [
      ("my_schedule", 0, "c", "my_schedule_00c"),
      ("daily_jokes", 23, "n", "daily_jokes_23n"),
      ("test", 9, "c", "test_09c"),
    ]

    for schedule_name, hour, suffix, expected_topic in test_cases:
      # Reset mocks
      mock_fcm.reset_mock()

      # Act
      joke_fns.send_single_joke_notification(schedule_name=schedule_name,
                                             joke_date=datetime.date(
                                               2024, 1, 15),
                                             notification_hour=hour,
                                             topic_suffix=suffix)

      # Assert
      mock_fcm.send_punny_joke_notification.assert_called_once_with(
        expected_topic, test_joke)

  def test_hour_padding_in_topic_name(self, mock_services):
    """Test that hours are zero-padded in topic names."""
    # Arrange
    mock_firestore, mock_fcm = mock_services

    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    # Act - test single digit hour
    joke_fns.send_single_joke_notification(
      schedule_name="test",
      joke_date=datetime.date(2024, 1, 15),
      notification_hour=5,  # Single digit
      topic_suffix="c")

    # Assert - should be zero-padded
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "test_05c",
      test_joke  # Note: 05, not just 5
    )

  @pytest.mark.parametrize("hour,expected_topic", [
    (0, "schedule_00c"),
    (5, "schedule_05c"),
    (12, "schedule_12c"),
    (23, "schedule_23c"),
  ])
  def test_hour_formatting_parametrized(self, mock_services, hour,
                                        expected_topic):
    """Test hour formatting with parametrized test cases."""
    # Arrange
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    # Act
    joke_fns.send_single_joke_notification(schedule_name="schedule",
                                           joke_date=datetime.date(
                                             2024, 1, 15),
                                           notification_hour=hour,
                                           topic_suffix="c")

    # Assert
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      expected_topic, test_joke)

  def test_optional_parameters_uses_schedule_name_as_topic(
      self, mock_services):
    """Test that when optional parameters are not provided, topic name is just the schedule name."""
    # Arrange
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    # Act
    joke_fns.send_single_joke_notification(schedule_name="my_schedule",
                                           joke_date=datetime.date(
                                             2024, 1, 15))

    # Assert
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "my_schedule", test_joke)

  def test_optional_parameters_with_none_values(self, mock_services):
    """Test that when optional parameters are explicitly set to None, topic name is just the schedule name."""
    # Arrange
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    # Act
    joke_fns.send_single_joke_notification(schedule_name="test_schedule",
                                           joke_date=datetime.date(
                                             2024, 1, 15),
                                           notification_hour=None,
                                           topic_suffix=None)

    # Assert
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "test_schedule", test_joke)

  def test_partial_optional_parameters_still_uses_schedule_name(
      self, mock_services):
    """Test that when only one optional parameter is provided, topic name is still just the schedule name."""
    # Arrange
    mock_firestore, mock_fcm = mock_services
    test_joke = models.PunnyJoke(key="test",
                                 setup_text="Test setup",
                                 punchline_text="Test punchline")
    mock_firestore.get_daily_joke.return_value = test_joke

    # Act - only provide notification_hour, not topic_suffix
    joke_fns.send_single_joke_notification(schedule_name="partial_schedule",
                                           joke_date=datetime.date(
                                             2024, 1, 15),
                                           notification_hour=9)

    # Assert - should still use just schedule name since topic_suffix is None
    mock_fcm.send_punny_joke_notification.assert_called_once_with(
      "partial_schedule", test_joke)


class TestNotifyAllJokeSchedules:
  """Tests for notify_all_joke_schedules helper."""

  def test_calls_notification_for_each_schedule(self, monkeypatch):
    """Test that notify_all_joke_schedules calls send_daily_joke_notification for each schedule."""
    # Arrange
    schedules = ["daily_jokes", "holiday_jokes", "kids_jokes"]
    monkeypatch.setattr('functions.joke_fns.firestore.list_joke_schedules',
                        lambda: schedules)

    calls = []

    def _capture(now, schedule_name="daily_jokes"):
      calls.append((now, schedule_name))

    monkeypatch.setattr('functions.joke_fns.send_daily_joke_notification',
                        _capture)

    scheduled_time = datetime.datetime(2024,
                                       1,
                                       15,
                                       14,
                                       30,
                                       tzinfo=datetime.timezone.utc)

    # Act
    joke_fns.notify_all_joke_schedules(scheduled_time)

    # Assert
    assert [c[1] for c in calls] == schedules


class TestSearchJokes:
  """Tests for search_jokes function."""

  @pytest.fixture(name="mock_search")
  def mock_search_fixture(self, monkeypatch):
    """Fixture that mocks the search.search_jokes function."""
    mock_search_jokes = Mock()
    monkeypatch.setattr('functions.joke_fns.search.search_jokes',
                        mock_search_jokes)
    return mock_search_jokes

  def test_valid_request_returns_jokes_with_distance(self, mock_search):
    """Test that a valid request returns jokes with id and vector distance."""

    # Arrange
    class _J:

      def __init__(self, key):
        self.joke = Mock(key=key)
        self.vector_distance = 0.0

    j1 = _J('joke1')
    j1.vector_distance = 0.1
    j2 = _J('joke2')
    j2.vector_distance = 0.2
    mock_search.return_value = [j1, j2]

    req = MagicMock()
    req.path = "/"
    req.method = 'POST'
    req.is_json = True
    req.get_json.return_value = {
      "data": {
        "search_query": "test query",
        "max_results": 5,
        "label": "test_label"
      }
    }

    # Act
    resp = joke_fns.search_jokes(req)

    # Assert
    # match_mode default is TIGHT which passes distance_threshold
    mock_search.assert_called_once()
    called_kwargs = mock_search.call_args.kwargs
    assert called_kwargs['query'] == 'test query'
    assert called_kwargs['label'] == 'test_label'
    assert called_kwargs['limit'] == 5
    assert called_kwargs['distance_threshold'] == 0.32
    filters = called_kwargs['field_filters']
    assert isinstance(filters, list)
    assert len(filters) == 1
    field, op, value = filters[0]
    assert field == 'public_timestamp'
    assert op == '<='
    assert isinstance(value, datetime.datetime)
    assert resp["data"]["jokes"] == [
      {
        "joke_id": "joke1",
        "vector_distance": 0.1
      },
      {
        "joke_id": "joke2",
        "vector_distance": 0.2
      },
    ]

  def test_missing_query_returns_error(self, mock_search):
    """Test that a request with a missing search query returns an error."""
    # Arrange
    req = MagicMock()
    req.path = "/"
    req.method = 'POST'
    req.is_json = True
    req.get_json.return_value = {"data": {"max_results": 5}}

    # Act
    resp = joke_fns.search_jokes(req)

    # Assert
    mock_search.assert_not_called()
    assert "Search query is required" in resp["data"]["error"]


class TestOnJokeWrite:
  """Tests for the on_joke_write cloud function."""

  @pytest.fixture(name="mock_get_joke_embedding")
  def mock_get_joke_embedding_fixture(self, monkeypatch):
    """Fixture that mocks the get_joke_embedding function."""
    mock_embedding_fn = Mock(return_value=([1.0, 2.0, 3.0],
                                           models.GenerationMetadata()))
    monkeypatch.setattr(joke_fns, "get_joke_embedding", mock_embedding_fn)
    return mock_embedding_fn

  @pytest.fixture(name="mock_firestore_service")
  def mock_firestore_service_fixture(self, monkeypatch):
    """Fixture that mocks the firestore service."""
    mock_firestore = Mock()
    # Mock the update_punny_joke function that's actually called
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_fns, "firestore", mock_firestore)
    return mock_firestore

  def test_joke_created_calculates_embedding(self, mock_get_joke_embedding,
                                             mock_firestore_service):
    """Test that a new joke gets its embedding calculated."""
    # Arrange
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p").to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_joke_updated_with_text_change_recalculates_embedding(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that an updated joke with text change gets its embedding recalculated."""
    # Arrange
    before_joke_dict = models.PunnyJoke(key="joke1",
                                        setup_text="s",
                                        punchline_text="p").to_dict()
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s_new",
                                       punchline_text="p").to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_joke_updated_without_text_change_does_not_recalculate_embedding(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that an updated joke without text change does not get its embedding recalculated."""
    # Arrange
    before_joke_dict = models.PunnyJoke(key="joke1",
                                        setup_text="s",
                                        punchline_text="p",
                                        pun_word="pun",
                                        zzz_joke_text_embedding=Vector(
                                          [1.0, 2.0, 3.0])).to_dict()
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p",
                                       pun_word="pun_new",
                                       zzz_joke_text_embedding=Vector(
                                         [1.0, 2.0, 3.0])).to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_joke_deleted_does_nothing(self, mock_get_joke_embedding,
                                     mock_firestore_service):
    """Test that a deleted joke does nothing."""
    # Arrange
    before_joke_dict = models.PunnyJoke(key="joke1",
                                        setup_text="s",
                                        punchline_text="p").to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=None)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_draft_joke_does_not_calculate_embedding(self,
                                                   mock_get_joke_embedding,
                                                   mock_firestore_service):
    """Test that draft jokes do not get their embedding calculated even when new."""
    # Arrange
    draft_joke = models.PunnyJoke(key="joke1",
                                  setup_text="s",
                                  punchline_text="p",
                                  state=models.JokeState.DRAFT)
    after_joke_dict = draft_joke.to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_draft_joke_text_change_does_not_recalculate_embedding(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that draft jokes do not get embedding recalculated even when text changes."""
    # Arrange
    before_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="old_setup",
      punchline_text="p",
      state=models.JokeState.DRAFT).to_dict()
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="new_setup",
                                       punchline_text="p",
                                       state=models.JokeState.DRAFT).to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_joke_missing_embedding_gets_calculated_even_without_text_change(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that a joke without embedding gets embedding calculated even without text change."""
    # Arrange
    before_joke_dict = models.PunnyJoke(key="joke1",
                                        setup_text="s",
                                        punchline_text="p",
                                        zzz_joke_text_embedding=Vector(
                                          [1, 2, 3])).to_dict()
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p",
                                       zzz_joke_text_embedding=None).to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_joke_empty_embedding_list_gets_calculated(self,
                                                     mock_get_joke_embedding,
                                                     mock_firestore_service):
    """Test that a joke with empty embedding list gets embedding calculated."""
    # Arrange
    before_joke_dict = models.PunnyJoke(key="joke1",
                                        setup_text="s",
                                        punchline_text="p",
                                        zzz_joke_text_embedding=Vector(
                                          [1, 2, 3])).to_dict()
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p",
                                       zzz_joke_text_embedding=None).to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_metadata_handling_when_dict(self, monkeypatch,
                                       mock_firestore_service):
    """Test metadata handling when generation_metadata is a dict."""
    # Arrange
    new_metadata = models.GenerationMetadata()
    new_metadata.generations = [
      models.SingleGenerationMetadata(model_name="test",
                                      label="test_generation")
    ]

    def mock_get_joke_embedding_func(_joke):
      return ([1.0, 2.0, 3.0], new_metadata)

    monkeypatch.setattr(joke_fns, "get_joke_embedding",
                        mock_get_joke_embedding_func)

    existing_metadata_dict = {
      "generations": [{
        "model_name": "old",
        "label": "old_generation"
      }]
    }
    existing_metadata = models.GenerationMetadata.from_dict(
      existing_metadata_dict)
    after_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      generation_metadata=existing_metadata).to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_firestore_service.update_punny_joke.assert_called_once()
    update_call = mock_firestore_service.update_punny_joke.call_args[0][
      1]  # Get the update_data parameter
    updated_metadata = update_call["generation_metadata"]
    assert len(
      updated_metadata["generations"]) == 2  # Should have both old and new

  def test_metadata_handling_when_none(self, monkeypatch,
                                       mock_firestore_service):
    """Test metadata handling when generation_metadata is None."""
    # Arrange
    new_metadata = models.GenerationMetadata()
    new_metadata.generations = [
      models.SingleGenerationMetadata(model_name="test",
                                      label="test_generation")
    ]

    def mock_get_joke_embedding_func(_joke):
      return ([1.0, 2.0, 3.0], new_metadata)

    monkeypatch.setattr(joke_fns, "get_joke_embedding",
                        mock_get_joke_embedding_func)

    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p",
                                       generation_metadata=None).to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_firestore_service.update_punny_joke.assert_called_once()
    update_call = mock_firestore_service.update_punny_joke.call_args[0][
      1]  # Get the update_data parameter
    updated_metadata = update_call["generation_metadata"]
    assert len(
      updated_metadata["generations"]) == 1  # Should have only the new one

  def test_metadata_handling_when_existing_object(self, monkeypatch,
                                                  mock_firestore_service):
    """Test metadata handling when generation_metadata is already a GenerationMetadata object."""
    # Arrange
    new_metadata = models.GenerationMetadata()
    new_metadata.generations = [
      models.SingleGenerationMetadata(model_name="test",
                                      label="test_generation")
    ]

    def mock_get_joke_embedding_func(_joke):
      return ([1.0, 2.0, 3.0], new_metadata)

    monkeypatch.setattr(joke_fns, "get_joke_embedding",
                        mock_get_joke_embedding_func)

    existing_metadata = models.GenerationMetadata()
    existing_metadata.generations = [
      models.SingleGenerationMetadata(model_name="old", label="old_generation")
    ]

    after_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      generation_metadata=existing_metadata).to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_firestore_service.update_punny_joke.assert_called_once()
    update_call = mock_firestore_service.update_punny_joke.call_args[0][
      1]  # Get the update_data parameter
    updated_metadata = update_call["generation_metadata"]
    assert len(
      updated_metadata["generations"]) == 2  # Should have both old and new

  def test_joke_with_none_key_does_not_update_firestore(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that a joke with None key does not update Firestore."""
    # Arrange
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p").to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)
    mock_event.params = {"joke_id": None}  # Test with None event param key

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once(
    )  # Embedding calculation happens
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_joke_with_empty_key_does_not_update_firestore(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that a joke with empty key does not update Firestore."""
    # Arrange
    after_joke_dict = models.PunnyJoke(key="joke1",
                                       setup_text="s",
                                       punchline_text="p").to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)
    mock_event.params = {"joke_id": ""}  # Test with empty event param key

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once(
    )  # Embedding calculation happens
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_setup_text_only_change_triggers_embedding_update(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that changing only setup text triggers embedding recalculation."""
    # Arrange
    before_joke_dict = models.PunnyJoke(
      key="joke1", setup_text="old setup",
      punchline_text="same punchline").to_dict()
    after_joke_dict = models.PunnyJoke(
      key="joke1", setup_text="new setup",
      punchline_text="same punchline").to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_punchline_text_only_change_triggers_embedding_update(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that changing only punchline text triggers embedding recalculation."""
    # Arrange
    before_joke_dict = models.PunnyJoke(
      key="joke1", setup_text="same setup",
      punchline_text="old punchline").to_dict()
    after_joke_dict = models.PunnyJoke(
      key="joke1", setup_text="same setup",
      punchline_text="new punchline").to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

  def test_joke_with_text_change_and_popularity_change_updates_both(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that changing both text and popularity metrics updates both embedding and popularity score."""
    # Arrange
    before_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="old setup",
      punchline_text="p",
      num_saves=1,
      num_shares=1,
      popularity_score=6,  # Correct for before: 1 + (1 * 5) = 6
      zzz_joke_text_embedding=Vector([1.0, 2.0, 3.0])).to_dict()
    after_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="new setup",  # Text changed
      punchline_text="p",
      num_saves=1,
      num_shares=3,  # Shares changed from 1 to 3
      popularity_score=6,  # Incorrect now - should be 1 + (3 * 5) = 16
      zzz_joke_text_embedding=Vector([1.0, 2.0, 3.0])).to_dict()
    mock_event = self._create_mock_event(before_data=before_joke_dict,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()  # Text changed
    mock_firestore_service.update_punny_joke.assert_called_once()

    # Check that both embedding and popularity score are updated in single call
    call_args = mock_firestore_service.update_punny_joke.call_args[0]
    update_data = call_args[1]
    assert "zzz_joke_text_embedding" in update_data
    assert "popularity_score" in update_data
    assert update_data["popularity_score"] == 16

  def test_new_joke_with_incorrect_popularity_score_gets_updated(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that a new joke with incorrect popularity score gets updated."""
    # Arrange
    after_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saves=5,
      num_shares=2,
      popularity_score=0  # Incorrect - should be 5 + (2 * 5) = 15
    ).to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

    # Check that both embedding and popularity score are updated
    call_args = mock_firestore_service.update_punny_joke.call_args[0]
    update_data = call_args[1]  # Second argument is the update data
    assert "zzz_joke_text_embedding" in update_data
    assert "popularity_score" in update_data
    assert update_data["popularity_score"] == 15

  def test_new_joke_with_correct_popularity_score_does_not_update(
      self, mock_get_joke_embedding, mock_firestore_service):
    """Test that a new joke with correct popularity score does not get updated."""
    # Arrange
    after_joke_dict = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saves=3,
      num_shares=1,
      popularity_score=8  # Correct - 3 + (1 * 5) = 8
    ).to_dict()
    mock_event = self._create_mock_event(before_data=None,
                                         after_data=after_joke_dict)

    # Act
    joke_fns.on_joke_write.__wrapped__(mock_event)

    # Assert
    mock_get_joke_embedding.assert_called_once()
    mock_firestore_service.update_punny_joke.assert_called_once()

    # Check that only embedding is updated, not popularity score
    call_args = mock_firestore_service.update_punny_joke.call_args[0]
    update_data = call_args[1]
    assert "zzz_joke_text_embedding" in update_data
    assert "popularity_score" not in update_data

  def test_popularity_score_calculation_with_zero_values(self):
    """Test that popularity score calculation handles zero values correctly."""
    joke = models.PunnyJoke(key="joke1",
                            setup_text="s",
                            punchline_text="p",
                            num_saves=0,
                            num_shares=0,
                            popularity_score=0)

    expected_score = joke_fns.calculate_popularity_score(joke)
    assert expected_score == 0

  def test_popularity_score_calculation_with_large_values(self):
    """Test that popularity score calculation handles large values correctly."""
    joke = models.PunnyJoke(key="joke1",
                            setup_text="s",
                            punchline_text="p",
                            num_saves=100,
                            num_shares=50,
                            popularity_score=0)

    expected_score = joke_fns.calculate_popularity_score(joke)
    assert expected_score == 100 + (50 * 5)  # 100 + 250 = 350

  def test_popularity_score_calculation_with_none_values(self):
    """Test that popularity score calculation handles None values correctly."""
    joke = models.PunnyJoke(key="joke1",
                            setup_text="s",
                            punchline_text="p",
                            num_saves=None,
                            num_shares=None,
                            popularity_score=0)

    expected_score = joke_fns.calculate_popularity_score(joke)
    assert expected_score == 0

  def _create_mock_event(self, before_data, after_data):
    """Helper to create a mock firestore event."""
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()

    if before_data:
      event.data.before = MagicMock()
      event.data.before.to_dict.return_value = before_data
    else:
      event.data.before = None

    if after_data:
      event.data.after = MagicMock()
      event.data.after.to_dict.return_value = after_data
    else:
      event.data.after = None

    return event


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
    monkeypatch.setattr(joke_fns.image_generation, "generate_pun_image",
                        mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to not exist (new document)
    mock_doc.exists = False
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None,
                               after_data={"image_description": "desc"})

    # Act
    joke_fns.on_joke_category_write.__wrapped__(event)

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
    monkeypatch.setattr(joke_fns.image_generation, "generate_pun_image",
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
    monkeypatch.setattr(joke_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_fns.on_joke_category_write.__wrapped__(event)

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
    monkeypatch.setattr(joke_fns.image_generation, "generate_pun_image",
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
    monkeypatch.setattr(joke_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_fns.on_joke_category_write.__wrapped__(event)

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
    monkeypatch.setattr(joke_fns.image_generation, "generate_pun_image",
                        mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "same"},
                               after_data={"image_description": "same"})

    # Act
    joke_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()

  def test_missing_image_description_skips(self, monkeypatch):
    # Arrange
    mock_generate = MagicMock()
    monkeypatch.setattr(joke_fns.image_generation, "generate_pun_image",
                        mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None, after_data={})

    # Act
    joke_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()


class TestModifyJokeImage:
  """Tests for the modify_joke_image cloud function."""

  @pytest.fixture(name="mock_image_generation")
  def mock_image_generation_fixture(self, monkeypatch):
    """Fixture that mocks the image_generation service."""
    mock_image_gen = Mock()
    monkeypatch.setattr(joke_fns, "image_generation", mock_image_gen)
    return mock_image_gen

  @pytest.fixture(name="mock_firestore_service")
  def mock_firestore_service_fixture(self, monkeypatch):
    """Fixture that mocks the firestore service."""
    mock_firestore = Mock()
    monkeypatch.setattr(joke_fns, "firestore", mock_firestore)
    return mock_firestore

  def test_modify_joke_image_success(self, mock_image_generation,
                                     mock_firestore_service):
    """Test that modify_joke_image successfully modifies an image."""
    # Arrange
    req = DummyReq(data={
      "joke_id": "joke1",
      "setup_instruction": "make it funnier",
    })

    mock_joke = models.PunnyJoke(
      key="joke1",
      setup_text="test",
      punchline_text="test",
      setup_image_url="https://storage.googleapis.com/example/setup.png")
    mock_firestore_service.get_punny_joke.return_value = mock_joke

    mock_new_image = models.Image(url="http://example.com/new.png",
                                  gcs_uri="gs://example/new.png")
    mock_image_generation.modify_image.return_value = mock_new_image
    mock_firestore_service.upsert_punny_joke.return_value = mock_joke

    # Act
    resp = joke_fns.modify_joke_image(req)

    # Assert
    mock_firestore_service.get_punny_joke.assert_called_once_with("joke1")
    mock_image_generation.modify_image.assert_called_once()
    mock_firestore_service.upsert_punny_joke.assert_called_once()
    assert "data" in resp

  def test_modify_joke_image_no_instruction_error(self, mock_image_generation,
                                                  mock_firestore_service):
    """Test that modify_joke_image returns an error if no instruction is provided."""
    # Arrange
    req = DummyReq(data={"joke_id": "joke1"})

    # Act
    resp = joke_fns.modify_joke_image(req)

    # Assert
    assert "error" in resp["data"]
    assert "At least one instruction" in resp["data"]["error"]
    mock_image_generation.modify_image.assert_not_called()
    mock_firestore_service.upsert_punny_joke.assert_not_called()


class TestUpscaleJoke:
    """Tests for the upscale_joke cloud function."""

    @pytest.fixture(name="mock_services")
    def mock_services_fixture(self, monkeypatch):
        """Fixture that mocks external services using monkeypatch."""
        mock_firestore = Mock()
        mock_image_client = Mock()
        mock_cloud_storage = Mock()

        monkeypatch.setattr('functions.joke_fns.firestore', mock_firestore)
        monkeypatch.setattr('functions.joke_fns.image_client', mock_image_client)
        monkeypatch.setattr('functions.joke_fns.cloud_storage', mock_cloud_storage)

        return mock_firestore, mock_image_client, mock_cloud_storage

    def test_upscale_joke_success(self, mock_services):
        """Test that upscale_joke successfully upscales a joke's images."""
        # Arrange
        mock_firestore, mock_image_client, mock_cloud_storage = mock_services

        req = DummyReq(data={"jokeId": "joke1"})

        mock_joke = models.PunnyJoke(
            key="joke1",
            setup_text="test",
            punchline_text="test",
            setup_image_url="https://storage.googleapis.com/example/setup.png",
            punchline_image_url="https://storage.googleapis.com/example/punchline.png",
            generation_metadata=models.GenerationMetadata(),
        )
        mock_firestore.get_punny_joke.return_value = mock_joke

        mock_client_instance = MagicMock()
        mock_image_client.get_client.return_value = mock_client_instance

        mock_upscaled_setup_image = models.Image(url_upscaled="http://example.com/new_setup.png", generation_metadata=models.GenerationMetadata())
        mock_upscaled_punchline_image = models.Image(url_upscaled="http://example.com/new_punchline.png", generation_metadata=models.GenerationMetadata())
        mock_client_instance.upscale_image.side_effect = [mock_upscaled_setup_image, mock_upscaled_punchline_image]

        mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = ["gs://example/setup.png", "gs://example/punchline.png"]

        # Act
        resp = joke_fns.upscale_joke(req)

        # Assert
        mock_firestore.get_punny_joke.assert_called_once_with("joke1")
        assert mock_client_instance.upscale_image.call_count == 2
        mock_client_instance.upscale_image.assert_called_with(gcs_uri="gs://example/punchline.png", new_size=4096)
        mock_firestore.update_punny_joke.assert_called_once()

        update_data = mock_firestore.update_punny_joke.call_args[0][1]
        assert update_data['setup_image_url_upscaled'] == "http://example.com/new_setup.png"
        assert update_data['punchline_image_url_upscaled'] == "http://example.com/new_punchline.png"
        assert "generation_metadata" in update_data

        assert "data" in resp
        assert resp["data"]["joke_data"]["setup_image_url_upscaled"] == "http://example.com/new_setup.png"
        assert resp["data"]["joke_data"]["punchline_image_url_upscaled"] == "http://example.com/new_punchline.png"
