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

  def fake_search_category_jokes(
      query,
      category_id,
      *,
      distance_threshold=None,  # pylint: disable=unused-argument
  ):
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

  # Avoid depending on Firestore 'jokes' collection in these unit tests.
  def fake_get_punny_jokes(joke_ids):
    results = []
    for jid in joke_ids:
      results.append(
        models.PunnyJoke(
          key=jid,
          setup_text="S",
          punchline_text="P",
          num_saved_users_fraction=0.0,
        ))
    return results

  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)
  # Prevent sheet generation from touching Firestore in these cache refresh tests.
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
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
  monkeypatch.setattr("common.joke_category_operations.search_category_jokes",
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


def test_refresh_sets_proposed_when_no_query_or_seasonal(
    monkeypatch, fake_env):
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

    def fake_search_jokes(**kwargs):
      assert kwargs["distance_threshold"] == 0.123
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
    monkeypatch.setattr("services.firestore.get_punny_jokes",
                        fake_get_punny_jokes)

    # Act
    jokes = joke_category_operations.search_category_jokes(
      "test query",
      "cat1",
      distance_threshold=0.123,
    )

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


class TestQueryTagsCategoryJokesBatching:
  """Tests for tag query batching and union semantics."""

  def test_batches_tags_over_firestore_limit_and_unions_results(self):
    """Tags > 10 should be partitioned into multiple queries and unioned."""

    class _FakeDoc:

      def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = dict(data)

      def to_dict(self):
        return dict(self._data)

    class _FakeQuery:

      def __init__(self, tag_to_docs: dict[str, list[_FakeDoc]],
                   seen_tag_chunks: list[list[str]]):
        self._tag_to_docs = tag_to_docs
        self._seen_tag_chunks = seen_tag_chunks
        self._tag_chunk: list[str] = []

      def where(self, *, filter):  # pylint: disable=redefined-builtin
        # We only care about the array_contains_any filter on "tags".
        field_path = getattr(filter, "field_path", None)
        op_string = getattr(filter, "op_string", None)
        value = getattr(filter, "value", None)
        if field_path == "tags" and op_string == "array_contains_any":
          assert isinstance(value, list)
          self._tag_chunk = list(value)
          self._seen_tag_chunks.append(list(value))
        return self

      def limit(self, _n: int):
        return self

      def stream(self):
        docs: list[_FakeDoc] = []
        for tag in self._tag_chunk:
          docs.extend(self._tag_to_docs.get(tag, []))
        return docs

    class _FakeClient:

      def __init__(self, tag_to_docs: dict[str, list[_FakeDoc]]):
        self._tag_to_docs = tag_to_docs
        self.seen_tag_chunks: list[list[str]] = []

      def collection(self, name: str):
        assert name == "jokes"
        return _FakeQuery(self._tag_to_docs, self.seen_tag_chunks)

    # Arrange: 12 tags forces 2 chunks (10 + 2). Include overlap to prove union.
    tags = [f"t{i}" for i in range(12)]
    tag_to_docs = {
      "t0": [
        _FakeDoc(
          "j1",
          {
            "setup_text": "S1",
            "punchline_text": "P1",
            "setup_image_url": "u1",
            "punchline_image_url": "v1",
            "num_saved_users_fraction": 0.2,
          },
        ),
      ],
      "t1": [
        _FakeDoc(
          "j2",
          {
            "setup_text": "S2",
            "punchline_text": "P2",
            "setup_image_url": "u2",
            "punchline_image_url": "v2",
            "num_saved_users_fraction": 0.9,
          },
        ),
      ],
      # Overlap: j2 appears again in the second chunk as well.
      "t11": [
        _FakeDoc(
          "j2",
          {
            "setup_text": "S2b",
            "punchline_text": "P2b",
            "setup_image_url": "u2b",
            "punchline_image_url": "v2b",
            "num_saved_users_fraction": 0.9,
          },
        ),
        _FakeDoc(
          "j3",
          {
            "setup_text": "S3",
            "punchline_text": "P3",
            "setup_image_url": "u3",
            "punchline_image_url": "v3",
            "num_saved_users_fraction": 0.4,
          },
        ),
      ],
    }
    client = _FakeClient(tag_to_docs)

    # Act
    payload = joke_category_operations.query_tags_category_jokes(client, tags)

    # Assert: two array_contains_any chunks observed: first 10, then remaining 2.
    assert client.seen_tag_chunks[0] == tags[:10]
    assert client.seen_tag_chunks[1] == tags[10:]

    # Union + dedupe: j2 should appear once. Sorted by num_saved_users_fraction.
    assert [p["joke_id"] for p in payload] == ["j2", "j3", "j1"]

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


def _make_jokes(n: int) -> list[models.PunnyJoke]:
  jokes: list[models.PunnyJoke] = []
  for i in range(n):
    jokes.append(
      models.PunnyJoke(
        key=f"j{i + 1}",
        setup_text="S",
        punchline_text="P",
        num_saved_users_fraction=0.0,
      ))
  return jokes


def test_ensure_category_joke_sheets_skips_when_under_5(monkeypatch):
  calls: list[dict] = []

  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])

  def fake_get_sheet(joke_ids, *, category_id=None, quality=80):  # pylint: disable=unused-argument
    calls.append({"joke_ids": list(joke_ids), "category_id": category_id})
    return "gs://bucket/file.pdf"

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.get_joke_notes_sheet", fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(4),
  )
  assert calls == []


def test_ensure_category_joke_sheets_creates_full_batches_only(monkeypatch):
  calls: list[dict] = []

  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])

  def fake_get_sheet(joke_ids, *, category_id=None, quality=80):  # pylint: disable=unused-argument
    calls.append({"joke_ids": list(joke_ids), "category_id": category_id})
    return "gs://bucket/file.pdf"

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.get_joke_notes_sheet", fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(9),
  )

  # 9 uncovered -> one full sheet of 5, last 4 ignored
  assert calls == [{
    "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
    "category_id": "cats",
  }]


def test_ensure_category_joke_sheets_respects_existing_coverage(monkeypatch):
  calls: list[dict] = []

  existing = [
    models.JokeSheet(
      key="s1",
      joke_str="j1,j2,j3,j4,j5",
      joke_ids=["j1", "j2", "j3", "j4", "j5"],
      category_id="cats",
    )
  ]
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: existing)

  def fake_get_sheet(joke_ids, *, category_id=None, quality=80):  # pylint: disable=unused-argument
    calls.append({"joke_ids": list(joke_ids), "category_id": category_id})
    return "gs://bucket/file.pdf"

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.get_joke_notes_sheet", fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(10),
  )

  # First 5 covered by existing sheet, next 5 should be generated.
  assert calls == [{
    "joke_ids": ["j6", "j7", "j8", "j9", "j10"],
    "category_id": "cats",
  }]
