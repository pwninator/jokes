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
      self._operations_doc = self._DummyOperationsDoc()

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

    class _DummyOperationsDoc:

      def __init__(self):
        self.exists = False

      class _Snapshot:

        def __init__(self, exists):
          self.exists = exists

        def to_dict(self):
          return {}

      def get(self):
        return self._Snapshot(self.exists)

      def set(self, *_args, **_kwargs):
        self.exists = True

    def collection(self, name):
      assert name == 'metadata'

      class DummyMetadataCol:

        def __init__(self, operations_doc):
          self._operations_doc = operations_doc

        def document(self, doc_name):
          assert doc_name == 'operations'
          return self._operations_doc

      return DummyMetadataCol(self._operations_doc)

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


def test_upsert_punny_joke_logs_operation(monkeypatch):
  """upsert_punny_joke should append operation log entries."""
  joke = models.PunnyJoke(
    setup_text="s",
    punchline_text="p",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
  )
  joke.key = None

  captured_main = {}
  captured_operations: list[tuple[dict, bool]] = []

  class DummyOperationsDoc:
    """Dummy operations document for capturing writes."""

    def __init__(self):
      self._data: dict | None = None
      self.exists = False

    class _Snapshot:

      def __init__(self, exists, data):
        self.exists = exists
        self._data = data

      def to_dict(self):
        return self._data

    def get(self):
      return self._Snapshot(self.exists, self._data)

    def set(self, data, merge=False):
      captured_operations.append((data, merge))
      self._data = data
      self.exists = True

  class DummyDoc:
    """Dummy joke document."""

    def __init__(self):
      self._exists = False
      self._operations_doc = DummyOperationsDoc()

    def get(self):

      class Snapshot:

        def __init__(self, exists):
          self.exists = exists

      return Snapshot(self._exists)

    def set(self, data):
      captured_main.update(data)
      self._exists = True

    def collection(self, name):
      assert name == 'metadata'

      class DummyMetadataCol:

        def __init__(self, operations_doc):
          self._operations_doc = operations_doc

        def document(self, doc_name):
          assert doc_name == 'operations'
          return self._operations_doc

      return DummyMetadataCol(self._operations_doc)

  dummy_doc = DummyDoc()

  class DummyCol:

    def document(self, _id):
      return dummy_doc

  class DummyDB:

    def collection(self, name):
      assert name == 'jokes'
      return DummyCol()

  monkeypatch.setattr(firestore, "db", DummyDB)
  monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", "TS")
  monkeypatch.setattr(firestore.utils, "create_firestore_key",
                      lambda *args, **kwargs: "joke-key")

  res = firestore.upsert_punny_joke(joke, operation="CREATE")

  assert res is not None
  assert captured_main["creation_time"] == "TS"
  assert captured_main["last_modification_time"] == "TS"
  assert captured_operations[0][1] is True
  assert "log" in captured_operations[0][0]
  log_entry = captured_operations[0][0]["log"][0]
  assert log_entry[firestore.OPERATION] == "CREATE"
  assert isinstance(log_entry[firestore.OPERATION_TIMESTAMP],
                    datetime.datetime)
  assert str(
    log_entry[firestore.OPERATION_TIMESTAMP].tzinfo) == "America/Los_Angeles"
  assert log_entry["setup_text"] == "s"
  assert log_entry["punchline_text"] == "p"
  assert log_entry["setup_scene_idea"] == "scene setup"
  assert log_entry["punchline_scene_idea"] == "scene punch"


def test_get_joke_by_state_orders_and_paginates(monkeypatch):
  """get_joke_by_state orders by creation_time desc and paginates by cursor."""
  captured: dict = {}

  class _Snapshot:

    def __init__(self, exists: bool = True):
      self.exists = exists

  class _Doc:

    def __init__(self, doc_id: str, data: dict | None, exists: bool = True):
      self.id = doc_id
      self.exists = exists
      self._data = data

    def to_dict(self):
      return self._data

  class _Query:

    def __init__(self, docs):
      self._docs = docs

    def order_by(self, field: str, direction=None):
      captured["order_by"] = (field, direction)
      return self

    def start_after(self, snapshot):
      captured["start_after_called"] = True
      captured["start_after_snapshot"] = snapshot
      return self

    def limit(self, n: int):
      captured["limit"] = n
      return self

    def stream(self):
      return self._docs

  class _DocRef:

    def __init__(self, snapshot: _Snapshot):
      self._snapshot = snapshot

    def get(self):
      return self._snapshot

  class _Collection:

    def document(self, _doc_id: str):
      return _DocRef(_Snapshot(exists=True))

  class _DB:

    def collection(self, name: str):
      assert name == "jokes"
      return _Collection()

  def _prepare(states, *, category_id: str | None = None, async_mode: bool):
    assert async_mode is False
    captured["states"] = states
    captured["category_id"] = category_id
    return _Query([
      _Doc("joke3", {
        "setup_text": "s3",
        "punchline_text": "p3",
        "state": "DRAFT",
      }),
      _Doc("joke2", {
        "setup_text": "s2",
        "punchline_text": "p2",
        "state": "DRAFT",
      }),
      _Doc("joke1", {
        "setup_text": "s1",
        "punchline_text": "p1",
        "state": "DRAFT",
      }),
    ])

  monkeypatch.setattr(firestore, "_prepare_jokes_query", _prepare)
  monkeypatch.setattr(firestore, "db", lambda: _DB())

  entries, next_cursor = firestore.get_joke_by_state(
    states=[models.JokeState.DRAFT],
    cursor="joke99",
    limit=2,
    category_id="cats",
  )

  assert captured["states"] == [models.JokeState.DRAFT]
  assert captured["category_id"] == "cats"
  assert captured["order_by"][0] == "creation_time"
  assert captured["order_by"][1] == firestore.Query.DESCENDING
  assert captured.get("start_after_called") is True
  assert captured["limit"] == 3  # limit + 1

  assert [j.key for j, _ in entries] == ["joke3", "joke2"]
  assert [cursor for _, cursor in entries] == ["joke3", "joke2"]
  assert next_cursor == "joke2"


