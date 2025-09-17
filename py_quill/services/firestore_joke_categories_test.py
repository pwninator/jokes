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
      self._exists = False

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      captured[self.k] = data

    async def get(self):
      return self

    @property
    def exists(self):
      return self._exists

    def to_dict(self):
      return {}

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

    async def get(self):
        return self

    @property
    def exists(self):
        return False

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


@pytest.mark.asyncio
async def test_upsert_joke_categories_state_default_proposed(monkeypatch):
  captured = {}

  class DummyDoc:

    def __init__(self, k):
      self.k = k
      self._exists = False

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      captured[self.k] = data

    async def get(self):
        return self

    @property
    def exists(self):
        return self._exists

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
  ]

  await fs.upsert_joke_categories(cats)

  assert captured["animal_jokes"]["state"] == models.JokeCategoryState.PROPOSED.value


@pytest.mark.asyncio
async def test_upsert_joke_categories_approved_fails(monkeypatch):
  class DummyDoc:

    def __init__(self, k):
      self.k = k
      self._exists = True
      self._data = {"state": models.JokeCategoryState.APPROVED.value}

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      raise AssertionError("Should not be called for approved categories")

    async def get(self):
        return self

    @property
    def exists(self):
        return self._exists

    def to_dict(self):
        return self._data

  class DummyCol:

    def document(self, key):
      return DummyDoc(key)

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "get_async_db", lambda: DummyDB())

  with pytest.raises(Exception):
    await fs.upsert_joke_categories([
      models.JokeCategory(display_name="Animal Jokes",
                          joke_description_query="animals"),
    ])


@pytest.mark.asyncio
async def test_upsert_joke_categories_rejected_becomes_proposed(monkeypatch):
  captured = {}

  class DummyDoc:

    def __init__(self, k):
      self.k = k
      self._exists = True
      self._data = {"state": models.JokeCategoryState.REJECTED.value}

    async def set(self, data, merge=False):  # pylint: disable=unused-argument
      captured[self.k] = data

    async def get(self):
        return self

    @property
    def exists(self):
        return self._exists

    def to_dict(self):
        return self._data

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
                        state=models.JokeCategoryState.REJECTED),
  ]

  await fs.upsert_joke_categories(cats)

  assert captured["animal_jokes"]["state"] == models.JokeCategoryState.PROPOSED.value


@pytest.mark.asyncio
async def test_delete_joke_category(monkeypatch):
  deleted_key = None

  class DummyDoc:

    def __init__(self, k):
      self.k = k

    async def delete(self):
      nonlocal deleted_key
      deleted_key = self.k

  class DummyCol:

    def document(self, key):
      return DummyDoc(key)

  class DummyDB:

    def collection(self, _name):
      return DummyCol()

  monkeypatch.setattr(fs, "get_async_db", lambda: DummyDB())

  await fs.delete_joke_category("animal_jokes")

  assert deleted_key == "animal_jokes"
