"""Tests for the firestore module."""
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
