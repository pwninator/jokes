"""Tests for the firestore module."""
import datetime

import pytest
from common import models
from services import firestore


def test_upsert_punny_joke_serializes_state_string(monkeypatch):
  """Test that the upsert_punny_joke function serializes the state string correctly."""
  joke = models.PunnyJoke(setup_text="s", punchline_text="p")
  joke.state = models.JokeState.DRAFT
  joke.key = None

  captured = {}

  class DummyDoc:
    """Dummy document class for testing."""

    def __init__(self):
      self._exists = False

    def get(self):
      """Dummy document class for testing."""

      class R:
        """Dummy result class for testing."""

        def __init__(self):
          self.exists = False

      return R()

    def set(self, data):
      """Dummy document class for testing."""
      captured.update(data)

  class DummyCol:
    """Dummy collection class for testing."""

    def document(self, _id):
      """Dummy document class for testing."""
      return DummyDoc()

  class DummyDB:
    """Dummy database class for testing."""

    def collection(self, _name):
      """Dummy collection class for testing."""
      return DummyCol()

  monkeypatch.setattr(firestore, "db", DummyDB)
  # Avoid server timestamp usage complexity by monkeypatching constants
  monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", "TS")

  res = firestore.upsert_punny_joke(joke)
  assert res is not None
  assert captured["state"] == "DRAFT"
  assert "key" not in captured


import pytest


def test_get_all_jokes(monkeypatch):
  """Test that get_all_jokes returns a list of PunnyJoke objects."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, id_, exists=True, data=None):
      self.id = id_
      self._exists = exists
      self._data = data or {"setup_text": "s", "punchline_text": "p"}

    @property
    def exists(self):
      return self._exists

    def to_dict(self):
      return self._data

  class DummyQuery:

    def stream(self):
      return [
        DummyDoc("joke1",
                 data={
                   "setup_text": "Why did the scarecrow win an award?",
                   "punchline_text": "Because he was outstanding in his field."
                 }),
        DummyDoc("joke2",
                 data={
                   "setup_text": "What do you call a fake noodle?",
                   "punchline_text": "An Impasta."
                 }),
      ]

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = fs.get_all_jokes()
  assert len(jokes) == 2
  assert jokes[0].key == "joke1"
  assert jokes[0].setup_text == "Why did the scarecrow win an award?"
  assert jokes[1].key == "joke2"
  assert jokes[1].punchline_text == "An Impasta."


@pytest.mark.asyncio
async def test_get_all_jokes_async(monkeypatch):
  """Test that get_all_jokes_async returns a list of PunnyJoke objects."""
  from services import firestore as fs

  class AsyncIterator:

    def __init__(self, seq):
      self.iter = iter(seq)

    def __aiter__(self):
      return self

    async def __anext__(self):
      try:
        return next(self.iter)
      except StopIteration:
        raise StopAsyncIteration

  class DummyDoc:

    def __init__(self, id_, exists=True, data=None):
      self.id = id_
      self._exists = exists
      self._data = data or {"setup_text": "s", "punchline_text": "p"}

    @property
    def exists(self):
      return self._exists

    def to_dict(self):
      return self._data

  class DummyQuery:

    def stream(self):
      return AsyncIterator([
        DummyDoc("joke1",
                 data={
                   "setup_text": "Why did the scarecrow win an award?",
                   "punchline_text": "Because he was outstanding in his field."
                 }),
        DummyDoc("joke2",
                 data={
                   "setup_text": "What do you call a fake noodle?",
                   "punchline_text": "An Impasta."
                 }),
      ])

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "get_async_db", DummyDB)

  jokes = await fs.get_all_jokes_async()
  assert len(jokes) == 2
  assert jokes[0].key == "joke1"
  assert jokes[0].setup_text == "Why did the scarecrow win an award?"
  assert jokes[1].key == "joke2"
  assert jokes[1].punchline_text == "An Impasta."


def test_get_punny_jokes_batch(monkeypatch):
  """get_punny_jokes returns a list of PunnyJoke for given IDs."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, id_, exists=True, data=None):
      self.id = id_
      self._exists = exists
      self._data = data or {"setup_text": "s", "punchline_text": "p"}

    @property
    def exists(self):
      return self._exists

    def to_dict(self):
      return self._data

  class DummyRef:

    def __init__(self, id_):
      self.id = id_

  class DummyCol:

    def document(self, id_):
      return DummyRef(id_)

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

    def get_all(self, refs):
      return [DummyDoc(ref.id) for ref in refs]

  monkeypatch.setattr(fs, "db", DummyDB)

  joke_ids = ["j1", "j2", "j3"]
  jokes = fs.get_punny_jokes(joke_ids)
  assert len(jokes) == 3
  assert all(j.key in joke_ids for j in jokes)


