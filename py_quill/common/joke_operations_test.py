"""Tests for the joke_operations module."""
import datetime
from unittest.mock import MagicMock, Mock

import pytest
from common import joke_operations, models
from google.cloud.firestore_v1.vector import Vector


@pytest.fixture(name='mock_firestore')
def mock_firestore_fixture(monkeypatch):
  """Fixture that mocks the firestore service."""
  mock_firestore = Mock()
  monkeypatch.setattr(joke_operations, 'firestore', mock_firestore)
  return mock_firestore


@pytest.fixture(name='mock_image_client')
def mock_image_client_fixture(monkeypatch):
  """Fixture that mocks the image_client service."""
  mock_image_client = Mock()
  monkeypatch.setattr(joke_operations, 'image_client', mock_image_client)
  return mock_image_client


@pytest.fixture(name='mock_cloud_storage')
def mock_cloud_storage_fixture(monkeypatch):
  """Fixture that mocks the cloud_storage service."""
  mock_cloud_storage = Mock()
  monkeypatch.setattr(joke_operations, 'cloud_storage', mock_cloud_storage)
  return mock_cloud_storage


def test_upscale_joke_success(mock_firestore, mock_image_client,
                              mock_cloud_storage):
  """Test that upscale_joke successfully upscales a joke's images."""
  # Arrange
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url="https://storage.googleapis.com/example/punchline.png",
    generation_metadata=models.GenerationMetadata(),
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  mock_upscaled_setup_image = models.Image(
    url_upscaled="http://example.com/new_setup.png",
    generation_metadata=models.GenerationMetadata())
  mock_upscaled_punchline_image = models.Image(
    url_upscaled="http://example.com/new_punchline.png",
    generation_metadata=models.GenerationMetadata())
  mock_client_instance.upscale_image.side_effect = [
    mock_upscaled_setup_image, mock_upscaled_punchline_image
  ]

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://example/setup.png", "gs://example/punchline.png"
  ]

  # Act
  upscaled_joke = joke_operations.upscale_joke("joke1")

  # Assert
  mock_firestore.get_punny_joke.assert_called_once_with("joke1")
  assert mock_client_instance.upscale_image.call_count == 2
  assert upscaled_joke.setup_image_url_upscaled == "http://example.com/new_setup.png"
  assert upscaled_joke.punchline_image_url_upscaled == "http://example.com/new_punchline.png"


def test_upscale_joke_idempotent(mock_firestore, mock_image_client):
  """Test that upscale_joke is idempotent and returns immediately if images are already upscaled."""
  # Arrange
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url_upscaled="http://example.com/existing_setup.png",
    punchline_image_url_upscaled="http://example.com/existing_punchline.png",
  )
  mock_firestore.get_punny_joke.return_value = mock_joke
  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  # Act
  upscaled_joke = joke_operations.upscale_joke("joke1")

  # Assert
  mock_firestore.get_punny_joke.assert_called_once_with("joke1")
  mock_image_client.get_client.assert_not_called()
  assert upscaled_joke.setup_image_url_upscaled == "http://example.com/existing_setup.png"
  assert upscaled_joke.punchline_image_url_upscaled == "http://example.com/existing_punchline.png"


def test_upscale_joke_not_found(mock_firestore):
  """Test that upscale_joke raises ValueError if joke is not found."""
  # Arrange
  mock_firestore.get_punny_joke.return_value = None

  # Act & Assert
  with pytest.raises(ValueError, match="Joke not found: joke1"):
    joke_operations.upscale_joke("joke1")


def test_upscale_joke_only_one_image(mock_firestore, mock_image_client,
                                     mock_cloud_storage):
  """Test that upscale_joke only upscales the missing image."""
  # Arrange
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url_upscaled="http://example.com/existing_punchline.png",
    generation_metadata=models.GenerationMetadata(),
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  mock_upscaled_setup_image = models.Image(
    url_upscaled="http://example.com/new_setup.png",
    generation_metadata=models.GenerationMetadata())
  mock_client_instance.upscale_image.return_value = mock_upscaled_setup_image

  mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

  # Act
  upscaled_joke = joke_operations.upscale_joke("joke1")

  # Assert
  mock_firestore.get_punny_joke.assert_called_once_with("joke1")
  mock_client_instance.upscale_image.assert_called_once()
  assert upscaled_joke.setup_image_url_upscaled == "http://example.com/new_setup.png"
  assert upscaled_joke.punchline_image_url_upscaled == "http://example.com/existing_punchline.png"


