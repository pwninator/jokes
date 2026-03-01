"""Tests for daily joke state operations."""

from __future__ import annotations

import copy
import datetime

import pytest

from common import joke_state_operations, models


class _FakeSnapshot:

  def __init__(self, doc_id: str, data: dict[str, object] | None):
    self.id = doc_id
    self._data = copy.deepcopy(data)
    self.exists = data is not None

  def to_dict(self) -> dict[str, object]:
    return copy.deepcopy(self._data or {})


class _FakeDocumentReference:

  def __init__(self, client: "_FakeClient", collection_name: str, doc_id: str):
    self._client = client
    self._collection_name = collection_name
    self.id = doc_id
    self.path = f"{collection_name}/{doc_id}"

  def get(self, transaction=None):
    _ = transaction
    collection = self._client.data.setdefault(self._collection_name, {})
    return _FakeSnapshot(self.id, collection.get(self.id))

  def set(self, value: dict[str, object]):
    collection = self._client.data.setdefault(self._collection_name, {})
    collection[self.id] = copy.deepcopy(value)

  def update(self, value: dict[str, object]):
    collection = self._client.data.setdefault(self._collection_name, {})
    current = copy.deepcopy(collection.get(self.id) or {})
    current.update(copy.deepcopy(value))
    collection[self.id] = current


class _FakeQuery:

  def __init__(self, client: "_FakeClient", collection_name: str):
    self._client = client
    self._collection_name = collection_name
    self._start = None
    self._end = None

  def order_by(self, field):
    _ = field
    return self

  def start_at(self, values):
    self._start = values[0]
    return self

  def end_at(self, values):
    self._end = values[0]
    return self

  def stream(self):
    collection = self._client.data.setdefault(self._collection_name, {})
    for doc_id in sorted(collection.keys()):
      if self._start is not None and doc_id < self._start:
        continue
      if self._end is not None and doc_id > self._end:
        continue
      yield _FakeSnapshot(doc_id, collection[doc_id])


class _FakeCollection:

  def __init__(self, client: "_FakeClient", name: str):
    self._client = client
    self._name = name

  def document(self, doc_id: str):
    return _FakeDocumentReference(self._client, self._name, doc_id)

  def order_by(self, field):
    _ = field
    return _FakeQuery(self._client, self._name)


class _FakeBatch:

  def __init__(self):
    self.committed = False

  def set(self, ref: _FakeDocumentReference, value: dict[str, object]):
    ref.set(value)

  def update(self, ref: _FakeDocumentReference, value: dict[str, object]):
    ref.update(value)

  def commit(self):
    self.committed = True
    return True


class _FakeClient:

  def __init__(self, data: dict[str, dict[str, dict[str, object]]]):
    self.data = copy.deepcopy(data)

  def collection(self, name: str):
    return _FakeCollection(self, name)

  def batch(self):
    return _FakeBatch()


def test_get_daily_calendar_window_clamps_to_earliest_and_marks_future_days(
    monkeypatch):
  client = _FakeClient({
    "joke_schedule_batches": {
      "daily_jokes_2026_03": {
        "jokes": {
          "05": {
            "joke_id": "joke-5",
            "setup": "March fifth",
            "setup_image_url": "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/setup.png",
          },
        },
      },
    },
  })
  monkeypatch.setattr(joke_state_operations.firestore, "db", lambda: client)

  window = joke_state_operations.get_daily_calendar_window(
    start_month=datetime.date(2026, 2, 1),
    end_month=datetime.date(2026, 4, 1),
    now_utc=datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
  )

  assert window.earliest_month_id == "2026-03"
  assert window.initial_month_id == "2026-03"
  assert window.today_iso_date == "2026-03-01"
  assert [month.month_id for month in window.months] == ["2026-03", "2026-04"]
  assert "02" in window.months[0].movable_day_keys
  assert window.months[0].entries["05"].joke_id == "joke-5"
  assert "width=50" in (window.months[0].entries["05"].thumbnail_url or "")
  assert window.months[1].entries == {}


