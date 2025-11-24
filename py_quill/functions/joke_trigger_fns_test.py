"""Tests for joke_trigger_fns module."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, Mock

import pytest
from common import joke_operations, models
from functions import joke_trigger_fns
from google.cloud.firestore_v1.vector import Vector


class TestOnJokeWrite:
  """Tests for the on_joke_write trigger."""

  @pytest.fixture(name='mock_get_joke_embedding')
  def mock_get_joke_embedding_fixture(self, monkeypatch):
    mock_embedding_fn = Mock(return_value=(Vector([1.0, 2.0, 3.0]),
                                           models.GenerationMetadata()))
    monkeypatch.setattr(joke_trigger_fns, "_get_joke_embedding",
                        mock_embedding_fn)
    return mock_embedding_fn

  @pytest.fixture(name='mock_firestore_service')
  def mock_firestore_service_fixture(self, monkeypatch):
    mock_firestore = Mock()
    mock_firestore.update_punny_joke = Mock()

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc_ref = MagicMock()
    mock_sub_collection = MagicMock()
    mock_sub_doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = False
    snapshot.to_dict.return_value = None

    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    mock_doc_ref.collection.return_value = mock_sub_collection
    mock_sub_collection.document.return_value = mock_sub_doc_ref
    mock_sub_doc_ref.get.return_value = snapshot

    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)
    mock_firestore.db = lambda: mock_db

    return mock_firestore

  def _create_event(self, before, after):
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()
    event.data.before = MagicMock() if before is not None else None
    event.data.after = MagicMock() if after is not None else None
    if before is not None:
      event.data.before.to_dict.return_value = before
    if after is not None:
      event.data.after.to_dict.return_value = after
    return event

  def test_new_joke_initializes_recent_counters_and_popularity(
      self, mock_get_joke_embedding, mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=4,
      num_shared_users=1,
      num_viewed_users=5,
      num_saved_users_fraction=0.0,
      num_shared_users_fraction=0.0,
    ).to_dict()

    event = self._create_event(before=None, after=after_joke)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    call_args = mock_firestore_service.update_punny_joke.call_args[0]
    update_data = call_args[1]
    assert update_data["num_viewed_users_recent"] == pytest.approx(5.0)
    assert update_data["num_saved_users_recent"] == pytest.approx(4.0)
    assert update_data["num_shared_users_recent"] == pytest.approx(1.0)
    assert update_data["popularity_score_recent"] == pytest.approx(25.0 / 5.0)
    assert "zzz_joke_text_embedding" in update_data

  def test_existing_recent_counters_coerced_to_float(self,
                                                     mock_get_joke_embedding,
                                                     mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=2,
      num_shared_users=1,
      num_viewed_users=4,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.25,
    ).to_dict()
    after_joke.update({
      "num_viewed_users_recent": 4,
      "num_saved_users_recent": 2,
      "num_shared_users_recent": 1,
    })

    event = self._create_event(before=after_joke, after=after_joke)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    update_data = mock_firestore_service.update_punny_joke.call_args[0][1]
    assert update_data["num_viewed_users_recent"] == pytest.approx(4.0)
    assert update_data["num_saved_users_recent"] == pytest.approx(2.0)
    assert update_data["num_shared_users_recent"] == pytest.approx(1.0)

  def test_draft_joke_skips_embedding(self, mock_get_joke_embedding,
                                      mock_firestore_service):
    draft_joke = models.PunnyJoke(key="joke1",
                                  setup_text="s",
                                  punchline_text="p",
                                  state=models.JokeState.DRAFT).to_dict()
    event = self._create_event(before=None, after=draft_joke)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    mock_get_joke_embedding.assert_not_called()
    mock_firestore_service.update_punny_joke.assert_not_called()

  def test_zero_views_keeps_fractions_unset(self, mock_get_joke_embedding,
                                            mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=3,
      num_shared_users=1,
      num_viewed_users=0,
      num_saved_users_fraction=0.0,
      num_shared_users_fraction=0.0,
    ).to_dict()

    event = self._create_event(before=None, after=after_joke)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    update_data = mock_firestore_service.update_punny_joke.call_args[0][1]
    assert "num_saved_users_fraction" not in update_data
    assert "num_shared_users_fraction" not in update_data

  def test_low_view_count_resets_fractions_to_zero(self,
                                                   mock_get_joke_embedding,
                                                   mock_firestore_service):
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="s",
      punchline_text="p",
      num_saved_users=30,
      num_shared_users=10,
      num_viewed_users=joke_trigger_fns.MIN_VIEWS_FOR_FRACTIONS - 1,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.2,
    ).to_dict()

    event = self._create_event(before=None, after=after_joke)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    update_data = mock_firestore_service.update_punny_joke.call_args[0][1]
    assert update_data["num_saved_users_fraction"] == pytest.approx(0.0)
    assert update_data["num_shared_users_fraction"] == pytest.approx(0.0)


class TestOnJokeWriteSearchSync:
  """Tests for syncing jokes to the joke_search collection via on_joke_write."""

  def _create_event(self, before, after):
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()
    event.data.before = MagicMock() if before else None
    event.data.after = MagicMock() if after else None
    if before:
      event.data.before.to_dict.return_value = before
    if after:
      event.data.after.to_dict.return_value = after
    return event

  def _setup_search_mocks(self, monkeypatch):
    mock_db = MagicMock()
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()

    def mock_collection(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_search_collection.document.return_value = mock_search_doc_ref

    search_doc_state = {"doc": None}

    def mock_get():
      snapshot = MagicMock()
      if search_doc_state["doc"] is None:
        snapshot.exists = False
        snapshot.to_dict.return_value = None
      else:
        snapshot.exists = True
        snapshot.to_dict.return_value = search_doc_state["doc"]
      return snapshot

    def mock_set(data, merge=False):
      if not merge or search_doc_state["doc"] is None:
        search_doc_state["doc"] = {}
      search_doc_state["doc"].update(data)

    def mock_delete():
      search_doc_state["doc"] = None

    mock_search_doc_ref.get.side_effect = mock_get
    mock_search_doc_ref.set.side_effect = mock_set
    mock_search_doc_ref.delete.side_effect = mock_delete

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)

    return mock_search_doc_ref, search_doc_state

  def test_calls_sync_joke_to_search_collection(self, monkeypatch):
    """Test that on_joke_write calls sync_joke_to_search_collection."""
    _, search_doc_state = self._setup_search_mocks(monkeypatch)

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    after_joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      public_timestamp=joke_date,
      is_public=True,
    )

    event = self._create_event(before=None, after=after_joke.to_dict())

    mock_embedding = Mock(return_value=(Vector([1.0]),
                                        models.GenerationMetadata()))
    monkeypatch.setattr(joke_trigger_fns, "_get_joke_embedding",
                        mock_embedding)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify sync was called (search doc was created)
    assert search_doc_state["doc"] is not None

  def test_deletes_search_doc_when_joke_deleted(self, monkeypatch):
    """Test that search document is deleted when joke is deleted."""
    mock_search_doc_ref, search_doc_state = self._setup_search_mocks(
      monkeypatch)

    # Set up existing search doc
    search_doc_state["doc"] = {
      "text_embedding": Vector([1.0, 2.0, 3.0]),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify delete was called
    mock_search_doc_ref.delete.assert_called_once()
    # Verify search doc was cleared
    assert search_doc_state["doc"] is None

  def test_deletes_search_doc_when_not_exists(self, monkeypatch):
    """Test that deletion handles case when search doc doesn't exist."""
    mock_search_doc_ref, search_doc_state = self._setup_search_mocks(
      monkeypatch)

    # No existing search doc
    search_doc_state["doc"] = None

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify delete was not called (since doc doesn't exist)
    mock_search_doc_ref.delete.assert_not_called()


class TestOnJokeWriteSubcollectionDeletion:
  """Tests for subcollection deletion when jokes are deleted."""

  def _create_event(self, before, after):
    event = MagicMock()
    event.params = {"joke_id": "joke1"}
    event.data = MagicMock()
    event.data.before = MagicMock() if before is not None else None
    event.data.after = MagicMock() if after is not None else None
    if before is not None:
      event.data.before.to_dict.return_value = before
    if after is not None:
      event.data.after.to_dict.return_value = after
    return event

  def _setup_subcollection_mocks(self, monkeypatch):
    """Set up mocks for subcollection deletion testing."""
    mock_db = MagicMock()
    mock_jokes_collection = MagicMock()
    mock_joke_doc_ref = MagicMock()
    mock_metadata_collection = MagicMock()
    mock_operations_doc_ref = MagicMock()
    mock_metadata_doc_ref = MagicMock()

    # Set up the jokes collection structure
    def mock_collection(collection_name):
      if collection_name == "jokes":
        return mock_jokes_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_jokes_collection.document.return_value = mock_joke_doc_ref

    # Set up subcollections
    def mock_joke_collections():
      """Return an iterator of subcollections."""
      return iter([mock_metadata_collection])

    mock_joke_doc_ref.collections.return_value = mock_joke_collections()

    # Set up metadata subcollection documents
    mock_metadata_collection.id = "metadata"
    mock_metadata_collection.document.return_value = mock_operations_doc_ref
    mock_metadata_collection.limit.return_value.stream.return_value = iter([
      MagicMock(reference=mock_operations_doc_ref),
      MagicMock(reference=mock_metadata_doc_ref),
    ])

    # Set up nested subcollections (empty for these docs)
    mock_operations_doc_ref.collections.return_value = iter([])
    mock_metadata_doc_ref.collections.return_value = iter([])

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)

    # Mock search deletion
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()
    mock_search_snapshot = MagicMock()
    mock_search_snapshot.exists = False

    def mock_search_collection_fn(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return mock_collection(collection_name)

    mock_db.collection.side_effect = mock_search_collection_fn
    mock_search_collection.document.return_value = mock_search_doc_ref
    mock_search_doc_ref.get.return_value = mock_search_snapshot

    return (mock_joke_doc_ref, mock_metadata_collection,
            mock_operations_doc_ref, mock_metadata_doc_ref)

  def test_deletes_subcollections_when_joke_deleted(self, monkeypatch):
    """Test that subcollections are deleted when joke is deleted."""
    (mock_joke_doc_ref, mock_metadata_collection, mock_operations_doc_ref,
     mock_metadata_doc_ref) = self._setup_subcollection_mocks(monkeypatch)

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify subcollections were queried
    mock_joke_doc_ref.collections.assert_called_once()

    # Verify documents in metadata subcollection were deleted
    mock_operations_doc_ref.delete.assert_called_once()
    mock_metadata_doc_ref.delete.assert_called_once()

  def test_deletes_nested_subcollections(self, monkeypatch):
    """Test that nested subcollections are recursively deleted."""
    mock_db = MagicMock()
    mock_jokes_collection = MagicMock()
    mock_joke_doc_ref = MagicMock()
    mock_metadata_collection = MagicMock()
    mock_operations_doc_ref = MagicMock()
    mock_nested_collection = MagicMock()
    mock_nested_doc_ref = MagicMock()

    def mock_collection(collection_name):
      if collection_name == "jokes":
        return mock_jokes_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_jokes_collection.document.return_value = mock_joke_doc_ref

    # Set up subcollections
    def mock_joke_collections():
      return iter([mock_metadata_collection])

    mock_joke_doc_ref.collections.return_value = mock_joke_collections()

    # Set up metadata subcollection with one document
    mock_metadata_collection.id = "metadata"
    mock_metadata_collection.limit.return_value.stream.return_value = iter([
      MagicMock(reference=mock_operations_doc_ref),
    ])

    # Set up nested subcollection under operations doc
    def mock_operations_collections():
      return iter([mock_nested_collection])

    mock_operations_doc_ref.collections.return_value = mock_operations_collections()

    # Set up nested collection documents
    mock_nested_collection.id = "nested"
    mock_nested_collection.limit.return_value.stream.return_value = iter([
      MagicMock(reference=mock_nested_doc_ref),
    ])
    mock_nested_doc_ref.collections.return_value = iter([])

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)

    # Mock search deletion
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()
    mock_search_snapshot = MagicMock()
    mock_search_snapshot.exists = False

    def mock_search_collection_fn(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return mock_collection(collection_name)

    mock_db.collection.side_effect = mock_search_collection_fn
    mock_search_collection.document.return_value = mock_search_doc_ref
    mock_search_doc_ref.get.return_value = mock_search_snapshot

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify nested subcollection was queried
    mock_operations_doc_ref.collections.assert_called_once()
    mock_nested_collection.limit.assert_called()

    # Verify nested document was deleted
    mock_nested_doc_ref.delete.assert_called_once()

    # Verify parent document was deleted
    mock_operations_doc_ref.delete.assert_called_once()

  def test_handles_empty_subcollections(self, monkeypatch):
    """Test that deletion handles jokes with no subcollections."""
    mock_db = MagicMock()
    mock_jokes_collection = MagicMock()
    mock_joke_doc_ref = MagicMock()

    def mock_collection(collection_name):
      if collection_name == "jokes":
        return mock_jokes_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_jokes_collection.document.return_value = mock_joke_doc_ref

    # No subcollections
    mock_joke_doc_ref.collections.return_value = iter([])

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)

    # Mock search deletion
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()
    mock_search_snapshot = MagicMock()
    mock_search_snapshot.exists = False

    def mock_search_collection_fn(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return mock_collection(collection_name)

    mock_db.collection.side_effect = mock_search_collection_fn
    mock_search_collection.document.return_value = mock_search_doc_ref
    mock_search_doc_ref.get.return_value = mock_search_snapshot

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    # Should not raise an error
    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify subcollections were queried
    mock_joke_doc_ref.collections.assert_called_once()

  def test_handles_missing_joke_id(self, monkeypatch):
    """Test that deletion handles missing joke_id gracefully."""
    mock_db = MagicMock()
    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)

    # Create event with no joke_id
    event = MagicMock()
    event.params = {}
    event.data = MagicMock()
    event.data.after = None

    # Should not raise an error
    joke_trigger_fns.on_joke_write.__wrapped__(event)

  def test_handles_large_subcollections_with_batching(self, monkeypatch):
    """Test that large subcollections are deleted in batches."""
    mock_db = MagicMock()
    mock_jokes_collection = MagicMock()
    mock_joke_doc_ref = MagicMock()
    mock_metadata_collection = MagicMock()

    def mock_collection(collection_name):
      if collection_name == "jokes":
        return mock_jokes_collection
      return MagicMock()

    mock_db.collection.side_effect = mock_collection
    mock_jokes_collection.document.return_value = mock_joke_doc_ref

    # Set up subcollections
    def mock_joke_collections():
      return iter([mock_metadata_collection])

    mock_joke_doc_ref.collections.return_value = mock_joke_collections()

    # Create 150 documents (more than batch size of 100)
    mock_docs = [
      MagicMock(reference=MagicMock()) for _ in range(150)
    ]
    for doc in mock_docs:
      doc.reference.collections.return_value = iter([])

    # First batch returns 100 docs, second batch returns 50 docs
    def mock_stream():
      first_batch = iter(mock_docs[:100])
      second_batch = iter(mock_docs[100:])
      return iter([first_batch, second_batch])

    mock_limit = MagicMock()
    mock_limit.stream.side_effect = [
      iter(mock_docs[:100]),
      iter(mock_docs[100:]),
    ]
    mock_metadata_collection.limit.return_value = mock_limit
    mock_metadata_collection.id = "metadata"

    mock_firestore = Mock()
    mock_firestore.db = lambda: mock_db
    mock_firestore.update_punny_joke = Mock()
    monkeypatch.setattr(joke_trigger_fns, "firestore", mock_firestore)
    monkeypatch.setattr(joke_operations, "firestore", mock_firestore)

    # Mock search deletion
    mock_search_collection = MagicMock()
    mock_search_doc_ref = MagicMock()
    mock_search_snapshot = MagicMock()
    mock_search_snapshot.exists = False

    def mock_search_collection_fn(collection_name):
      if collection_name == "joke_search":
        return mock_search_collection
      return mock_collection(collection_name)

    mock_db.collection.side_effect = mock_search_collection_fn
    mock_search_collection.document.return_value = mock_search_doc_ref
    mock_search_doc_ref.get.return_value = mock_search_snapshot

    # Create event with no after data (deletion)
    event = self._create_event(before=None, after=None)

    joke_trigger_fns.on_joke_write.__wrapped__(event)

    # Verify limit was called twice (for batching)
    assert mock_metadata_collection.limit.call_count >= 1

    # Verify all documents were deleted
    for doc in mock_docs:
      doc.reference.delete.assert_called_once()