def test_upsert_joke_user_usage_insert(monkeypatch):
  """Inserts a new joke user doc with count=1 and timestamps."""
  from services import firestore as fs

  captured = {}

  class DummyDoc:

    def __init__(self):
      self._exists = False

    def get(self, transaction=None):  # pylint: disable=unused-argument

      class R:

        def __init__(self):
          self.exists = False

      return R()

  class DummyCol:

    def document(self, _id):  # pylint: disable=unused-argument
      return DummyDoc()

  class DummyTxn:
    _read_only = False

    def set(self, doc_ref, data):  # pylint: disable=unused-argument
      captured.update(data)

  class DummyDB:

    def collection(self, _name):  # pylint: disable=unused-argument
      return DummyCol()

    def transaction(self):
      return DummyTxn()

  monkeypatch.setattr(fs, "db", DummyDB)
  # Avoid server timestamp complexity
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  # Call the undecorated logic directly with our dummy txn
  count = fs._upsert_joke_user_usage_logic(DummyTxn(), "user1")  # pylint: disable=protected-access
  assert count == 1
  assert captured["created_at"] == "TS"
  assert captured["last_login_at"] == "TS"
  assert captured["num_distinct_day_used"] == 1


def test_upsert_joke_user_usage_no_increment_same_day(monkeypatch):
  """Does not increment when last_login_at and now fall in same day bucket."""
  from services import firestore as fs

  class DummySnap:

    def __init__(self, data):
      self._data = data
      self.exists = True

    def to_dict(self):
      return self._data

  class DummyDoc:

    def __init__(self, snap):
      self._snap = snap

    def get(self, transaction=None):  # pylint: disable=unused-argument
      return self._snap

  class DummyCol:

    def __init__(self, snap):
      self._snap = snap

    def document(self, _id):  # pylint: disable=unused-argument
      return DummyDoc(self._snap)

  updates = {}

  class DummyTxn:
    _read_only = False

    def update(self, doc_ref, data):  # pylint: disable=unused-argument
      updates.update(data)

  class DummyDB:

    def __init__(self, snap):
      self._snap = snap

    def collection(self, _name):  # pylint: disable=unused-argument
      return DummyCol(self._snap)

    def transaction(self):
      return DummyTxn()

  created = datetime.datetime(2024, 1, 1, 0, 0, 0)
  # same day bucket: last_login_at = created + 2 hours; now = created + 5 hours
  last_login_at = created + datetime.timedelta(hours=2)
  now = created + datetime.timedelta(hours=5)
  snap_data = {
    'created_at': created,
    'last_login_at': last_login_at,
    'num_distinct_day_used': 5,
  }

  monkeypatch.setattr(fs, "db", lambda: DummyDB(DummySnap(snap_data)))
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  count = fs._upsert_joke_user_usage_logic(DummyTxn(), "user1", now_utc=now)  # pylint: disable=protected-access
  assert count == 5
  assert updates["num_distinct_day_used"] == 5
  assert updates["last_login_at"] == "TS"


def test_upsert_joke_user_usage_increment_new_day(monkeypatch):
  """Increments by 1 when now falls into a new whole-day bucket."""
  from services import firestore as fs

  class DummySnap:

    def __init__(self, data):
      self._data = data
      self.exists = True

    def to_dict(self):
      return self._data

  class DummyDoc:

    def __init__(self, snap):
      self._snap = snap

    def get(self, transaction=None):  # pylint: disable=unused-argument
      return self._snap

  class DummyCol:

    def __init__(self, snap):
      self._snap = snap

    def document(self, _id):  # pylint: disable=unused-argument
      return DummyDoc(self._snap)

  updates = {}

  class DummyTxn:
    _read_only = False

    def update(self, doc_ref, data):  # pylint: disable=unused-argument
      updates.update(data)

  class DummyDB:

    def __init__(self, snap):
      self._snap = snap

    def collection(self, _name):  # pylint: disable=unused-argument
      return DummyCol(self._snap)

    def transaction(self):
      return DummyTxn()

  created = datetime.datetime(2024, 1, 1, 0, 0, 0)
  last_login_at = created + datetime.timedelta(days=1, hours=1)
  now = created + datetime.timedelta(days=2, hours=2)
  snap_data = {
    'created_at': created,
    'last_login_at': last_login_at,
    'num_distinct_day_used': 7,
  }

  monkeypatch.setattr(fs, "db", lambda: DummyDB(DummySnap(snap_data)))
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  count = fs._upsert_joke_user_usage_logic(DummyTxn(), "user1", now_utc=now)  # pylint: disable=protected-access
  assert count == 8
  assert updates["num_distinct_day_used"] == 8
  assert updates["last_login_at"] == "TS"