def test_move_daily_joke_updates_batches_and_joke_state(monkeypatch):
  client = _FakeClient({
    "joke_schedule_batches": {
      "daily_jokes_2026_03": {
        "jokes": {
          "05": {
            "joke_id": "joke-1",
            "setup": "setup",
            "punchline": "punch",
            "setup_image_url": "setup.png",
            "punchline_image_url": "punch.png",
          },
        },
      },
      "daily_jokes_2026_04": {
        "jokes": {},
      },
    },
    "jokes": {
      "joke-1": {
        "setup_text": "setup",
        "punchline_text": "punch",
        "setup_image_url": "setup.png",
        "punchline_image_url": "punch.png",
        "state": models.JokeState.PUBLISHED.value,
      },
    },
  })
  monkeypatch.setattr(joke_state_operations.firestore, "db", lambda: client)

  result = joke_state_operations.move_daily_joke(
    joke_id="joke-1",
    source_date=datetime.date(2026, 3, 5),
    target_date=datetime.date(2026, 4, 7),
    now_utc=datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
  )

  assert result.target_date == datetime.date(2026, 4, 7)
  assert client.data["joke_schedule_batches"]["daily_jokes_2026_03"][
    "jokes"] == {}
  assert client.data["joke_schedule_batches"]["daily_jokes_2026_04"]["jokes"][
    "07"]["joke_id"] == "joke-1"
  assert client.data["jokes"]["joke-1"][
    "state"] == models.JokeState.DAILY.value
  assert client.data["jokes"]["joke-1"]["is_public"] is False
  assert client.data["jokes"]["joke-1"][
    "public_timestamp"] == datetime.datetime(2026,
                                             4,
                                             7,
                                             tzinfo=datetime.timezone(
                                               datetime.timedelta(hours=-7)))


def test_move_daily_joke_rejects_occupied_target(monkeypatch):
  client = _FakeClient({
    "joke_schedule_batches": {
      "daily_jokes_2026_03": {
        "jokes": {
          "05": {
            "joke_id": "joke-1",
          },
        },
      },
      "daily_jokes_2026_04": {
        "jokes": {
          "07": {
            "joke_id": "joke-2",
          },
        },
      },
    },
    "jokes": {
      "joke-1": {
        "setup_text": "setup",
        "punchline_text": "punch",
        "state": models.JokeState.DAILY.value,
      },
    },
  })
  monkeypatch.setattr(joke_state_operations.firestore, "db", lambda: client)

  with pytest.raises(ValueError, match="already has a scheduled joke"):
    joke_state_operations.move_daily_joke(
      joke_id="joke-1",
      source_date=datetime.date(2026, 3, 5),
      target_date=datetime.date(2026, 4, 7),
      now_utc=datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
    )

  assert client.data["joke_schedule_batches"]["daily_jokes_2026_03"]["jokes"][
    "05"]["joke_id"] == "joke-1"


def test_move_daily_joke_rejects_today_anywhere(monkeypatch):
  client = _FakeClient({
    "joke_schedule_batches": {
      "daily_jokes_2026_03": {
        "jokes": {
          "02": {
            "joke_id": "joke-1",
          },
        },
      },
    },
    "jokes": {
      "joke-1": {
        "setup_text": "setup",
        "punchline_text": "punch",
        "state": models.JokeState.DAILY.value,
      },
    },
  })
  monkeypatch.setattr(joke_state_operations.firestore, "db", lambda: client)

  with pytest.raises(ValueError, match="cannot be moved"):
    joke_state_operations.move_daily_joke(
      joke_id="joke-1",
      source_date=datetime.date(2026, 3, 2),
      target_date=datetime.date(2026, 3, 8),
      now_utc=datetime.datetime(2026, 3, 1, 12, tzinfo=datetime.timezone.utc),
    )