def test_update_punny_joke_sets_is_public_when_published(monkeypatch):
  captured = {}

  class DummyDoc:

    def __init__(self):
      self._data = {"setup_text": "s", "punchline_text": "p"}

    def get(self):

      class Snapshot:

        def __init__(self, data):
          self.exists = True
          self._data = data

        def to_dict(self):
          return self._data

      return Snapshot(dict(self._data))

    def update(self, data):
      captured.update(data)
      self._data.update(data)

  class DummyCol:

    def document(self, _id):
      return DummyDoc()

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(firestore, "db", DummyDB)
  monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", "TS")

  diff = firestore.update_punny_joke(
    "joke1",
    {"state": models.JokeState.PUBLISHED.value},
  )

  assert captured["state"] == "PUBLISHED"
  assert captured["is_public"] is True
  assert captured["last_modification_time"] == "TS"
  assert diff == {
    "state": "PUBLISHED",
    "is_public": True,
  }


def test_update_punny_joke_sets_is_public_false_for_non_public(monkeypatch):
  captured = {}

  class DummyDoc:

    def __init__(self):
      self._data = {"setup_text": "s", "punchline_text": "p"}

    def get(self):

      class Snapshot:

        def __init__(self, data):
          self.exists = True
          self._data = data

        def to_dict(self):
          return self._data

      return Snapshot(dict(self._data))

    def update(self, data):
      captured.update(data)
      self._data.update(data)

  class DummyCol:

    def document(self, _id):
      return DummyDoc()

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(firestore, "db", DummyDB)
  monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", "TS")

  diff = firestore.update_punny_joke(
    "joke1",
    {
      "state": models.JokeState.DAILY,
      "is_public": True,
    },
  )

  assert captured["state"] == "DAILY"
  assert captured["is_public"] is False
  assert captured["last_modification_time"] == "TS"
  assert diff == {
    "state": "DAILY",
    "is_public": False,
  }


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


def test_upsert_joke_sheet_returns_existing_doc_id(monkeypatch):
  from common import models
  from services import firestore as fs

  captured: dict[str, object] = {}

  class DummyDocRef:

    def set(self, data, merge: bool = False):
      captured["data"] = data
      captured["merge"] = merge

  class DummyDoc:

    def __init__(self, doc_id: str):
      self.id = doc_id
      self.exists = True
      self.reference = DummyDocRef()

    def to_dict(self):
      # Simulate older doc missing joke_ids so upsert backfills.
      return {"joke_str": "a,b"}

  class DummyQuery:

    def limit(self, _n: int):
      return self

    def get(self):
      return [DummyDoc("existing-id")]

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

    def add(self, _data):
      raise AssertionError("Should not create when existing doc found")

  class DummyDB:

    def collection(self, name: str):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  sheet = models.JokeSheet(joke_ids=["a", "b"])
  saved = fs.upsert_joke_sheet(sheet)
  assert saved.key == "existing-id"
  assert saved.joke_str == "a,b"
  assert saved.joke_ids == ["a", "b"]
  assert captured["merge"] is True
  assert captured["data"] == {
    "joke_str": "a,b",
    "joke_ids": ["a", "b"],
    "category_id": None,
    "index": None,
    "image_gcs_uri": None,
    "pdf_gcs_uri": None,
    "avg_saved_users_fraction": 0.0,
  }


def test_upsert_joke_sheet_creates_when_missing(monkeypatch):
  from common import models
  from services import firestore as fs

  captured: dict[str, object] = {}

  class DummyQuery:

    def limit(self, _n: int):
      return self

    def get(self):
      return []

  class DummyDocRef:

    def __init__(self, doc_id: str):
      self.id = doc_id

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

    def add(self, data):
      captured["data"] = data
      return None, DummyDocRef("created-id")

  class DummyDB:

    def collection(self, name: str):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  sheet = models.JokeSheet(joke_ids=["a", "b"])
  saved = fs.upsert_joke_sheet(sheet)
  assert saved.key == "created-id"
  assert saved.joke_str == "a,b"
  assert saved.joke_ids == ["a", "b"]
  assert captured["data"] == {
    "joke_str": "a,b",
    "joke_ids": ["a", "b"],
    "category_id": None,
    "index": None,
    "image_gcs_uri": None,
    "pdf_gcs_uri": None,
    "avg_saved_users_fraction": 0.0,
  }


