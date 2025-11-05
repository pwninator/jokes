"""Tests for joke_category_operations module."""

from types import SimpleNamespace

import pytest

from common import joke_category_operations, models


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
  search_calls: list[dict] = []
  seasonal_calls: list[str] = []

  def fake_search_category_jokes(query, category_id):
    search_calls.append({
      "query": query,
      "category": category_id,
    })
    return [
      {
        "joke_id": "j1",
        "setup": "Why did the chicken cross the road?",
        "punchline": "To get to the other side!",
        "setup_image_url": "https://example.com/setup.jpg",
        "punchline_image_url": "https://example.com/punchline.jpg",
      },
      {
        "joke_id": "j2",
        "setup": "Knock knock!",
        "punchline": "Who's there?",
        "setup_image_url": "https://example.com/setup2.jpg",
        "punchline_image_url": "https://example.com/punchline2.jpg",
      },
    ]

  def fake_query_seasonal_jokes(client, seasonal_name):  # pylint: disable=unused-argument
    seasonal_calls.append(seasonal_name)
    return [
      {
        "joke_id": f"{seasonal_name}-1",
        "setup": "Seasonal setup",
        "punchline": "Seasonal punchline",
        "setup_image_url": "https://example.com/seasonal_setup.jpg",
        "punchline_image_url": "https://example.com/seasonal_punchline.jpg",
      },
    ]

  monkeypatch.setattr("common.joke_category_operations.search_category_jokes",
                      fake_search_category_jokes)
  monkeypatch.setattr(
    "common.joke_category_operations.query_seasonal_category_jokes",
    fake_query_seasonal_jokes)

  # Prepare fake categories store and outputs
  cache_refs: dict[str, _FakeCacheDocRef] = {}
  category_updates: dict[str, dict] = {}

  def make_db(categories: list[dict]):
    docs = [_FakeDoc(doc_id, data) for doc_id, data in categories]
    return _FakeDb(docs, cache_refs, category_updates)

  return SimpleNamespace(search_calls=search_calls,
                         seasonal_calls=seasonal_calls,
                         cache_refs=cache_refs,
                         category_updates=category_updates,
                         make_db=make_db)


def _run_refresh(monkeypatch, fake_db):
  monkeypatch.setattr("services.firestore.db", lambda: fake_db)
  # Execute
  joke_category_operations.refresh_category_caches()


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
  assert len(fake_env.search_calls) == 1
  call = fake_env.search_calls[0]
  assert call["query"] == "jokes about cats"
  assert call["category"] == "animals"
  
  # Cache write
  cache = fake_env.cache_refs.get("animals")
  assert cache is not None
  assert len(cache.set_calls) == 1
  payload = cache.set_calls[0]
  assert isinstance(payload.get("jokes"), list) and len(payload["jokes"]) == 2
  assert {
    "joke_id", "setup", "punchline", "setup_image_url", "punchline_image_url"
  }.issubset(set(payload["jokes"][0].keys()))
  # No forced state change
  assert fake_env.category_updates == {}


def test_refresh_forces_proposed_when_empty_results(monkeypatch, fake_env):
  # Arrange: search returns empty for this test
  monkeypatch.setattr(
    "common.joke_category_operations.search_category_jokes",
    lambda *args, **kwargs: [])

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