def test_upscale_joke_missing_one_image_url(mock_firestore, mock_image_client,
                                            mock_cloud_storage):
  """Test that upscale_joke only upscales the available image if one is missing."""
  # Arrange
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url=None,  # Missing punchline image
    generation_metadata=models.GenerationMetadata(),
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  mock_upscaled_setup_image = models.Image(
    url_upscaled="http://example.com/new_setup.png",
    generation_metadata=models.GenerationMetadata())
  mock_client_instance.upscale_image.return_value = mock_upscaled_setup_image

  mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

  # Act
  upscaled_joke = joke_operations.upscale_joke("joke1")

  # Assert
  mock_firestore.get_punny_joke.assert_called_once_with("joke1")
  mock_client_instance.upscale_image.assert_called_once()
  assert upscaled_joke.setup_image_url_upscaled == "http://example.com/new_setup.png"
  assert upscaled_joke.punchline_image_url_upscaled is None


def test_upscale_joke_updates_metadata(mock_firestore, mock_image_client,
                                       mock_cloud_storage):
  """Test that upscale_joke correctly updates the generation_metadata."""
  # Arrange

  initial_metadata = models.GenerationMetadata()
  initial_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="initial_model"))

  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url=None,
    generation_metadata=initial_metadata,
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  upscale_metadata = models.GenerationMetadata()
  upscale_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="upscale_model"))
  mock_upscaled_image = models.Image(
    url_upscaled="http://example.com/new_setup.png",
    generation_metadata=upscale_metadata)
  mock_client_instance.upscale_image.return_value = mock_upscaled_image

  mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

  # Act
  upscaled_joke = joke_operations.upscale_joke("joke1")

  # Assert
  assert len(upscaled_joke.generation_metadata.generations) == 2
  assert upscaled_joke.generation_metadata.generations[
    0].model_name == "initial_model"
  assert upscaled_joke.generation_metadata.generations[
    1].model_name == "upscale_model"


@pytest.fixture(name='mock_search_collection')
def mock_search_collection_fixture(monkeypatch, mock_firestore):
  """Fixture that mocks the joke_search collection for sync_joke_to_search_collection tests."""
  mock_db = MagicMock()
  mock_search_collection = MagicMock()
  mock_search_doc_ref = MagicMock()

  def mock_collection(collection_name):
    if collection_name == "joke_search":
      return mock_search_collection
    return MagicMock()

  mock_db.collection.side_effect = mock_collection
  mock_search_collection.document.return_value = mock_search_doc_ref
  mock_firestore.db = lambda: mock_db

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

  mock_search_doc_ref.get.side_effect = mock_get
  mock_search_doc_ref.set.side_effect = mock_set

  return mock_search_doc_ref, search_doc_state


