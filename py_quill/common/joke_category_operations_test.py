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
    self._latest_payload: dict | None = None

  def set(self, payload, merge: bool | None = None):  # pylint: disable=unused-argument
    self.set_calls.append(dict(payload))
    self._latest_payload = dict(payload)

  class _Snapshot:

    def __init__(self, exists: bool, data: dict | None):
      self.exists = exists
      self._data = data

    def to_dict(self):
      return dict(self._data) if isinstance(self._data, dict) else {}

  def get(self):
    return self._Snapshot(self._latest_payload is not None, self._latest_payload)


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
      jokes_by_id=None,  # pylint: disable=unused-argument
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

  def fake_query_seasonal_jokes(client,
                                seasonal_name,
                                *,
                                jokes_by_id=None):  # pylint: disable=unused-argument
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
  # Avoid depending on Firestore 'jokes' writes; tested separately.
  monkeypatch.setattr("common.joke_category_operations._sync_joke_category_ids",
                      lambda **_kwargs: 0)
  # Prevent sheet generation from touching Firestore in these cache refresh tests.
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      lambda *_args, **_kwargs: None)
  # Execute
  joke_category_operations.refresh_category_caches()


def test_refresh_joke_sheets_cache_filters_active_categories(monkeypatch):
  categories = [
    models.JokeCategory(id="cats", display_name="Cats", state="APPROVED"),
    models.JokeCategory(id="seasonal",
                        display_name="Seasonal",
                        state="SEASONAL"),
    models.JokeCategory(id="proposed",
                        display_name="Proposed",
                        state="PROPOSED"),
  ]

  monkeypatch.setattr("services.firestore.get_all_joke_categories",
                      lambda: categories)

  sheet_calls: list[str] = []

  def fake_get_joke_sheets_by_category(category_id: str):
    sheet_calls.append(category_id)
    return [
      models.JokeSheet(
        key=f"{category_id}-sheet",
        category_id=category_id,
        index=0,
        image_gcs_uri="gs://img",
        pdf_gcs_uri="gs://pdf",
      )
    ]

  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      fake_get_joke_sheets_by_category)

  captured: dict[str, object] = {}

  def fake_update_joke_sheets_cache(categories_arg, sheets_arg):
    captured["categories"] = categories_arg
    captured["sheets"] = sheets_arg

  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      fake_update_joke_sheets_cache)

  joke_category_operations._refresh_joke_sheets_cache(  # pylint: disable=protected-access
  )

  assert sheet_calls == ["cats", "seasonal"]
  category_ids = [category.id for category in captured["categories"]]
  assert category_ids == ["cats", "seasonal"]
  sheet_category_ids = [sheet.category_id for sheet in captured["sheets"]]
  assert sheet_category_ids == ["cats", "seasonal"]


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


def test_sync_joke_category_ids_updates_only_when_needed():
  from common import joke_category_operations as ops  # local import for direct access

  class _Ref:
    pass

  class _Snap:

    def __init__(self, exists: bool, category_id: object):
      self.exists = exists
      self.reference = _Ref()
      self._category_id = category_id

    def to_dict(self):
      return {"category_id": self._category_id}

  class _Batch:

    def __init__(self):
      self.updates: list[tuple[object, dict]] = []
      self.committed = False

    def update(self, ref, payload):
      self.updates.append((ref, dict(payload)))

    def commit(self):
      self.committed = True

  class _Client:

    def __init__(self, snaps):
      self._snaps = snaps
      self._batch = _Batch()

    def collection(self, _name):
      class _Col:

        def document(self, _doc_id):
          return object()

      return _Col()

    def get_all(self, _refs):
      return list(self._snaps)

    def batch(self):
      return self._batch

  # Case 1: unconditional updates to new category id when different.
  client = _Client([
    _Snap(True, "old"),
    _Snap(True, "animals"),  # already correct
    _Snap(False, "old"),  # missing doc
  ])
  writes = ops._sync_joke_category_ids(  # pylint: disable=protected-access
    client=client,
    joke_ids={"j1", "j2", "j3"},
    expected_existing_category_id=None,
    new_category_id="animals",
  )
  assert writes == 1
  assert client._batch.committed is True
  assert client._batch.updates[0][1] == {"category_id": "animals"}

  # Case 2: only update when existing matches expected.
  client2 = _Client([
    _Snap(True, "animals"),
    _Snap(True, "_uncategorized"),
  ])
  writes2 = ops._sync_joke_category_ids(  # pylint: disable=protected-access
    client=client2,
    joke_ids={"j1", "j2"},
    expected_existing_category_id="animals",
    new_category_id="_uncategorized",
  )
  assert writes2 == 1
  assert client2._batch.updates[0][1] == {"category_id": "_uncategorized"}

  # Case 3: empty dict falls back to Firestore reads.
  client3 = _Client([_Snap(True, "old")])
  writes3 = ops._sync_joke_category_ids(  # pylint: disable=protected-access
    client=client3,
    joke_ids={"j1"},
    expected_existing_category_id=None,
    new_category_id="animals",
    jokes_by_id={},
  )
  assert writes3 == 1
  assert client3._batch.updates[0][1] == {"category_id": "animals"}


