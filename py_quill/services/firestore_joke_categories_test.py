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
                   "joke_description_query": "animals"
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
                        joke_description_query="animals"),
    models.JokeCategory(display_name="Seasonal",
                        joke_description_query="season"),
  ]

  await fs.upsert_joke_categories(cats)

  assert "animal_jokes" in captured
  assert captured["animal_jokes"]["display_name"] == "Animal Jokes"
  assert captured["seasonal"]["joke_description_query"] == "season"


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

  # Missing/blank fields after stripping should raise ValueError
  with pytest.raises(ValueError):
    await fs.upsert_joke_categories([
      models.JokeCategory(display_name="   ", joke_description_query="ok"),
    ])

  with pytest.raises(ValueError):
    await fs.upsert_joke_categories([
      models.JokeCategory(display_name="Name", joke_description_query="   "),
    ])