def test_upsert_joke_sheet_skips_when_unchanged(monkeypatch):
  from common import models
  from services import firestore as fs

  captured = {"set_called": False}

  class DummyDocRef:

    def set(self, data, merge: bool = False):
      captured["set_called"] = True

  class DummyDoc:

    def __init__(self, doc_id: str):
      self.id = doc_id
      self.reference = DummyDocRef()

    @property
    def exists(self):
      return True

    def to_dict(self):
      return {
        "joke_str": "a,b",
        "joke_ids": ["a", "b"],
        "category_id": None,
        "index": None,
        "image_gcs_uri": None,
        "pdf_gcs_uri": None,
        "avg_saved_users_fraction": 0.0,
      }

  class DummyQuery:

    def limit(self, _n: int):
      return self

    def get(self):
      return [DummyDoc("existing-id")]

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

    def add(self, _data):
      raise AssertionError("Should not create when existing doc found")

  class DummyDB:

    def collection(self, name: str):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  sheet = models.JokeSheet(joke_ids=["a", "b"])
  saved = fs.upsert_joke_sheet(sheet)
  assert saved.key == "existing-id"
  assert saved.joke_str == "a,b"
  assert saved.joke_ids == ["a", "b"]
  assert captured["set_called"] is False


def test_upsert_joke_sheet_writes_category_id(monkeypatch):
  from common import models
  from services import firestore as fs

  captured: dict[str, object] = {}

  class DummyDocRef:

    def set(self, data, merge=False):  # pylint: disable=unused-argument
      captured["data"] = data
      captured["merge"] = merge

  class DummyDoc:

    def __init__(self, doc_id: str):
      self.id = doc_id
      self.reference = DummyDocRef()

    @property
    def exists(self):
      return True

    def to_dict(self):
      # Missing category_id so upsert should backfill.
      return {"joke_str": "a,b", "joke_ids": ["a", "b"]}

  class DummyQuery:

    def limit(self, _n: int):
      return self

    def get(self):
      return [DummyDoc("existing-id")]

  class DummyCol:

    def where(self, filter=None):  # pylint: disable=unused-argument
      return DummyQuery()

    def add(self, _data):
      raise AssertionError("Should not create when existing doc found")

  class DummyDB:

    def collection(self, name: str):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  sheet = models.JokeSheet(
    joke_ids=["a", "b"],
    category_id="cats",
    image_gcs_uri="gs://tmp/joke_notes_sheets/abc.png",
    pdf_gcs_uri="gs://tmp/joke_notes_sheets/abc.pdf",
  )
  saved = fs.upsert_joke_sheet(sheet)
  assert saved.key == "existing-id"
  assert saved.joke_str == "a,b"
  assert saved.joke_ids == ["a", "b"]
  assert saved.category_id == "cats"
  assert saved.image_gcs_uri == "gs://tmp/joke_notes_sheets/abc.png"
  assert saved.pdf_gcs_uri == "gs://tmp/joke_notes_sheets/abc.pdf"
  assert captured["merge"] is True
  assert captured["data"] == {
    "joke_str": "a,b",
    "joke_ids": ["a", "b"],
    "category_id": "cats",
    "index": None,
    "image_gcs_uri": "gs://tmp/joke_notes_sheets/abc.png",
    "pdf_gcs_uri": "gs://tmp/joke_notes_sheets/abc.pdf",
    "avg_saved_users_fraction": 0.0,
  }


def test_get_joke_sheets_by_category_filters_index(monkeypatch):
  from services import firestore as fs

  captured_filters: list = []

  class DummyQuery:

    def __init__(self, filters):
      self._filters = filters

    def where(self, filter):  # pylint: disable=redefined-builtin
      self._filters.append(filter)
      return self

    def stream(self):
      return []

  class DummyCol:

    def __init__(self, filters):
      self._filters = filters

    def where(self, filter):  # pylint: disable=redefined-builtin
      self._filters.append(filter)
      return DummyQuery(self._filters)

  class DummyDB:

    def __init__(self, filters):
      self._filters = filters

    def collection(self, name):
      assert name == "joke_sheets"
      return DummyCol(self._filters)

  monkeypatch.setattr(fs, "db", lambda: DummyDB(captured_filters))

  results = fs.get_joke_sheets_by_category("animals", index=2)

  assert results == []
  assert len(captured_filters) == 2
  assert getattr(captured_filters[0], "field_path", None) == "category_id"
  assert getattr(captured_filters[0], "op_string", None) == "=="
  assert getattr(captured_filters[0], "value", None) == "animals"
  assert getattr(captured_filters[1], "field_path", None) == "index"
  assert getattr(captured_filters[1], "op_string", None) == "=="
  assert getattr(captured_filters[1], "value", None) == 2