class TestSyncJokeToSearchCollection:
  """Tests for sync_joke_to_search_collection function."""

  def test_creates_new_search_doc_with_all_fields(self, mock_search_collection,
                                                  mock_firestore):
    """Test that sync creates a new search doc with all joke fields."""
    _, search_doc_state = mock_search_collection

    joke_date = datetime.datetime.now(datetime.timezone.utc)
    new_embedding = Vector([1.0, 2.0, 3.0])
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      public_timestamp=joke_date,
      is_public=True,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.3,
      popularity_score=64.0,
    )

    joke_operations.sync_joke_to_search_collection(joke, new_embedding)

    synced = search_doc_state["doc"]
    assert synced is not None
    assert synced["text_embedding"] == new_embedding
    assert synced["state"] == models.JokeState.PUBLISHED.value
    assert synced["is_public"] is True
    assert synced["public_timestamp"] == joke_date
    assert synced["num_saved_users_fraction"] == 0.5
    assert synced["num_shared_users_fraction"] == 0.3
    assert synced["popularity_score"] == 64.0

  def test_creates_new_search_doc_with_partial_fields(self,
                                                      mock_search_collection,
                                                      mock_firestore):
    """Test that sync creates search doc even when some fields are None."""
    _, search_doc_state = mock_search_collection

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.DRAFT,
      is_public=False,
      num_saved_users_fraction=None,
      num_shared_users_fraction=None,
      popularity_score=None,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced is not None
    assert synced["state"] == models.JokeState.DRAFT.value
    assert synced["is_public"] is False
    assert "num_saved_users_fraction" not in synced
    assert "num_shared_users_fraction" not in synced
    assert "popularity_score" not in synced

  def test_updates_only_changed_fields(self, mock_search_collection,
                                       mock_firestore):
    """Test that only changed fields are updated in existing search doc."""
    _, search_doc_state = mock_search_collection

    # Set up existing search doc
    existing_date = datetime.datetime.now(datetime.timezone.utc)
    search_doc_state["doc"] = {
      "text_embedding": Vector([1.0, 2.0, 3.0]),
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "public_timestamp": existing_date,
      "num_saved_users_fraction": 0.5,
      "num_shared_users_fraction": 0.3,
      "popularity_score": 10.5,
    }

    new_date = datetime.datetime.now(datetime.timezone.utc)
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.DAILY,  # Changed
      public_timestamp=new_date,  # Changed
      is_public=False,  # Changed
      num_saved_users_fraction=0.5,  # Same
      num_shared_users_fraction=0.4,  # Changed
      popularity_score=81.0,  # Changed
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["state"] == models.JokeState.DAILY.value
    assert synced["is_public"] is False
    assert synced["public_timestamp"] == new_date
    assert synced["num_saved_users_fraction"] == 0.5  # Unchanged
    assert synced["num_shared_users_fraction"] == 0.4  # Updated
    assert synced["popularity_score"] == 81.0  # Updated
    # Existing embedding should remain
    assert synced["text_embedding"] == Vector([1.0, 2.0, 3.0])

  def test_no_update_when_nothing_changed(self, mock_search_collection,
                                          mock_firestore):
    """Test that no update occurs when all fields are unchanged."""
    _, search_doc_state = mock_search_collection

    existing_date = datetime.datetime.now(datetime.timezone.utc)
    existing_embedding = Vector([1.0, 2.0, 3.0])
    search_doc_state["doc"] = {
      "text_embedding": existing_embedding,
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
      "public_timestamp": existing_date,
      "num_saved_users_fraction": 0.5,
      "num_shared_users_fraction": 0.3,
      "popularity_score": 64.0,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      public_timestamp=existing_date,
      is_public=True,
      num_saved_users_fraction=0.5,
      num_shared_users_fraction=0.3,
      popularity_score=64.0,
    )

    mock_search_doc_ref, _ = mock_search_collection
    joke_operations.sync_joke_to_search_collection(joke, None)

    # Verify set was not called since nothing changed
    mock_search_doc_ref.set.assert_not_called()

  def test_uses_new_embedding_when_provided(self, mock_search_collection,
                                            mock_firestore):
    """Test that new embedding is used when provided."""
    _, search_doc_state = mock_search_collection

    existing_embedding = Vector([5.0, 6.0, 7.0])
    search_doc_state["doc"] = {
      "text_embedding": existing_embedding,
    }

    new_embedding = Vector([1.0, 2.0, 3.0])
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
    )

    joke_operations.sync_joke_to_search_collection(joke, new_embedding)

    synced = search_doc_state["doc"]
    assert synced["text_embedding"] == new_embedding

  def test_uses_existing_embedding_from_joke_when_no_new_embedding(
      self, mock_search_collection, mock_firestore):
    """Test that existing embedding from joke is used when no new embedding provided and search doc lacks it."""
    _, search_doc_state = mock_search_collection

    # Search doc has no embedding
    search_doc_state["doc"] = {}

    joke_embedding = Vector([5.0, 6.0, 7.0])
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      zzz_joke_text_embedding=joke_embedding,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["text_embedding"] == joke_embedding

  def test_does_not_overwrite_existing_embedding_when_no_new_embedding(
      self, mock_search_collection, mock_firestore):
    """Test that existing embedding in search doc is preserved when no new embedding provided."""
    _, search_doc_state = mock_search_collection

    existing_embedding = Vector([1.0, 2.0, 3.0])
    search_doc_state["doc"] = {
      "text_embedding": existing_embedding,
    }

    joke_embedding = Vector([5.0, 6.0, 7.0])
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      zzz_joke_text_embedding=joke_embedding,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    # Should preserve existing embedding, not use joke's embedding
    assert synced["text_embedding"] == existing_embedding

  def test_skips_sync_when_joke_has_no_key(self, mock_search_collection,
                                           mock_firestore):
    """Test that sync is skipped when joke has no key."""
    _, search_doc_state = mock_search_collection

    joke = models.PunnyJoke(
      key=None,  # No key
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    # Should not create search doc when joke has no key
    assert search_doc_state["doc"] is None

  def test_syncs_is_public_when_changed(self, mock_search_collection,
                                        mock_firestore):
    """Test that is_public is synced when it changes."""
    _, search_doc_state = mock_search_collection

    # Set up existing search doc with is_public=False
    search_doc_state["doc"] = {
      "state": models.JokeState.PUBLISHED.value,
      "is_public": False,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      is_public=True,  # Changed from False to True
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["is_public"] is True

  def test_syncs_state_when_changed(self, mock_search_collection,
                                    mock_firestore):
    """Test that state is synced when it changes."""
    _, search_doc_state = mock_search_collection

    search_doc_state["doc"] = {
      "state": models.JokeState.DRAFT.value,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,  # Changed
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["state"] == models.JokeState.PUBLISHED.value

  def test_syncs_public_timestamp_when_changed(self, mock_search_collection,
                                               mock_firestore):
    """Test that public_timestamp is synced when it changes."""
    _, search_doc_state = mock_search_collection

    old_date = datetime.datetime.now(datetime.timezone.utc)
    search_doc_state["doc"] = {
      "public_timestamp": old_date,
    }

    new_date = datetime.datetime.now(
      datetime.timezone.utc) + datetime.timedelta(days=1)
    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.DAILY,
      public_timestamp=new_date,  # Changed
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["public_timestamp"] == new_date

  def test_syncs_fractions_when_changed(self, mock_search_collection,
                                        mock_firestore):
    """Test that fraction fields are synced when they change."""
    _, search_doc_state = mock_search_collection

    search_doc_state["doc"] = {
      "num_saved_users_fraction": 0.3,
      "num_shared_users_fraction": 0.2,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      num_saved_users_fraction=0.5,  # Changed
      num_shared_users_fraction=0.4,  # Changed
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["num_saved_users_fraction"] == 0.5
    assert synced["num_shared_users_fraction"] == 0.4

  def test_syncs_popularity_score_when_changed(self, mock_search_collection,
                                               mock_firestore):
    """Test that popularity_score is synced when it changes."""
    _, search_doc_state = mock_search_collection

    search_doc_state["doc"] = {
      "popularity_score": 10.0,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      popularity_score=64.0,  # Changed
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["popularity_score"] == 64.0

  def test_handles_none_values_in_search_doc(self, mock_search_collection,
                                             mock_firestore):
    """Test that None values in search doc are handled correctly."""
    _, search_doc_state = mock_search_collection

    # Search doc has None values
    search_doc_state["doc"] = {
      "state": None,
      "is_public": None,
      "num_saved_users_fraction": None,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      is_public=True,
      num_saved_users_fraction=0.5,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert synced["state"] == models.JokeState.PUBLISHED.value
    assert synced["is_public"] is True
    assert synced["num_saved_users_fraction"] == 0.5

  def test_handles_none_values_in_joke(self, mock_search_collection,
                                       mock_firestore):
    """Test that None values in joke are handled correctly."""
    _, search_doc_state = mock_search_collection

    # Search doc has values
    search_doc_state["doc"] = {
      "num_saved_users_fraction": 0.5,
      "num_shared_users_fraction": 0.3,
      "popularity_score": 64.0,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.DRAFT,
      num_saved_users_fraction=None,
      num_shared_users_fraction=None,
      popularity_score=None,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    # None values should update the search doc
    assert synced["num_saved_users_fraction"] is None
    assert synced["num_shared_users_fraction"] is None
    assert synced["popularity_score"] is None