def test_refresh_uses_seasonal_name_when_present(monkeypatch, fake_env):
  categories = [("halloween", {
    "display_name": "Halloween",
    "seasonal_name": "Halloween",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  _run_refresh(monkeypatch, fake_db)

  assert fake_env.seasonal_calls == ["Halloween"]
  assert fake_env.search_calls == []
  cache = fake_env.cache_refs.get("halloween")
  assert cache is not None
  assert cache.set_calls[0]["jokes"][0]["joke_id"] == "Halloween-1"


def test_refresh_sets_proposed_when_no_query_or_seasonal(monkeypatch, fake_env):
  categories = [("misc", {
    "display_name": "Misc",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  _run_refresh(monkeypatch, fake_db)

  assert "misc" not in fake_env.cache_refs
  assert fake_env.category_updates.get("misc") == {"state": "PROPOSED"}


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

  # Assert: no search calls and no cache writes
  assert fake_env.search_calls == []
  assert fake_env.seasonal_calls == []
  assert fake_env.cache_refs == {}
  # Blank query category should be set to PROPOSED
  assert fake_env.category_updates == {"blank": {"state": "PROPOSED"}}


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


class TestSearchCategoryJokesSorting:
  """Tests for search_category_jokes sorting behavior."""

  def test_sorts_results_by_num_saved_users_fraction(self, monkeypatch):
    """Test that search results are sorted by num_saved_users_fraction in descending order."""

    # Arrange
    from services.search import JokeSearchResult
    results = [
      JokeSearchResult(joke_id="j1", vector_distance=0.1),
      JokeSearchResult(joke_id="j2", vector_distance=0.1),
      JokeSearchResult(joke_id="j3", vector_distance=0.1),
      JokeSearchResult(joke_id="j4", vector_distance=0.1),
    ]

    def fake_search_jokes(**kwargs):  # pylint: disable=unused-argument
      return results

    # Mock full jokes returned by firestore.get_punny_jokes
    # These should have the fresh num_saved_users_fraction values
    full_jokes = [
      models.PunnyJoke(
        key="j1",
        setup_text="Setup j1",
        punchline_text="Punchline j1",
        setup_image_url="https://example.com/j1-setup.jpg",
        punchline_image_url="https://example.com/j1-punchline.jpg",
        num_saved_users_fraction=0.1,
      ),
      models.PunnyJoke(
        key="j2",
        setup_text="Setup j2",
        punchline_text="Punchline j2",
        setup_image_url="https://example.com/j2-setup.jpg",
        punchline_image_url="https://example.com/j2-punchline.jpg",
        num_saved_users_fraction=0.5,
      ),
      models.PunnyJoke(
        key="j3",
        setup_text="Setup j3",
        punchline_text="Punchline j3",
        setup_image_url="https://example.com/j3-setup.jpg",
        punchline_image_url="https://example.com/j3-punchline.jpg",
        num_saved_users_fraction=0.0,
      ),
      models.PunnyJoke(
        key="j4",
        setup_text="Setup j4",
        punchline_text="Punchline j4",
        setup_image_url="https://example.com/j4-setup.jpg",
        punchline_image_url="https://example.com/j4-punchline.jpg",
        num_saved_users_fraction=0.3,
      ),
    ]

    def fake_get_punny_jokes(joke_ids):
      # Return jokes in the order requested (preserve order for testing)
      id_to_joke = {j.key: j for j in full_jokes}
      return [id_to_joke[jid] for jid in joke_ids if jid in id_to_joke]

    monkeypatch.setattr("services.search.search_jokes", fake_search_jokes)
    monkeypatch.setattr(
      "services.firestore.get_punny_jokes", fake_get_punny_jokes)

    # Act
    jokes = joke_category_operations.search_category_jokes("test query", "cat1")

    # Assert
    assert len(jokes) == 4
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[0]["setup"] == "Setup j2"
    assert jokes[0]["punchline"] == "Punchline j2"
    assert jokes[1]["joke_id"] == "j4"
    assert jokes[1]["setup"] == "Setup j4"
    assert jokes[2]["joke_id"] == "j1"
    assert jokes[2]["setup"] == "Setup j1"
    assert jokes[3]["joke_id"] == "j3"
    assert jokes[3]["setup"] == "Setup j3"


class TestQuerySeasonalCategoryJokesSorting:
  """Tests for query_seasonal_category_jokes sorting behavior."""

  def test_sorts_docs_by_num_saved_users_fraction(self, monkeypatch):
    """Test that seasonal jokes are sorted by num_saved_users_fraction in descending order."""

    # Arrange
    class _MockDoc:

      def __init__(self, doc_id, fraction):
        self.id = doc_id
        self._fraction = fraction
        self._data = {
          "setup_text": f"Setup {doc_id}",
          "punchline_text": f"Punchline {doc_id}",
          "num_saved_users_fraction": fraction,
        }

      def to_dict(self):
        return self._data

    class _MockQuery:

      def __init__(self, docs):
        self._docs = docs

      def where(self, filter):  # pylint: disable=redefined-builtin
        return self

      def limit(self, limit):
        return self

      def stream(self):
        return iter(self._docs)

    class _MockCollection:

      def __init__(self, docs):
        self._docs = docs

      def collection(self, name):
        return self

      def where(self, filter):  # pylint: disable=redefined-builtin
        return _MockQuery(self._docs)

    docs = [
      _MockDoc("j1", 0.1),
      _MockDoc("j2", 0.5),
      _MockDoc("j3", 0.0),
      _MockDoc("j4", 0.3),
    ]

    mock_client = _MockCollection(docs)

    # Act
    jokes = joke_category_operations.query_seasonal_category_jokes(
      mock_client, "Halloween")

    # Assert
    assert len(jokes) == 4
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[1]["joke_id"] == "j4"
    assert jokes[2]["joke_id"] == "j1"
    assert jokes[3]["joke_id"] == "j3"

  def test_handles_missing_fraction_field(self, monkeypatch):
    """Test that docs without num_saved_users_fraction are sorted last."""

    # Arrange
    class _MockDoc:

      def __init__(self, doc_id, fraction=None):
        self.id = doc_id
        self._data = {
          "setup_text": f"Setup {doc_id}",
          "punchline_text": f"Punchline {doc_id}",
        }
        if fraction is not None:
          self._data["num_saved_users_fraction"] = fraction

      def to_dict(self):
        return self._data

    class _MockQuery:

      def __init__(self, docs):
        self._docs = docs

      def where(self, filter):  # pylint: disable=redefined-builtin
        return self

      def limit(self, limit):
        return self

      def stream(self):
        return iter(self._docs)

    class _MockCollection:

      def __init__(self, docs):
        self._docs = docs

      def collection(self, name):
        return self

      def where(self, filter):  # pylint: disable=redefined-builtin
        return _MockQuery(self._docs)

    docs = [
      _MockDoc("j1", None),
      _MockDoc("j2", 0.2),
    ]

    mock_client = _MockCollection(docs)

    # Act
    jokes = joke_category_operations.query_seasonal_category_jokes(
      mock_client, "Halloween")

    # Assert
    assert len(jokes) == 2
    assert jokes[0]["joke_id"] == "j2"
    assert jokes[1]["joke_id"] == "j1"