def test_update_joke_sheets_cache_writes_payload(monkeypatch):
  from services import firestore as fs

  captured: dict[str, object] = {}

  class DummyDoc:

    def set(self, data, merge: bool = False):
      captured["data"] = data
      captured["merge"] = merge

  class DummyCol:

    def document(self, doc_id):
      assert doc_id == "joke_sheets"
      return DummyDoc()

  class DummyDB:

    def collection(self, name):
      assert name == "joke_cache"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  categories = [
    models.JokeCategory(id="cats", display_name="Cats", state="APPROVED"),
    models.JokeCategory(id="dogs", display_name="Dogs", state="SEASONAL"),
  ]
  sheets = [
    models.JokeSheet(
      key="sheet-2",
      category_id="cats",
      index=1,
      image_gcs_uri="gs://img2",
      pdf_gcs_uri="gs://pdf2",
    ),
    models.JokeSheet(
      key="sheet-1",
      category_id="cats",
      index=0,
      image_gcs_uri="gs://img1",
      pdf_gcs_uri="gs://pdf1",
    ),
    models.JokeSheet(
      key="missing-pdf",
      category_id="cats",
      index=2,
      image_gcs_uri="gs://img3",
      pdf_gcs_uri=None,
    ),
    models.JokeSheet(
      key="missing-index",
      category_id="cats",
      index=None,
      image_gcs_uri="gs://img4",
      pdf_gcs_uri="gs://pdf4",
    ),
    models.JokeSheet(
      key="other-category",
      category_id="other",
      index=0,
      image_gcs_uri="gs://img5",
      pdf_gcs_uri="gs://pdf5",
    ),
  ]

  fs.update_joke_sheets_cache(categories, sheets)

  assert captured["merge"] is False
  payload = captured["data"]
  assert payload["refresh_timestamp"] == "TS"
  categories_payload = payload["categories"]
  assert set(categories_payload.keys()) == {"cats"}
  assert categories_payload["cats"]["category_display_name"] == "Cats"
  cat_sheets = categories_payload["cats"]["sheets"]
  assert [s["sheet_key"] for s in cat_sheets] == ["sheet-1", "sheet-2"]
  assert cat_sheets[0]["image_gcs_uri"] == "gs://img1"
  assert cat_sheets[0]["pdf_gcs_uri"] == "gs://pdf1"
  assert cat_sheets[1]["image_gcs_uri"] == "gs://img2"
  assert cat_sheets[1]["pdf_gcs_uri"] == "gs://pdf2"


def test_get_joke_sheets_cache_returns_doc(monkeypatch):
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, exists, data):
      self.exists = exists
      self._data = data

    def to_dict(self):
      return self._data

  class DummyCol:

    def document(self, doc_id):
      assert doc_id == "joke_sheets"
      return self

    def get(self):
      return DummyDoc(
        True, {
          "categories": {
            "cats": {
              "category_display_name":
              "Cats",
              "sheets": [
                {
                  "image_gcs_uri": "gs://img1",
                  "pdf_gcs_uri": "gs://pdf1",
                  "sheet_key": "sheet-1",
                },
                {
                  "image_gcs_uri": None,
                  "pdf_gcs_uri": "gs://pdf2",
                  "sheet_key": "sheet-2",
                },
              ],
            },
          }
        })

  class DummyDB:

    def collection(self, name):
      assert name == "joke_cache"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  result = fs.get_joke_sheets_cache()
  assert len(result) == 1
  category, sheets = result[0]
  assert category.id == "cats"
  assert category.display_name == "Cats"
  assert len(sheets) == 1
  assert sheets[0].key == "sheet-1"
  assert sheets[0].index == 0
  assert sheets[0].image_gcs_uri == "gs://img1"
  assert sheets[0].pdf_gcs_uri == "gs://pdf1"


def test_delete_joke_sheet_deletes_when_exists(monkeypatch):
  from services import firestore as fs

  captured = {"deleted": False}

  class DummyDocRef:

    def get(self):

      class Snapshot:
        exists = True

      return Snapshot()

    def delete(self):
      captured["deleted"] = True

  class DummyCol:

    def document(self, _id):
      return DummyDocRef()

  class DummyDB:

    def collection(self, name):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  result = fs.delete_joke_sheet("sheet-1")
  assert result is True
  assert captured["deleted"] is True


def test_delete_joke_sheet_returns_false_when_missing(monkeypatch):
  from services import firestore as fs

  captured = {"deleted": False}

  class DummyDocRef:

    def get(self):

      class Snapshot:
        exists = False

      return Snapshot()

    def delete(self):
      captured["deleted"] = True

  class DummyCol:

    def document(self, _id):
      return DummyDocRef()

  class DummyDB:

    def collection(self, name):
      assert name == "joke_sheets"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  result = fs.delete_joke_sheet("sheet-1")
  assert result is False
  assert captured["deleted"] is False


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
  count = fs._upsert_joke_user_usage_logic(  # pylint: disable=protected-access
    DummyTxn(),
    "user1",
    feed_cursor="cursor123",
    local_feed_count=10,
  )
  assert count == 1
  assert captured["created_at"] == "TS"
  assert captured["last_login_at"] == "TS"
  assert captured["num_distinct_day_used"] == 1
  assert captured["feed_cursor"] == "cursor123"
  assert captured["local_feed_count"] == 10