class TestOnJokeCategoryWrite:
  """Tests for the on_joke_category_write cloud function."""

  def _create_event(self, before_data, after_data, category_id="cat1"):
    event = MagicMock()
    event.params = {"category_id": category_id}
    event.data = MagicMock()
    event.data.before = MagicMock() if before_data is not None else None
    event.data.after = MagicMock() if after_data is not None else None
    if before_data is not None:
      event.data.before.to_dict.return_value = before_data
    if after_data is not None:
      event.data.after.to_dict.return_value = after_data
    return event

  def test_new_doc_with_image_description_generates_and_updates(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to not exist (new document)
    mock_doc.exists = False
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None,
                               after_data={"image_description": "desc"})

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once(
    )  # Should call get() to check if doc exists
    mock_doc.set.assert_called_once()  # Should call set() for new document
    args = mock_doc.set.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [mock_image.url]

  def test_existing_doc_with_image_description_generates_and_updates(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/new_image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to exist with existing data
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
      "image_url": "http://example.com/old_image.png",
      "all_image_urls": ["http://example.com/old_image.png"]
    }
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once(
    )  # Should call get() to check if doc exists
    mock_doc.update.assert_called_once(
    )  # Should call update() for existing document
    args = mock_doc.update.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [
      "http://example.com/old_image.png", "http://example.com/new_image.png"
    ]

  def test_existing_doc_without_all_image_urls_initializes_it(
      self, monkeypatch):
    # Arrange
    mock_image = MagicMock()
    mock_image.url = "http://example.com/new_image.png"
    mock_generate = MagicMock(return_value=mock_image)
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_generate)

    mock_db = MagicMock()
    mock_doc = MagicMock()
    # Mock the document to exist but without all_image_urls field
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
      "image_url": "http://example.com/old_image.png"
      # No all_image_urls field
    }
    mock_doc.get.return_value = mock_doc  # get() returns the document itself
    mock_coll = MagicMock(return_value=MagicMock(document=MagicMock(
      return_value=mock_doc)))
    mock_db.collection = mock_coll
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "old_desc"},
                               after_data={"image_description": "new_desc"})

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_called_once()
    mock_doc.get.assert_called_once()
    mock_doc.update.assert_called_once()
    args = mock_doc.update.call_args[0]
    assert args[0]["image_url"] == mock_image.url
    assert args[0]["all_image_urls"] == [
      "http://example.com/old_image.png", "http://example.com/new_image.png"
    ]

  def test_description_unchanged_does_nothing(self, monkeypatch):
    # Arrange
    mock_generate = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data={"image_description": "same"},
                               after_data={"image_description": "same"})

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()

  def test_missing_image_description_skips(self, monkeypatch):
    # Arrange
    mock_generate = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_generate)
    mock_db = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    event = self._create_event(before_data=None, after_data={})

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    mock_generate.assert_not_called()
    mock_db.collection.assert_not_called()

  @pytest.mark.parametrize(
    "before_data,after_data,should_refresh",
    [
      # Query change - should refresh
      ({
        "joke_description_query": "cats"
      }, {
        "joke_description_query": "dogs",
        "state": "APPROVED"
      }, True),
      # Seasonal name change - should refresh
      ({
        "seasonal_name": "Halloween"
      }, {
        "seasonal_name": "Christmas",
        "state": "APPROVED"
      }, True),
      # New doc with query - should refresh
      (None, {
        "joke_description_query": "animals",
        "state": "APPROVED"
      }, True),
      # Query and seasonal unchanged - should not refresh
      ({
        "joke_description_query": "cats",
        "seasonal_name": None
      }, {
        "joke_description_query": "cats",
        "seasonal_name": None,
        "image_description": "new description"
      }, False),
    ])
  def test_cache_refresh_behavior(self, monkeypatch, before_data, after_data,
                                  should_refresh):
    """Test that cache is refreshed when query/seasonal changes, not otherwise."""
    # Arrange
    mock_image_gen = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.image_generation,
                        "generate_pun_image", mock_image_gen)

    mock_db = MagicMock()
    monkeypatch.setattr(joke_trigger_fns.firestore, "db",
                        MagicMock(return_value=mock_db))

    # Mock the cache refresh helper
    mock_refresh = MagicMock(return_value="updated")
    monkeypatch.setattr(
      "common.joke_category_operations.refresh_single_category_cache",
      mock_refresh)

    event = self._create_event(before_data=before_data, after_data=after_data)

    # Act
    joke_trigger_fns.on_joke_category_write.__wrapped__(event)

    # Assert
    if should_refresh:
      mock_refresh.assert_called_once_with("cat1", event.data.after.to_dict())
    else:
      mock_refresh.assert_not_called()
