"""Tests for stats_fns bucketing logic."""
import datetime

import pytest

from functions import stats_fns


def test_bucket_jokes_viewed_ranges():
  """Ensure bucket ranges match the defined spec."""
  assert stats_fns._bucket_jokes_viewed(0) == "0"
  assert stats_fns._bucket_jokes_viewed(1) == "1-9"
  assert stats_fns._bucket_jokes_viewed(9) == "1-9"
  assert stats_fns._bucket_jokes_viewed(10) == "10-19"
  assert stats_fns._bucket_jokes_viewed(99) == "90-99"
  assert stats_fns._bucket_jokes_viewed(100) == "100-149"
  assert stats_fns._bucket_jokes_viewed(149) == "100-149"
  assert stats_fns._bucket_jokes_viewed(150) == "150-199"


def test_to_int_best_effort():
  """_to_int should gracefully handle non-numeric input."""
  assert stats_fns._to_int(5) == 5
  assert stats_fns._to_int("7") == 7
  assert stats_fns._to_int(None) == 0
  assert stats_fns._to_int("abc") == 0


def test_bucket_used_in_stats_loop(monkeypatch):
  """Verify bucketing is applied inside stats calculation."""
  # Capture writes to Firestore
  recorded = {}

  class _FakeDocRef:

    def __init__(self, doc_id):
      self.id = doc_id

    def set(self, data, merge=False):
      recorded["doc_id"] = self.id
      recorded["data"] = data
      recorded["merge"] = merge

  class _FakeCollection:

    def __init__(self):
      self._docs = []

    def where(self, filter=None):  # noqa: A002
      return self

    def stream(self):
      return self._docs

    def document(self, doc_id):
      return _FakeDocRef(doc_id)

  fake_collection = _FakeCollection()

  class _FakeFirestore:

    def collection(self, name):
      assert name in {"joke_stats", "joke_users"}
      return fake_collection

  # Patch db() to return fake
  monkeypatch.setattr(stats_fns.firestore_service, "db",
                      lambda: _FakeFirestore())

  # Build fake user docs
  class _FakeDoc:

    def __init__(self, last_login, days_used, viewed):
      self._data = {
        "last_login_at": last_login,
        "client_num_days_used": days_used,
        "client_num_viewed": viewed,
      }

    def to_dict(self):
      return self._data

  now = datetime.datetime.now(datetime.timezone.utc)
  yesterday = now - datetime.timedelta(hours=12)
  # Two users: one with 5 jokes, one with 120 jokes
  fake_collection._docs = [
    _FakeDoc(yesterday, 3, 5),
    _FakeDoc(yesterday, 3, 120),
  ]

  # Run
  stats_fns.joke_stats_calculate.__wrapped__(
    stats_fns.scheduler_fn.ScheduledEvent(
      job_name=None, schedule_time=now))

  assert recorded["doc_id"]  # YYYYMMDD string
  data = recorded["data"]
  # Buckets should be aggregated into the defined ranges
  assert data["num_1d_users_by_jokes_viewed"] == {
    "1-9": 1,
    "100-149": 1,
  }
  assert data["num_7d_users_by_jokes_viewed"] == {
    "1-9": 1,
    "100-149": 1,
  }
  # Matrix keyed by days used
  by_days = data["num_7d_users_by_days_used_by_jokes_viewed"]
  assert by_days["3"] == {
    "1-9": 1,
    "100-149": 1,
  }
  assert recorded["merge"] is True