def test_upsert_joke_user_usage_includes_client_navigated(monkeypatch):
  """Records client_num_navigated when provided."""
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
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  fs._upsert_joke_user_usage_logic(  # pylint: disable=protected-access
    DummyTxn(),
    "user1",
    client_num_navigated=42,
  )

  assert captured["client_num_navigated"] == 42


def test_upsert_joke_user_usage_includes_client_thumbs(monkeypatch):
  """Records client thumb counts when provided."""
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
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  fs._upsert_joke_user_usage_logic(  # pylint: disable=protected-access
    DummyTxn(),
    "user1",
    client_num_thumbs_up=5,
    client_num_thumbs_down=7,
  )

  assert captured["client_num_thumbs_up"] == 5
  assert captured["client_num_thumbs_down"] == 7


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


def test_upsert_joke_user_usage_with_requested_review(monkeypatch):
  """Test that requested_review is passed through and stored."""
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
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  # Test with requested_review = True
  fs._upsert_joke_user_usage_logic(DummyTxn(), "user1", requested_review=True)  # pylint: disable=protected-access
  assert captured["requested_review"] is True

  # Test with requested_review = False
  fs._upsert_joke_user_usage_logic(DummyTxn(), "user1", requested_review=False)  # pylint: disable=protected-access
  assert captured["requested_review"] is False


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


def test_update_joke_feed_single_chunk(monkeypatch):
  """Test that update_joke_feed creates a single document when jokes fit in one chunk."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = [{"id": f"joke{i}", "text": f"joke {i}"} for i in range(30)]
  fs.update_joke_feed(jokes)

  assert len(captured_docs) == 1
  assert "0000000000" in captured_docs
  assert captured_docs["0000000000"]["jokes"] == jokes
  assert len(captured_docs["0000000000"]["jokes"]) == 30


def test_update_joke_feed_multiple_chunks(monkeypatch):
  """Test that update_joke_feed creates multiple documents when jokes exceed chunk size."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = [{"id": f"joke{i}", "text": f"joke {i}"} for i in range(120)]
  fs.update_joke_feed(jokes)

  assert len(captured_docs) == 3  # 120 jokes / 50 = 3 chunks
  assert "0000000000" in captured_docs
  assert "0000000001" in captured_docs
  assert "0000000002" in captured_docs

  # First chunk: jokes 0-49
  assert len(captured_docs["0000000000"]["jokes"]) == 50
  assert captured_docs["0000000000"]["jokes"][0]["id"] == "joke0"
  assert captured_docs["0000000000"]["jokes"][49]["id"] == "joke49"

  # Second chunk: jokes 50-99
  assert len(captured_docs["0000000001"]["jokes"]) == 50
  assert captured_docs["0000000001"]["jokes"][0]["id"] == "joke50"
  assert captured_docs["0000000001"]["jokes"][49]["id"] == "joke99"

  # Third chunk: jokes 100-119
  assert len(captured_docs["0000000002"]["jokes"]) == 20
  assert captured_docs["0000000002"]["jokes"][0]["id"] == "joke100"
  assert captured_docs["0000000002"]["jokes"][19]["id"] == "joke119"


def test_update_joke_feed_exactly_one_chunk(monkeypatch):
  """Test that update_joke_feed handles exactly 50 jokes (one chunk)."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = [{"id": f"joke{i}", "text": f"joke {i}"} for i in range(50)]
  fs.update_joke_feed(jokes)

  assert len(captured_docs) == 1
  assert "0000000000" in captured_docs
  assert len(captured_docs["0000000000"]["jokes"]) == 50
  assert captured_docs["0000000000"]["jokes"] == jokes


def test_update_joke_feed_exactly_two_chunks(monkeypatch):
  """Test that update_joke_feed handles exactly 100 jokes (two chunks)."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = [{"id": f"joke{i}", "text": f"joke {i}"} for i in range(100)]
  fs.update_joke_feed(jokes)

  assert len(captured_docs) == 2
  assert "0000000000" in captured_docs
  assert "0000000001" in captured_docs
  assert len(captured_docs["0000000000"]["jokes"]) == 50
  assert len(captured_docs["0000000001"]["jokes"]) == 50


