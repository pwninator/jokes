"""Tests for joke categories Firestore helpers."""

import pytest
from common import models
from services import firestore as fs


def test_get_all_joke_categories_sync(monkeypatch):

  class DummyDoc:

    def __init__(self, id_, exists=True, data=None):
      self.id = id_
      self._exists = exists
      self._data = data or {
        "display_name": "Animal Jokes",
        "joke_description_query": "animals"
      }

    @property
    def exists(self):
      return self._exists

    def to_dict(self):
      return self._data

  class DummyQuery:

    def stream(self):
      return [
        DummyDoc("animal",
                 data={
                   "display_name": "Animal Jokes",
                   "joke_description_query": "animals",
                   "image_description": "cute animals"
                 }),
        DummyDoc("seasonal",
                 data={
                   "display_name": "Seasonal",
                   "joke_description_query": "season"
                 }),
      ]

  class DummyDB:

    def collection(self, _name):
      return DummyQuery()

  monkeypatch.setattr(fs, "db", lambda: DummyDB())

  cats = fs.get_all_joke_categories()
  assert len(cats) == 2
  assert isinstance(cats[0], models.JokeCategory)
  assert cats[0].display_name == "Animal Jokes"
  assert cats[1].joke_description_query == "season"
  assert cats[0].image_description == "cute animals"


@pytest.mark.asyncio
async def test_upsert_joke_categories_async(monkeypatch):
  captured = {}

  class DummyDoc:

    def __init__(self, k):
      self.k = k

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      captured[self.k] = data

  class DummyCol:

    def document(self, key):
      return DummyDoc(key)

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "get_async_db", lambda: DummyDB())

  cats = [
    models.JokeCategory(display_name="Animal Jokes",
                        joke_description_query="animals",
                        image_description="cute animals"),
    models.JokeCategory(display_name="Seasonal",
                        joke_description_query="season"),
  ]

  await fs.upsert_joke_categories(cats)

  assert "animal_jokes" in captured
  assert captured["animal_jokes"]["display_name"] == "Animal Jokes"
  assert captured["seasonal"]["joke_description_query"] == "season"
  assert captured["animal_jokes"]["image_description"] == "cute animals"


@pytest.mark.asyncio
async def test_upsert_joke_categories_validation(monkeypatch):

  class DummyDoc:

    def __init__(self, k):
      self.k = k

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      raise AssertionError("Should not be called for invalid categories")

  class DummyCol:

    def document(self, key):
      return DummyDoc(key)

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "get_async_db", lambda: DummyDB())

  with pytest.raises(ValueError):
    await fs.upsert_joke_categories([
      models.JokeCategory(display_name="Name"),
    ])


def test_update_and_get_joke_categories_cache(monkeypatch):
  captured: dict[str, object] = {}

  class DummyDoc:

    def __init__(self, doc_id: str, data: dict, exists: bool = True):
      self.id = doc_id
      self._data = dict(data)
      self.exists = exists

    def to_dict(self):
      return dict(self._data)

  class DummyCategoriesQuery:

    def stream(self):
      return [
        DummyDoc(
          "animals",
          {
            "display_name": "Animals",
            "joke_description_query": "animals",
            "image_url": "https://img/animals.png",
            "state": "APPROVED",
          },
        ),
        DummyDoc(
          "empty",
          {
            "display_name": "",
          },
        ),
      ]

  class DummyCacheDoc:

    def __init__(self):
      self.exists = False
      self._data: dict | None = None

    def set(self, payload):
      self.exists = True
      self._data = dict(payload)
      captured["payload"] = dict(payload)

    def get(self):
      return self

    def to_dict(self):
      return dict(self._data) if isinstance(self._data, dict) else {}

  class DummyCacheCollection:

    def __init__(self, cache_doc: DummyCacheDoc):
      self._cache_doc = cache_doc

    def document(self, doc_id: str):
      assert doc_id == "joke_categories"
      return self._cache_doc

  class DummyDB:

    def __init__(self):
      self._cache_doc = DummyCacheDoc()

    def collection(self, name: str):
      if name == "joke_categories":
        return DummyCategoriesQuery()
      if name == "joke_cache":
        return DummyCacheCollection(self._cache_doc)
      raise AssertionError(f"Unexpected collection: {name}")

  db = DummyDB()
  monkeypatch.setattr(fs, "db", lambda: db)
  monkeypatch.setattr(fs, "SERVER_TIMESTAMP", "TS")

  count = fs.update_joke_categories_cache()
  assert count == 1
  assert captured["payload"]["refresh_timestamp"] == "TS"
  assert captured["payload"]["categories"] == [{
    "category_id": "animals",
    "display_name": "Animals",
    "image_url": "https://img/animals.png",
    "state": "APPROVED",
  }]

  categories = fs.get_all_joke_categories(use_cache=True)
  assert len(categories) == 1
  assert categories[0].id == "animals"
  assert categories[0].display_name == "Animals"
  assert categories[0].image_url == "https://img/animals.png"
  assert categories[0].state == "APPROVED"


def test_get_uncategorized_public_jokes_filters_by_category_id(monkeypatch):
  monkeypatch.setattr(fs, "FieldFilter",
                      lambda field, op, value: (field, op, value))

  captured_filters: list[tuple[str, str, object]] = []

  class DummyDoc:

    def __init__(self, doc_id: str):
      self.id = doc_id
      self.exists = True

    def to_dict(self):
      return {
        "setup_text": "S",
        "punchline_text": "P",
        "is_public": True,
        "category_id": "_uncategorized",
      }

  class DummyQuery:

    def where(self, *, filter=None):  # pylint: disable=redefined-builtin
      captured_filters.append(filter)
      return self

    def stream(self):
      return [DummyDoc("j1"), DummyDoc("j2")]

  class DummyDB:

    def collection(self, name: str):
      assert name == "jokes"
      return DummyQuery()

  monkeypatch.setattr(fs, "db", lambda: DummyDB())

  jokes = fs.get_uncategorized_public_jokes([])
  assert [j.key for j in jokes] == ["j1", "j2"]
  assert ("is_public", "==", True) in captured_filters
  assert ("category_id", "==", "_uncategorized") in captured_filters