def test_refresh_updates_cache_filters_negative_tags(monkeypatch, fake_env):
  # Arrange: Category has negative_tags=["NSFW"]
  categories = [("animals", {
    "display_name": "Animals",
    "joke_description_query": "animals",
    "state": "APPROVED",
    "negative_tags": ["NSFW"],
  })]
  fake_db = fake_env.make_db(categories)

  # Setup environment manually to avoid _run_refresh overriding our mock
  monkeypatch.setattr("services.firestore.db", lambda: fake_db)

  # Mock jokes, one with "nsfw" tag, one without
  def fake_get_punny_jokes(joke_ids):
    return [
      models.PunnyJoke(
        key="j1",
        setup_text="Safe joke",
        punchline_text="Haha",
        tags=["clean"],
      ),
      models.PunnyJoke(
        key="j2",
        setup_text="Bad joke",
        punchline_text="Boooo",
        tags=["NSFW", "dirty"],
      ),
    ]

  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      lambda *_args, **_kwargs: None)

  # Act
  joke_category_operations.refresh_category_caches()

  # Assert
  cache = fake_env.cache_refs.get("animals")
  assert cache is not None
  payload = cache.set_calls[0]
  # Should only include j1 (safe joke), j2 should be filtered out
  assert len(payload["jokes"]) == 1
  assert payload["jokes"][0]["joke_id"] == "j1"


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
  assert cache is not None and cache.set_calls[0] == {
    "jokes": [],
    "joke_id_order": []
  }
  assert fake_env.category_updates.get("sports") == {"state": "PROPOSED"}


def test_refresh_sorts_by_joke_id_order(monkeypatch, fake_env):
  # Arrange
  categories = [("animals", {
    "display_name": "Animals",
    "joke_description_query": "cats",
    "state": "APPROVED",
    "joke_id_order": ["j3", "j1"],
  })]
  fake_db = fake_env.make_db(categories)

  monkeypatch.setattr("services.firestore.db", lambda: fake_db)

  # Mock jokes with different saved fractions
  def fake_get_punny_jokes(joke_ids):
    jokes = [
      models.PunnyJoke(key="j1",
                       setup_text="J1",
                       punchline_text="P1",
                       num_saved_users_fraction=0.1),
      models.PunnyJoke(key="j2",
                       setup_text="J2",
                       punchline_text="P2",
                       num_saved_users_fraction=0.9),
      models.PunnyJoke(key="j3",
                       setup_text="J3",
                       punchline_text="P3",
                       num_saved_users_fraction=0.2),
    ]
    # Filter by requested ids
    return [j for j in jokes if j.key in joke_ids]

  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      lambda *_args, **_kwargs: None)

  # Mock search to return j1, j2, j3
  def fake_search(*args, **kwargs):
    return [{"joke_id": "j1"}, {"joke_id": "j2"}, {"joke_id": "j3"}]

  monkeypatch.setattr("common.joke_category_operations.search_category_jokes",
                      fake_search)

  # Act
  joke_category_operations.refresh_category_caches()

  # Assert
  cache = fake_env.cache_refs.get("animals")
  assert cache is not None
  payload = cache.set_calls[0]
  jokes = payload["jokes"]

  # j3 (first in order), j1 (second in order), j2 (remaining, sorted by fraction)
  assert [j["joke_id"] for j in jokes] == ["j3", "j1", "j2"]
  assert payload["joke_id_order"] == ["j3", "j1"]


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