def test_update_joke_feed_empty_list(monkeypatch):
  """Test that update_joke_feed handles empty joke list."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = []
  fs.update_joke_feed(jokes)

  # Should create no documents for empty list
  assert len(captured_docs) == 0


def test_update_joke_feed_one_over_chunk(monkeypatch):
  """Test that update_joke_feed handles exactly 51 jokes (two chunks)."""
  from services import firestore as fs

  captured_docs = {}

  class DummyDoc:

    def __init__(self, doc_id):
      self._doc_id = doc_id

    def set(self, data):
      captured_docs[self._doc_id] = data

  class DummyCol:

    def document(self, doc_id):
      return DummyDoc(doc_id)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes = [{"id": f"joke{i}", "text": f"joke {i}"} for i in range(51)]
  fs.update_joke_feed(jokes)

  assert len(captured_docs) == 2
  assert "0000000000" in captured_docs
  assert "0000000001" in captured_docs
  assert len(captured_docs["0000000000"]["jokes"]) == 50
  assert len(captured_docs["0000000001"]["jokes"]) == 1
  assert captured_docs["0000000001"]["jokes"][0]["id"] == "joke50"


def test_get_top_jokes(monkeypatch):
  """Test that get_top_jokes returns a list of PunnyJoke objects, filtered, sorted, and limited."""
  from google.cloud.firestore import Query
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

    def __init__(self, docs):
      self._docs = docs
      self._filters = []
      self._order_by = None
      self._limit = None

    def where(self, filter):
      self._filters.append(filter)
      return self

    def order_by(self, field, direction=Query.ASCENDING):
      self._order_by = (field, direction)
      return self

    def limit(self, limit):
      self._limit = limit
      return self

    def stream(self):
      # Simulate filtering
      filtered_docs = [
        doc for doc in self._docs
        if all((f.field_path == 'is_public'
                and doc.to_dict().get('is_public') == f.value)
               for f in self._filters)
      ]
      # Simulate sorting
      if self._order_by:
        field, direction = self._order_by
        filtered_docs.sort(key=lambda doc: doc.to_dict().get(field, 0),
                           reverse=(direction == Query.DESCENDING))

      # Simulate limiting
      if self._limit is not None:
        filtered_docs = filtered_docs[:self._limit]

      return filtered_docs

  class DummyCol:

    def __init__(self, docs):
      self._docs = docs

    def where(self, filter):
      return DummyQuery(self._docs).where(filter)

    def document(self, _id):
      # Not used in get_top_jokes, but needed for other tests
      pass

  class DummyDB:

    def __init__(self, docs):
      self._docs = docs

    def collection(self, _name):
      return DummyCol(self._docs)

  # Prepare dummy data
  joke1 = DummyDoc("joke1",
                   data={
                     "setup_text": "s1",
                     "punchline_text": "p1",
                     "is_public": True,
                     "popularity_score_recent": 100
                   })
  joke2 = DummyDoc("joke2",
                   data={
                     "setup_text": "s2",
                     "punchline_text": "p2",
                     "is_public": True,
                     "popularity_score_recent": 200
                   })
  joke3 = DummyDoc("joke3",
                   data={
                     "setup_text": "s3",
                     "punchline_text": "p3",
                     "is_public": False,
                     "popularity_score_recent": 300
                   })  # Not public
  joke4 = DummyDoc("joke4",
                   data={
                     "setup_text": "s4",
                     "punchline_text": "p4",
                     "is_public": True,
                     "popularity_score_recent": 150
                   })

  all_jokes = [joke1, joke2, joke3, joke4]

  monkeypatch.setattr(fs, "db", lambda: DummyDB(all_jokes))

  # Test case 1: Get top 2 public jokes by popularity
  top_jokes = fs.get_top_jokes('popularity_score_recent', 2)
  assert len(top_jokes) == 2
  assert top_jokes[0].key == "joke2"  # popularity 200
  assert top_jokes[1].key == "joke4"  # popularity 150

  # Test case 2: Get top 1 public joke
  top_jokes = fs.get_top_jokes('popularity_score_recent', 1)
  assert len(top_jokes) == 1
  assert top_jokes[0].key == "joke2"

  # Test case 3: No public jokes
  monkeypatch.setattr(fs, "db",
                      lambda: DummyDB([joke3]))  # Only non-public joke
  top_jokes = fs.get_top_jokes('popularity_score_recent', 5)
  assert len(top_jokes) == 0

  # Test case 4: Empty collection
  monkeypatch.setattr(fs, "db", lambda: DummyDB([]))
  top_jokes = fs.get_top_jokes('popularity_score_recent', 5)
  assert len(top_jokes) == 0


def test_get_joke_feed_page_no_cursor(monkeypatch):
  """Test get_joke_feed_page with no cursor returns first page."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, doc_id, jokes_data):
      self.id = doc_id
      self._jokes = jokes_data

    def exists(self):
      return True

    def to_dict(self):
      return {"jokes": self._jokes}

  class DummyQuery:

    def __init__(self, docs):
      self._docs = docs
      self._cursor = None
      self._limit = None

    def order_by(self, field_path):
      return self

    def start_after(self, cursor):
      self._cursor = cursor
      return self

    def limit(self, n):
      self._limit = n
      return self

    def stream(self):
      return iter(self._docs)

  class DummyCol:

    def __init__(self, docs_by_id):
      self._docs_by_id = docs_by_id
      self._all_docs = []
      for doc_id, jokes in docs_by_id.items():
        self._all_docs.append(DummyDoc(doc_id, jokes))

    def order_by(self, field_path):
      return DummyQuery(self._all_docs)

    def document(self, doc_id):
      return DummyDoc(doc_id, self._docs_by_id.get(doc_id, []))

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol({
        "0000000000": [
          {
            "key": "joke1",
            "setup_text": "Setup 1",
            "punchline_text": "Punch 1"
          },
          {
            "key": "joke2",
            "setup_text": "Setup 2",
            "punchline_text": "Punch 2"
          },
        ],
        "0000000001": [
          {
            "key": "joke3",
            "setup_text": "Setup 3",
            "punchline_text": "Punch 3"
          },
        ],
      })

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes, cursor = fs.get_joke_feed_page(cursor=None, limit=2)

  assert len(jokes) == 2
  assert jokes[0].key == "joke1"
  assert jokes[1].key == "joke2"
  # Cursor should be "doc_id:joke_index" where joke_index is the index of the NEXT joke
  assert cursor == "0000000001:0"


