"""Tests for category cache refresh in joke_auto_fns._refresh_category_caches."""

from types import SimpleNamespace

import pytest

from common import models, config


class _FakeDoc:

  def __init__(self, doc_id: str, data: dict):
    self.id = doc_id
    self._data = dict(data)
    self.exists = True

  def to_dict(self):
    return dict(self._data)


class _FakeCacheDocRef:

  def __init__(self):
    self.set_calls: list[dict] = []

  def set(self, payload, merge: bool | None = None):  # pylint: disable=unused-argument
    self.set_calls.append(dict(payload))


class _FakeCategoryDocRef:

  def __init__(self, doc_id: str, cache_refs: dict[str, _FakeCacheDocRef],
               category_updates: dict[str, dict]):
    self._id = doc_id
    self._cache_refs = cache_refs
    self._category_updates = category_updates

  def collection(self, name: str):  # only category_jokes is expected
    assert name == "category_jokes"

    class _Sub:

      def __init__(self, cache_refs, doc_id):
        self._cache_refs = cache_refs
        self._doc_id = doc_id

      def document(self, name: str):  # only cache
        assert name == "cache"
        ref = self._cache_refs.setdefault(self._doc_id, _FakeCacheDocRef())
        return ref

    return _Sub(self._cache_refs, self._id)

  def set(self, payload: dict, merge: bool = False):  # category state update
    self._category_updates[self._id] = dict(payload)


class _FakeCollection:

  def __init__(self, name: str, categories: list[_FakeDoc], cache_refs,
               category_updates):
    self._name = name
    self._categories = categories
    self._cache_refs = cache_refs
    self._category_updates = category_updates

  def stream(self):
    assert self._name == "joke_categories"
    return list(self._categories)

  def document(self, doc_id: str):
    return _FakeCategoryDocRef(doc_id, self._cache_refs,
                               self._category_updates)


class _FakeDb:

  def __init__(self, categories: list[_FakeDoc], cache_refs, category_updates):
    self._categories = categories
    self._cache_refs = cache_refs
    self._category_updates = category_updates

  def collection(self, name: str):
    if name == "joke_categories":
      return _FakeCollection(name, self._categories, self._cache_refs,
                             self._category_updates)
    raise AssertionError(f"Unexpected collection: {name}")


@pytest.fixture(name="fake_env")
def fake_env_fixture(monkeypatch):
  # Capture search calls
  calls: list[dict] = []

  def fake_search_jokes(query, label, field_filters, limit,
                        distance_threshold):  # pylint: disable=unused-argument
    calls.append({
      "query": query,
      "label": label,
      "filters": list(field_filters),
      "limit": limit,
      "threshold": distance_threshold,
    })

    # Return two results by default
    class _R:

      def __init__(self, key):
        self.joke = models.PunnyJoke(key=key,
                                     setup_text="S",
                                     punchline_text="P")

    return [_R("j1"), _R("j2")]

  monkeypatch.setattr("services.search.search_jokes", fake_search_jokes)

  # Prepare fake categories store and outputs
  cache_refs: dict[str, _FakeCacheDocRef] = {}
  category_updates: dict[str, dict] = {}

  def make_db(categories: list[dict]):
    docs = [_FakeDoc(doc_id, data) for doc_id, data in categories]
    return _FakeDb(docs, cache_refs, category_updates)

  return SimpleNamespace(calls=calls,
                         cache_refs=cache_refs,
                         category_updates=category_updates,
                         make_db=make_db)


def _run_refresh(monkeypatch, fake_db):
  import py_quill.functions.joke_auto_fns as mod
  monkeypatch.setattr("services.firestore.db", lambda: fake_db)
  # Execute
  mod._refresh_category_caches()  # pylint: disable=protected-access


def test_refresh_updates_cache_for_approved_category(monkeypatch, fake_env):
  # Arrange
  categories = [("animals", {
    "display_name": "Animals",
    "joke_description_query": "cats",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  # Act
  _run_refresh(monkeypatch, fake_db)

  # Assert: search params
  assert len(fake_env.calls) == 1
  call = fake_env.calls[0]
  assert call["query"] == "jokes about cats"
  assert call["label"] == "daily_cache:category:animals"
  assert call["limit"] == 100
  assert call["threshold"] == config.JOKE_SEARCH_TIGHT_THRESHOLD
  # Filters include state in [PUBLISHED, DAILY] and is_public True
  assert ("state", "in",
          [models.JokeState.PUBLISHED.value,
           models.JokeState.DAILY.value]) in call["filters"]
  assert ("is_public", "==", True) in call["filters"]

  # Cache write
  cache = fake_env.cache_refs.get("animals")
  assert cache is not None
  assert len(cache.set_calls) == 1
  payload = cache.set_calls[0]
  assert isinstance(payload.get("jokes"), list) and len(payload["jokes"]) == 2
  assert {"joke_id", "setup_image_url",
          "punchline_image_url"}.issubset(set(payload["jokes"][0].keys()))
  # No forced state change
  assert fake_env.category_updates == {}


def test_refresh_forces_proposed_when_empty_results(monkeypatch, fake_env):
  # Arrange: search returns empty for this test
  def empty_search(**kwargs):  # pylint: disable=unused-argument
    return []

  monkeypatch.setattr("services.search.search_jokes",
                      lambda **kwargs: empty_search(**kwargs))

  categories = [("sports", {
    "display_name": "Sports",
    "joke_description_query": "basketball",
    "state": "PROPOSED",
  })]
  fake_db = fake_env.make_db(categories)

  # Act
  _run_refresh(monkeypatch, fake_db)

  # Assert: empty cache written and state set to PROPOSED
  cache = fake_env.cache_refs.get("sports")
  assert cache is not None and cache.set_calls[0] == {"jokes": []}
  assert fake_env.category_updates.get("sports") == {"state": "PROPOSED"}


def test_refresh_skips_non_target_states_and_blank_queries(
    monkeypatch, fake_env):
  # Arrange: includes REJECTED and blank query categories which should be skipped
  categories = [
    ("rejected", {
      "display_name": "Rejected",
      "joke_description_query": "bad",
      "state": "REJECTED",
    }),
    ("blank", {
      "display_name": "Blank",
      "joke_description_query": "  ",
      "state": "APPROVED",
    }),
  ]
  fake_db = fake_env.make_db(categories)

  # Act
  _run_refresh(monkeypatch, fake_db)

  # Assert: no search calls and no writes
  assert fake_env.calls == []
  assert fake_env.cache_refs == {}
  assert fake_env.category_updates == {}


def test_refresh_continues_on_search_error(monkeypatch, fake_env):
  # Arrange: two categories, first raises, second succeeds
  class _Err(Exception):
    pass

  def search_flaky(query, label, field_filters, limit, distance_threshold):  # pylint: disable=unused-argument
    if "first" in label:
      raise _Err("boom")

    class _R:

      def __init__(self, key):
        self.joke = models.PunnyJoke(key=key,
                                     setup_text="S",
                                     punchline_text="P")

    return [_R("ok")]

  monkeypatch.setattr("services.search.search_jokes", search_flaky)

  categories = [
    ("first", {
      "display_name": "First",
      "joke_description_query": "x",
      "state": "APPROVED",
    }),
    ("second", {
      "display_name": "Second",
      "joke_description_query": "y",
      "state": "APPROVED",
    }),
  ]

  fake_db = fake_env.make_db(categories)

  # Act
  _run_refresh(monkeypatch, fake_db)

  # Assert: second category still cached
  cache = fake_env.cache_refs.get("second")
  assert cache is not None and len(cache.set_calls) == 1