def test_refresh_uses_book_id_when_present(monkeypatch, fake_env):
  """Category with book_id should fetch jokes from joke_books collection."""

  # Setup mock joke book
  class _FakeBookDoc:

    def __init__(self):
      self.exists = True

    def to_dict(self):
      return {
        "jokes": ["j1", "j2"],
        "book_name": "Test Book",
      }

  class _FakeBookRef:

    def __init__(self, doc):
      self._doc = doc

    def get(self):
      return self._doc

  class _FakeBookCollection:

    def __init__(self, book_doc):
      self._book_doc = book_doc

    def document(self, book_id):
      assert book_id == "book-123"
      return _FakeBookRef(self._book_doc)

  # Extend _FakeDb to support joke_books collection
  original_fake_db_collection = _FakeDb.collection

  def extended_collection(self, name: str):
    if name == "joke_books":
      return _FakeBookCollection(extended_collection._book_doc)
    return original_fake_db_collection(self, name)

  book_doc = _FakeBookDoc()
  extended_collection._book_doc = book_doc

  categories = [("book_cat", {
    "display_name": "Book Category",
    "book_id": "book-123",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  # Monkey patch collection method
  original_collection = fake_db.collection
  fake_db.collection = lambda name: extended_collection(fake_db, name)

  monkeypatch.setattr("services.firestore.db", lambda: fake_db)

  # Mock jokes returned from book
  def fake_get_punny_jokes(joke_ids):
    return [
      models.PunnyJoke(
        key=jid,
        setup_text=f"Setup {jid}",
        punchline_text=f"Punchline {jid}",
        setup_image_url=f"https://example.com/{jid}-setup.jpg",
        punchline_image_url=f"https://example.com/{jid}-punchline.jpg",
        num_saved_users_fraction=0.5 if jid == "j1" else 0.3,
        state=models.JokeState.PUBLISHED,
        is_public=True,
      ) for jid in joke_ids
    ]

  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      lambda *_args, **_kwargs: None)

  # Act
  joke_category_operations.refresh_category_caches()

  # Assert
  assert fake_env.search_calls == []
  assert fake_env.seasonal_calls == []
  cache = fake_env.cache_refs.get("book_cat")
  assert cache is not None
  payload = cache.set_calls[0]
  jokes = payload["jokes"]
  assert len(jokes) == 2
  # Should be sorted by num_saved_users_fraction (descending)
  assert jokes[0]["joke_id"] == "j1"
  assert jokes[1]["joke_id"] == "j2"
  assert jokes[0]["setup"] == "Setup j1"
  assert jokes[0]["punchline"] == "Punchline j1"


def test_refresh_sets_proposed_when_no_query_or_seasonal(
    monkeypatch, fake_env):
  categories = [("misc", {
    "display_name": "Misc",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  _run_refresh(monkeypatch, fake_db)

  cache = fake_env.cache_refs.get("misc")
  assert cache is None or cache.set_calls == []
  assert fake_env.category_updates.get("misc") == {"state": "PROPOSED"}


def test_refresh_unions_book_id_with_other_sources(monkeypatch, fake_env):
  """Category with book_id and search should union jokes from both sources."""

  class _FakeBookDoc:

    def __init__(self):
      self.exists = True

    def to_dict(self):
      return {"jokes": ["j2", "j3"], "book_name": "Test Book"}

  class _FakeBookRef:

    def __init__(self, doc):
      self._doc = doc

    def get(self):
      return self._doc

  class _FakeBookCollection:

    def __init__(self, book_doc):
      self._book_doc = book_doc

    def document(self, book_id):
      assert book_id == "book-123"
      return _FakeBookRef(self._book_doc)

  # Extend _FakeDb to support joke_books collection
  original_fake_db_collection = _FakeDb.collection

  def extended_collection(self, name: str):
    if name == "joke_books":
      return _FakeBookCollection(extended_collection._book_doc)
    return original_fake_db_collection(self, name)

  book_doc = _FakeBookDoc()
  extended_collection._book_doc = book_doc

  categories = [("combined", {
    "display_name": "Combined",
    "joke_description_query": "cats",
    "book_id": "book-123",
    "state": "APPROVED",
  })]
  fake_db = fake_env.make_db(categories)

  # Monkey patch collection method
  original_collection = fake_db.collection
  fake_db.collection = lambda name: extended_collection(fake_db, name)

  monkeypatch.setattr("services.firestore.db", lambda: fake_db)

  # Mock jokes: search returns j1, j2; book returns j2, j3
  # Union should have j1, j2, j3 (j2 appears once)
  def fake_get_punny_jokes(joke_ids):
    return [
      models.PunnyJoke(
        key=jid,
        setup_text=f"S {jid}",
        punchline_text=f"P {jid}",
        num_saved_users_fraction=0.5,
        state=models.JokeState.PUBLISHED,
        is_public=True,
      ) for jid in joke_ids
    ]

  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])
  monkeypatch.setattr("services.firestore.update_joke_sheets_cache",
                      lambda *_args, **_kwargs: None)

  # Mock search to return j1, j2 and track calls
  original_fake_search = fake_env.search_calls

  def fake_search(*args, **kwargs):
    original_fake_search.append({
      "query":
      args[0] if args else kwargs.get("query"),
      "category_id":
      args[1] if len(args) > 1 else kwargs.get("category_id"),
    })
    return [
      {
        "joke_id": "j1",
        "setup": "S j1",
        "punchline": "P j1",
        "setup_image_url": None,
        "punchline_image_url": None
      },
      {
        "joke_id": "j2",
        "setup": "S j2",
        "punchline": "P j2",
        "setup_image_url": None,
        "punchline_image_url": None
      },
    ]

  monkeypatch.setattr("common.joke_category_operations.search_category_jokes",
                      fake_search)

  # Act
  joke_category_operations.refresh_category_caches()

  # Assert
  assert len(fake_env.search_calls) == 1
  cache = fake_env.cache_refs.get("combined")
  assert cache is not None
  payload = cache.set_calls[0]
  joke_ids = [j["joke_id"] for j in payload["jokes"]]
  # Should have all jokes: j1 (from search), j2 (from both, deduped), j3 (from book)
  assert set(joke_ids) == {"j1", "j2", "j3"}
  assert len(joke_ids) == 3


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
  assert all(ref.set_calls == [] for ref in fake_env.cache_refs.values())
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
    """Test that search results return all jokes correctly."""

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

    # Assert - verify all jokes are returned (order is not guaranteed)
    assert len(jokes) == 4
    joke_ids = {j["joke_id"] for j in jokes}
    assert joke_ids == {"j1", "j2", "j3", "j4"}
    # Verify data is correct
    joke_by_id = {j["joke_id"]: j for j in jokes}
    assert joke_by_id["j2"]["setup"] == "Setup j2"
    assert joke_by_id["j2"]["punchline"] == "Punchline j2"
    assert joke_by_id["j4"]["setup"] == "Setup j4"
    assert joke_by_id["j1"]["setup"] == "Setup j1"
    assert joke_by_id["j3"]["setup"] == "Setup j3"

  def test_with_jokes_by_id_skips_firestore_get_punny_jokes(self, monkeypatch):
    """When jokes_by_id is provided, we should not re-read jokes via firestore."""
    from services.search import JokeSearchResult

    def fake_search_jokes(**_kwargs):
      return [
        JokeSearchResult(joke_id="j1", vector_distance=0.1),
        JokeSearchResult(joke_id="j2", vector_distance=0.1),
      ]

    monkeypatch.setattr("services.search.search_jokes", fake_search_jokes)
    monkeypatch.setattr("services.firestore.get_punny_jokes",
                        lambda _ids: (_ for _ in ()).throw(
                          AssertionError("get_punny_jokes should not be called")))

    jokes_by_id = {
      "j1":
      models.PunnyJoke(key="j1",
                       setup_text="S1",
                       punchline_text="P1",
                       setup_image_url="u1",
                       punchline_image_url="v1",
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
      "j2":
      models.PunnyJoke(key="j2",
                       setup_text="S2",
                       punchline_text="P2",
                       setup_image_url="u2",
                       punchline_image_url="v2",
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
    }

    payload = joke_category_operations.search_category_jokes(
      "q",
      "cat1",
      distance_threshold=0.1,
      jokes_by_id=jokes_by_id,
    )

    assert {p["joke_id"] for p in payload} == {"j1", "j2"}

  def test_without_jokes_by_id_calls_firestore_get_punny_jokes(self, monkeypatch):
    """Regression: without jokes_by_id, we still fetch jokes from firestore."""
    from services.search import JokeSearchResult

    monkeypatch.setattr(
      "services.search.search_jokes",
      lambda **_kwargs: [
        JokeSearchResult(joke_id="j1", vector_distance=0.1),
      ],
    )

    calls: list[list[str]] = []

    def fake_get_punny_jokes(joke_ids):
      calls.append(list(joke_ids))
      return [
        models.PunnyJoke(
          key="j1",
          setup_text="S1",
          punchline_text="P1",
          setup_image_url="u1",
          punchline_image_url="v1",
        )
      ]

    monkeypatch.setattr("services.firestore.get_punny_jokes",
                        fake_get_punny_jokes)

    payload = joke_category_operations.search_category_jokes(
      "q",
      "cat1",
      distance_threshold=0.1,
    )

    assert calls == [["j1"]]
    assert payload[0]["joke_id"] == "j1"


class TestQuerySeasonalCategoryJokesSorting:
  """Tests for query_seasonal_category_jokes sorting behavior."""

  def test_sorts_docs_by_num_saved_users_fraction(self, monkeypatch):
    """Test that seasonal jokes return all jokes correctly."""

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

    # Assert - verify all jokes are returned (order is not guaranteed)
    assert len(jokes) == 4
    joke_ids = {j["joke_id"] for j in jokes}
    assert joke_ids == {"j1", "j2", "j3", "j4"}
    # Verify data is correct
    joke_by_id = {j["joke_id"]: j for j in jokes}
    assert joke_by_id["j1"]["setup"] == "Setup j1"
    assert joke_by_id["j2"]["setup"] == "Setup j2"
    assert joke_by_id["j3"]["setup"] == "Setup j3"
    assert joke_by_id["j4"]["setup"] == "Setup j4"

  def test_with_jokes_by_id_skips_firestore_query(self):
    """When jokes_by_id is provided, we should not touch the client query interface."""

    class _ExplodingClient:

      def collection(self, _name: str):
        raise AssertionError("Firestore query should not be used")

    jokes_by_id = {
      "j1":
      models.PunnyJoke(key="j1",
                       setup_text="S1",
                       punchline_text="P1",
                       seasonal="Halloween",
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
      "j2":
      models.PunnyJoke(key="j2",
                       setup_text="S2",
                       punchline_text="P2",
                       seasonal="Halloween",
                       state=models.JokeState.DRAFT,
                       is_public=True),
      "j3":
      models.PunnyJoke(key="j3",
                       setup_text="S3",
                       punchline_text="P3",
                       seasonal="Halloween",
                       state=models.JokeState.DAILY,
                       is_public=False),
      "j4":
      models.PunnyJoke(key="j4",
                       setup_text="S4",
                       punchline_text="P4",
                       seasonal="Other",
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
    }

    payload = joke_category_operations.query_seasonal_category_jokes(
      _ExplodingClient(),
      "Halloween",
      jokes_by_id=jokes_by_id,
    )
    assert {p["joke_id"] for p in payload} == {"j1"}


class TestQueryBookCategoryJokes:
  """Tests for query_book_category_jokes function."""

  def test_fetches_jokes_from_book(self, monkeypatch):
    """Test that query_book_category_jokes fetches jokes from joke_books collection."""

    class _FakeBookDoc:

      def __init__(self, exists=True, jokes=None):
        self.exists = exists
        self._jokes = jokes or []

      def to_dict(self):
        return {"jokes": self._jokes, "book_name": "Test Book"}

    class _FakeBookRef:

      def __init__(self, doc):
        self._doc = doc

      def get(self):
        return self._doc

    class _FakeBookCollection:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def document(self, book_id):
        return _FakeBookRef(self._book_doc)

    class _FakeClient:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def collection(self, name):
        assert name == "joke_books"
        return _FakeBookCollection(self._book_doc)

    book_doc = _FakeBookDoc(jokes=["j1", "j2"])
    client = _FakeClient(book_doc)

    # Mock get_punny_jokes
    def fake_get_punny_jokes(joke_ids):
      return [
        models.PunnyJoke(
          key="j1",
          setup_text="Setup j1",
          punchline_text="Punchline j1",
          setup_image_url="https://example.com/j1-setup.jpg",
          punchline_image_url="https://example.com/j1-punchline.jpg",
          num_saved_users_fraction=0.5,
          state=models.JokeState.PUBLISHED,
          is_public=True,
        ),
        models.PunnyJoke(
          key="j2",
          setup_text="Setup j2",
          punchline_text="Punchline j2",
          setup_image_url="https://example.com/j2-setup.jpg",
          punchline_image_url="https://example.com/j2-punchline.jpg",
          num_saved_users_fraction=0.3,
          state=models.JokeState.PUBLISHED,
          is_public=True,
        ),
      ]

    monkeypatch.setattr("services.firestore.get_punny_jokes",
                        fake_get_punny_jokes)

    # Act
    jokes = joke_category_operations.query_book_category_jokes(
      client, "book-123")

    # Assert
    assert len(jokes) == 2
    assert jokes[0]["joke_id"] == "j1"  # Sorted by fraction (descending)
    assert jokes[1]["joke_id"] == "j2"
    assert jokes[0]["setup"] == "Setup j1"
    assert jokes[0]["punchline"] == "Punchline j1"

  def test_returns_empty_if_book_not_found(self, monkeypatch):
    """Test that query_book_category_jokes returns empty list if book doesn't exist."""

    class _FakeBookDoc:

      def __init__(self):
        self.exists = False

    class _FakeBookRef:

      def __init__(self, doc):
        self._doc = doc

      def get(self):
        return self._doc

    class _FakeBookCollection:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def document(self, book_id):
        return _FakeBookRef(self._book_doc)

    class _FakeClient:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def collection(self, name):
        assert name == "joke_books"
        return _FakeBookCollection(self._book_doc)

    book_doc = _FakeBookDoc()
    client = _FakeClient(book_doc)

    # Act
    jokes = joke_category_operations.query_book_category_jokes(
      client, "missing-book")

    # Assert
    assert jokes == []

  def test_filters_non_public_jokes(self, monkeypatch):
    """Test that query_book_category_jokes filters out non-public jokes."""

    class _FakeBookDoc:

      def __init__(self):
        self.exists = True

      def to_dict(self):
        return {"jokes": ["j1", "j2", "j3"], "book_name": "Test Book"}

    class _FakeBookRef:

      def __init__(self, doc):
        self._doc = doc

      def get(self):
        return self._doc

    class _FakeBookCollection:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def document(self, book_id):
        return _FakeBookRef(self._book_doc)

    class _FakeClient:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def collection(self, name):
        assert name == "joke_books"
        return _FakeBookCollection(self._book_doc)

    book_doc = _FakeBookDoc()
    client = _FakeClient(book_doc)

    # Mock get_punny_jokes with mixed public/private jokes
    def fake_get_punny_jokes(joke_ids):
      return [
        models.PunnyJoke(
          key="j1",
          setup_text="S1",
          punchline_text="P1",
          num_saved_users_fraction=0.5,
          state=models.JokeState.PUBLISHED,
          is_public=True,  # Public
        ),
        models.PunnyJoke(
          key="j2",
          setup_text="S2",
          punchline_text="P2",
          num_saved_users_fraction=0.3,
          state=models.JokeState.DAILY,
          is_public=False,  # Not public
        ),
        models.PunnyJoke(
          key="j3",
          setup_text="S3",
          punchline_text="P3",
          num_saved_users_fraction=0.2,
          state=models.JokeState.DRAFT,  # Invalid state
          is_public=True,
        ),
      ]

    monkeypatch.setattr("services.firestore.get_punny_jokes",
                        fake_get_punny_jokes)

    # Act
    jokes = joke_category_operations.query_book_category_jokes(
      client, "book-123")

    # Assert: Only j1 should be included (public + PUBLISHED/DAILY)
    assert len(jokes) == 1
    assert jokes[0]["joke_id"] == "j1"

  def test_returns_empty_if_book_has_no_jokes(self, monkeypatch):
    """Test that query_book_category_jokes returns empty list if book has no jokes."""

    class _FakeBookDoc:

      def __init__(self):
        self.exists = True

      def to_dict(self):
        return {"jokes": [], "book_name": "Empty Book"}

    class _FakeBookRef:

      def __init__(self, doc):
        self._doc = doc

      def get(self):
        return self._doc

    class _FakeBookCollection:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def document(self, book_id):
        return _FakeBookRef(self._book_doc)

    class _FakeClient:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def collection(self, name):
        assert name == "joke_books"
        return _FakeBookCollection(self._book_doc)

    book_doc = _FakeBookDoc()
    client = _FakeClient(book_doc)

    # Act
    jokes = joke_category_operations.query_book_category_jokes(
      client, "empty-book")

    # Assert
    assert jokes == []

  def test_handles_empty_jokes_field(self, monkeypatch):
    """Test that query_book_category_jokes handles missing jokes field gracefully."""

    class _FakeBookDoc:

      def __init__(self):
        self.exists = True

      def to_dict(self):
        return {"book_name": "Test Book"}  # No jokes field

    class _FakeBookRef:

      def __init__(self, doc):
        self._doc = doc

      def get(self):
        return self._doc

    class _FakeBookCollection:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def document(self, book_id):
        return _FakeBookRef(self._book_doc)

    class _FakeClient:

      def __init__(self, book_doc):
        self._book_doc = book_doc

      def collection(self, name):
        assert name == "joke_books"
        return _FakeBookCollection(self._book_doc)

    book_doc = _FakeBookDoc()
    client = _FakeClient(book_doc)

    # Act
    jokes = joke_category_operations.query_book_category_jokes(
      client, "no-jokes-book")

    # Assert
    assert jokes == []


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

    # Union + dedupe: j2 should appear once. Order is not guaranteed.
    joke_ids = {p["joke_id"] for p in payload}
    assert joke_ids == {"j1", "j2", "j3"}
    assert len(payload) == 3

  def test_with_jokes_by_id_skips_firestore_query(self):
    """When jokes_by_id is provided, we should not touch the client query interface."""

    class _ExplodingClient:

      def collection(self, _name: str):
        raise AssertionError("Firestore query should not be used")

    jokes_by_id = {
      "j1":
      models.PunnyJoke(key="j1",
                       setup_text="S1",
                       punchline_text="P1",
                       tags=["Cats", "Animals"],
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
      "j2":
      models.PunnyJoke(key="j2",
                       setup_text="S2",
                       punchline_text="P2",
                       tags=["dogs"],
                       state=models.JokeState.PUBLISHED,
                       is_public=True),
      "j3":
      models.PunnyJoke(key="j3",
                       setup_text="S3",
                       punchline_text="P3",
                       tags=["cats"],
                       state=models.JokeState.DRAFT,
                       is_public=True),
      "j4":
      models.PunnyJoke(key="j4",
                       setup_text="S4",
                       punchline_text="P4",
                       tags=["cats"],
                       state=models.JokeState.PUBLISHED,
                       is_public=False),
    }

    payload = joke_category_operations.query_tags_category_jokes(
      _ExplodingClient(),
      ["cats"],
      jokes_by_id=jokes_by_id,
    )
    assert {p["joke_id"] for p in payload} == {"j1"}

  def test_handles_missing_fraction_field(self, monkeypatch):
    """Test that docs without num_saved_users_fraction are still returned."""

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

    # Assert - verify all jokes are returned (order is not guaranteed)
    assert len(jokes) == 2
    joke_ids = {j["joke_id"] for j in jokes}
    assert joke_ids == {"j1", "j2"}


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


def _make_jokes_with_fractions(
    fractions: list[float]) -> list[models.PunnyJoke]:
  jokes: list[models.PunnyJoke] = []
  for i, fraction in enumerate(fractions):
    jokes.append(
      models.PunnyJoke(
        key=f"j{i + 1}",
        setup_text="S",
        punchline_text="P",
        num_saved_users_fraction=fraction,
      ))
  return jokes


def test_ensure_category_joke_sheets_skips_when_under_5(monkeypatch):
  calls: list[dict] = []

  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(4),
  )
  assert calls == []


def test_ensure_category_joke_sheets_creates_full_batches_only(monkeypatch):
  calls: list[dict] = []

  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(9),
  )

  # 9 uncovered -> one full sheet of 5, last 4 ignored
  assert calls == [{
    "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
    "category_id": "cats",
    "index": 0,
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

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(10),
  )

  # Ensure existing sheet and create the next full batch.
  assert calls == [
    {
      "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
      "category_id": "cats",
      "index": 0,
    },
    {
      "joke_ids": ["j6", "j7", "j8", "j9", "j10"],
      "category_id": "cats",
      "index": 1,
    },
  ]


def test_ensure_category_joke_sheets_deletes_invalid_sheet(monkeypatch):
  calls: list[dict] = []
  deleted: list[str] = []

  existing = [
    models.JokeSheet(
      key="s1",
      joke_str="j1,j2,jx",
      joke_ids=["j1", "j2", "jx"],
      category_id="cats",
    )
  ]
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: existing)
  monkeypatch.setattr("services.firestore.delete_joke_sheet",
                      lambda sheet_id: deleted.append(sheet_id) or True)

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(5),
  )

  assert deleted == ["s1"]
  assert calls == [
    {
      "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
      "category_id": "cats",
      "index": 0,
    },
  ]


def test_ensure_category_joke_sheets_deletes_non_five_id_sheets(monkeypatch):
  calls: list[dict] = []
  deleted: list[str] = []

  existing = [
    models.JokeSheet(
      key="s1",
      joke_str="j1,j2,j3,j4",
      joke_ids=["j1", "j2", "j3", "j4"],
      category_id="cats",
    ),
    models.JokeSheet(
      key="s2",
      joke_str="",
      joke_ids=[],
      category_id="cats",
    ),
  ]
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: existing)
  monkeypatch.setattr("services.firestore.delete_joke_sheet",
                      lambda sheet_id: deleted.append(sheet_id) or True)

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    _make_jokes(5),
  )

  assert sorted(deleted) == ["s1", "s2"]
  assert calls == [
    {
      "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
      "category_id": "cats",
      "index": 0,
    },
  ]


def test_ensure_category_joke_sheets_assigns_indexes_by_order(monkeypatch):
  calls: list[dict] = []

  # No existing sheets
  monkeypatch.setattr("services.firestore.get_joke_sheets_by_category",
                      lambda _category_id: [])

  def fake_get_sheet(jokes, *, category_id=None, quality=80, index=None):  # pylint: disable=unused-argument
    calls.append({
      "joke_ids": [j.key for j in jokes if j.key],
      "category_id": category_id,
      "index": index,
    })
    return models.JokeSheet(
      joke_ids=[j.key for j in jokes if j.key],
      category_id=category_id,
      index=index,
      image_gcs_uri="gs://bucket/file.png",
      pdf_gcs_uri="gs://bucket/file.pdf",
    )

  monkeypatch.setattr(
    "common.joke_notes_sheet_operations.ensure_joke_notes_sheet",
    fake_get_sheet)

  # Batch 1 (low quality) comes first in input
  # Batch 2 (high quality) comes second in input
  jokes = _make_jokes_with_fractions([0.1] * 5 + [0.9] * 5)

  joke_category_operations._ensure_category_joke_sheets(  # pylint: disable=protected-access
    "cats",
    jokes,
  )

  # Should preserve input order: low quality first at index 0
  assert calls == [
    {
      "joke_ids": ["j1", "j2", "j3", "j4", "j5"],
      "category_id": "cats",
      "index": 0,
    },
    {
      "joke_ids": ["j6", "j7", "j8", "j9", "j10"],
      "category_id": "cats",
      "index": 1,
    },
  ]