def test_get_joke_feed_page_with_cursor(monkeypatch):
  """Test get_joke_feed_page with cursor starts from that document."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, doc_id, jokes_data):
      self.id = doc_id
      self._jokes = jokes_data

    def exists(self):
      return True

    def to_dict(self):
      return {"jokes": self._jokes}

  docs_by_id = {
    "0000000000": [
      {
        "key": "joke1",
        "setup_text": "Setup 1",
        "punchline_text": "Punch 1"
      },
    ],
    "0000000001": [
      {
        "key": "joke2",
        "setup_text": "Setup 2",
        "punchline_text": "Punch 2"
      },
      {
        "key": "joke3",
        "setup_text": "Setup 3",
        "punchline_text": "Punch 3"
      },
    ],
  }

  class DummyQuery:

    def __init__(self, docs, start_at_doc_id=None):
      self._docs = docs
      self._start_at_doc_id = start_at_doc_id

    def order_by(self, field_path):
      return self

    def start_at(self, cursor):
      # cursor is a list with one element: [doc_id]
      if cursor:
        self._start_at_doc_id = cursor[0]
      return self

    def start_after(self, cursor):
      # Legacy support - not used with new cursor format
      return self

    def limit(self, n):
      return self

    def stream(self):
      # Filter docs based on start_at
      if self._start_at_doc_id:
        found = False
        for doc in self._docs:
          if found:
            yield doc
          elif doc.id == self._start_at_doc_id:
            found = True
            yield doc
      else:
        for doc in self._docs:
          yield doc

  class DummyCol:

    def __init__(self, docs_by_id):
      self._docs_by_id = docs_by_id
      self._all_docs = []
      for doc_id, jokes in docs_by_id.items():
        self._all_docs.append(DummyDoc(doc_id, jokes))

    def order_by(self, field_path):
      return DummyQuery(self._all_docs)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol(docs_by_id)

  monkeypatch.setattr(fs, "db", DummyDB)

  # Use cursor "0000000001:0" to start from the first joke of doc "0000000001"
  # (cursor represents the next joke to return)
  jokes, cursor = fs.get_joke_feed_page(cursor="0000000001:0", limit=2)

  assert len(jokes) == 2
  assert jokes[0].key == "joke2"
  assert jokes[1].key == "joke3"
  # Since we read limit + 1 and got exactly limit, there are no more
  assert cursor is None


def test_get_joke_feed_page_empty_feed(monkeypatch):
  """Test get_joke_feed_page with empty feed collection."""
  from services import firestore as fs

  class DummyQuery:

    def order_by(self, field_path):
      return self

    def start_after(self, cursor):
      return self

    def limit(self, n):
      return self

    def stream(self):
      return iter([])

  class DummyCol:

    def order_by(self, field_path):
      return DummyQuery()

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol()

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes, cursor = fs.get_joke_feed_page()

  assert len(jokes) == 0
  assert cursor is None


def test_get_joke_feed_page_single_document(monkeypatch):
  """Test get_joke_feed_page with single document containing fewer than limit."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, doc_id, jokes_data):
      self.id = doc_id
      self._jokes = jokes_data

    def exists(self):
      return True

    def to_dict(self):
      return {"jokes": self._jokes}

  class DummyQuery:

    def __init__(self, docs, cursor_id=None):
      self._docs = docs
      self._cursor_id = cursor_id

    def order_by(self, field_path):
      return self

    def start_after(self, cursor):
      # Filter docs after cursor
      cursor_id = cursor[0] if cursor else None
      # If starting after "0000000000" (the only doc), there are no more docs
      # This handles the check query case
      if cursor_id == "0000000000":
        return DummyQuery([], cursor_id)
      filtered = []
      found_cursor = cursor_id is None
      for doc in self._docs:
        if found_cursor:
          filtered.append(doc)
        elif doc.id == cursor_id:
          found_cursor = True
      return DummyQuery(filtered, cursor_id)

    def limit(self, n):
      return self

    def stream(self):
      return iter(self._docs)

  class DummyCol:

    def __init__(self, docs_by_id):
      self._docs_by_id = docs_by_id
      self._all_docs = []
      for doc_id, jokes in docs_by_id.items():
        self._all_docs.append(DummyDoc(doc_id, jokes))

    def order_by(self, field_path):
      return DummyQuery(self._all_docs, None)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol({
        "0000000000": [
          {
            "key": "joke1",
            "setup_text": "Setup 1",
            "punchline_text": "Punch 1"
          },
        ],
      })

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes, cursor = fs.get_joke_feed_page(limit=10)

  assert len(jokes) == 1
  assert jokes[0].key == "joke1"
  # Since we got fewer than limit jokes, there are no more
  assert cursor is None


def test_get_joke_feed_page_crosses_document_boundary(monkeypatch):
  """Test get_joke_feed_page when limit requires crossing document boundary."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, doc_id, jokes_data):
      self.id = doc_id
      self._jokes = jokes_data

    def exists(self):
      return True

    def to_dict(self):
      return {"jokes": self._jokes}

  class DummyQuery:

    def __init__(self, docs):
      self._docs = docs

    def order_by(self, field_path):
      return self

    def start_after(self, cursor):
      return self

    def limit(self, n):
      return self

    def stream(self):
      return iter(self._docs)

  class DummyCol:

    def __init__(self, docs_by_id):
      self._docs_by_id = docs_by_id
      self._all_docs = []
      for doc_id, jokes in docs_by_id.items():
        self._all_docs.append(DummyDoc(doc_id, jokes))

    def order_by(self, field_path):
      return DummyQuery(self._all_docs)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol({
        "0000000000": [
          {
            "key": "joke1",
            "setup_text": "Setup 1",
            "punchline_text": "Punch 1"
          },
          {
            "key": "joke2",
            "setup_text": "Setup 2",
            "punchline_text": "Punch 2"
          },
        ],
        "0000000001": [
          {
            "key": "joke3",
            "setup_text": "Setup 3",
            "punchline_text": "Punch 3"
          },
        ],
      })

  monkeypatch.setattr(fs, "db", DummyDB)

  jokes, cursor = fs.get_joke_feed_page(limit=3)

  assert len(jokes) == 3
  assert jokes[0].key == "joke1"
  assert jokes[1].key == "joke2"
  assert jokes[2].key == "joke3"
  # Since we read limit + 1 and got exactly limit, there are no more
  assert cursor is None


def test_get_joke_feed_page_partial_document_consumption(monkeypatch):
  """Test get_joke_feed_page when a document has more jokes than the limit."""
  from services import firestore as fs

  class DummyDoc:

    def __init__(self, doc_id, jokes_data):
      self.id = doc_id
      self._jokes = jokes_data

    def exists(self):
      return True

    def to_dict(self):
      return {"jokes": self._jokes}

  # Track which documents and indices are accessed
  accessed_docs = []
  accessed_indices = []

  class DummyQuery:

    def __init__(self, docs, start_at_doc_id=None):
      self._docs = docs
      self._start_at_doc_id = start_at_doc_id

    def order_by(self, field_path):
      return self

    def start_at(self, cursor):
      # cursor is a list with one element: [doc_id]
      if cursor:
        self._start_at_doc_id = cursor[0]
        accessed_docs.append(cursor[0])
      return self

    def start_after(self, cursor):
      # Legacy support - should not be used with new cursor format
      return self

    def stream(self):
      # Filter docs based on start_at
      if self._start_at_doc_id:
        found = False
        for doc in self._docs:
          if found:
            yield doc
          elif doc.id == self._start_at_doc_id:
            found = True
            yield doc
      else:
        for doc in self._docs:
          yield doc

  class DummyCol:

    def __init__(self, docs_by_id):
      self._docs_by_id = docs_by_id
      self._all_docs = []
      for doc_id, jokes in docs_by_id.items():
        self._all_docs.append(DummyDoc(doc_id, jokes))

    def order_by(self, field_path):
      return DummyQuery(self._all_docs)

  class DummyDB:

    def collection(self, collection_name):
      assert collection_name == "joke_feed"
      return DummyCol({
        "doc1": [
          {
            "key": f"joke{i}",
            "setup_text": f"Setup {i}",
            "punchline_text": f"Punch {i}"
          } for i in range(1, 21)  # 20 jokes in doc1
        ],
      })

  monkeypatch.setattr(fs, "db", DummyDB)

  # First call: get first 10 jokes
  accessed_docs.clear()
  jokes1, cursor1 = fs.get_joke_feed_page(cursor=None, limit=10)

  assert len(jokes1) == 10
  assert jokes1[0].key == "joke1"
  assert jokes1[9].key == "joke10"
  # Cursor should be "doc1:10" (doc ID and index of NEXT joke to return)
  assert cursor1 == "doc1:10"

  # Second call: use cursor to get next 10 jokes from same document
  accessed_docs.clear()
  jokes2, cursor2 = fs.get_joke_feed_page(cursor="doc1:10", limit=10)

  assert len(jokes2) == 10
  assert jokes2[0].key == "joke11"
  assert jokes2[9].key == "joke20"
  # No more jokes, so cursor should be None
  assert cursor2 is None
  # Should have started at doc1
  assert "doc1" in accessed_docs
