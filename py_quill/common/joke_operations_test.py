"""Tests for the joke_operations module."""
import datetime
from io import BytesIO
from unittest.mock import MagicMock, Mock, create_autospec

import pytest
from common import joke_operations, models
from google.api_core import datetime_helpers
from google.cloud.firestore_v1.vector import Vector
from PIL import Image


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


@pytest.fixture(name='mock_image_generation')
def mock_image_generation_fixture(monkeypatch):
  """Fixture that mocks the image_generation service."""
  mock_image_generation = create_autospec(joke_operations.image_generation)
  monkeypatch.setattr(joke_operations, 'image_generation',
                      mock_image_generation)
  return mock_image_generation


@pytest.fixture(name='mock_scene_prompts')
def mock_scene_prompts_fixture(monkeypatch):
  """Fixture that stubs scene prompt helpers."""

  def fake_modify(**_kwargs):
    return ("updated setup scene", "updated punchline scene",
            models.SingleGenerationMetadata(model_name="editor"))

  def fake_descriptions(**_kwargs):
    return ("detailed setup image", "detailed punchline image",
            models.SingleGenerationMetadata(model_name="describer"))

  monkeypatch.setattr(
    joke_operations.joke_operation_prompts,
    'modify_scene_ideas_with_suggestions',
    fake_modify,
  )
  monkeypatch.setattr(
    joke_operations.joke_operation_prompts,
    'generate_detailed_image_descriptions',
    fake_descriptions,
  )

  return fake_modify, fake_descriptions


@pytest.fixture(name='mock_scene_ideas')
def mock_scene_ideas_fixture(monkeypatch):
  """Fixture that stubs scene idea and safety generation."""

  def fake_generate(*_args, **_kwargs):
    return "idea-setup", "idea-punch", models.GenerationMetadata()

  monkeypatch.setattr(
    joke_operations.joke_operation_prompts,
    "generate_joke_scene_ideas",
    fake_generate,
  )
  return fake_generate


def test_initialize_joke_creates_new_with_overrides(monkeypatch,
                                                    mock_firestore):
  """initialize_joke should build a new joke and apply field overrides."""
  monkeypatch.setattr(joke_operations.random, 'randint', lambda _a, _b: 999)

  joke = joke_operations.initialize_joke(
    joke_id=None,
    user_id="user-42",
    admin_owned=False,
    setup_text="  Setup ",
    punchline_text="Punchline ",
    seasonal="Holiday",
    tags=["winter", "cozy"],
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    setup_image_description="setup desc",
    punchline_image_description="punch desc",
  )

  assert joke.owner_user_id == "user-42"
  assert joke.state == models.JokeState.DRAFT
  assert joke.random_id == 999
  assert joke.setup_text == "Setup"
  assert joke.punchline_text == "Punchline"
  assert joke.setup_scene_idea == "scene setup"
  assert joke.punchline_scene_idea == "scene punch"
  assert joke.setup_image_description == "setup desc"
  assert joke.punchline_image_description == "punch desc"
  assert joke.seasonal == "Holiday"
  assert joke.tags == ["winter", "cozy"]
  mock_firestore.get_punny_joke.assert_not_called()


def test_initialize_joke_updates_existing_fields(mock_firestore):
  """initialize_joke should patch provided fields on an existing joke."""
  joke = models.PunnyJoke(
    key="j-1",
    setup_text="old setup",
    punchline_text="old punch",
    setup_scene_idea="old scene",
    punchline_scene_idea="old punch scene",
  )
  mock_firestore.get_punny_joke.return_value = joke

  updated = joke_operations.initialize_joke(
    joke_id="j-1",
    user_id=None,
    admin_owned=False,
    setup_text="new setup",
    punchline_text="new punch",
    seasonal="Spring",
    tags=["fresh"],
    setup_scene_idea="new scene",
    setup_image_description="desc",
  )

  assert updated is joke
  assert updated.key == "j-1"
  assert updated.setup_text == "new setup"
  assert updated.punchline_text == "new punch"
  assert updated.setup_scene_idea == "new scene"
  assert updated.punchline_scene_idea == "old punch scene"
  assert updated.setup_image_description == "desc"
  assert updated.seasonal == "Spring"
  assert updated.tags == ["fresh"]
  mock_firestore.get_punny_joke.assert_called_once_with("j-1")


def test_initialize_joke_updates_image_urls_and_clears_upscaled(mock_firestore):
  """initialize_joke should allow selecting existing image URLs."""
  joke = models.PunnyJoke(
    key="j-1",
    setup_text="setup",
    punchline_text="punch",
    setup_image_url="setup-old",
    punchline_image_url="punch-old",
    setup_image_url_upscaled="setup-old-up",
    punchline_image_url_upscaled="punch-old-up",
    all_setup_image_urls=["setup-old"],
    all_punchline_image_urls=["punch-old"],
  )
  mock_firestore.get_punny_joke.return_value = joke

  updated = joke_operations.initialize_joke(
    joke_id="j-1",
    user_id=None,
    admin_owned=False,
    setup_image_url="setup-new",
    punchline_image_url="punch-new",
  )

  assert updated.setup_image_url == "setup-new"
  assert updated.punchline_image_url == "punch-new"
  assert updated.setup_image_url_upscaled is None
  assert updated.punchline_image_url_upscaled is None
  assert "setup-new" in updated.all_setup_image_urls
  assert "punch-new" in updated.all_punchline_image_urls


def test_initialize_joke_raises_for_missing_joke(mock_firestore):
  """initialize_joke should raise when the joke_id cannot be found."""
  mock_firestore.get_punny_joke.return_value = None

  with pytest.raises(joke_operations.JokeNotFoundError,
                     match='Joke not found: missing'):
    joke_operations.initialize_joke(
      joke_id="missing",
      user_id=None,
      admin_owned=False,
    )


def test_generate_joke_images_updates_images(mock_image_generation):
  """generate_joke_images should update images and clear upscaled URLs."""
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_description="setup desc",
    punchline_image_description="punch desc",
    setup_image_url_upscaled="old_setup_upscaled",
    punchline_image_url_upscaled="old_punch_upscaled",
  )
  setup_image = models.Image(url="setup-url")
  punch_image = models.Image(url="punch-url")
  mock_image_generation.generate_pun_images.return_value = (setup_image,
                                                            punch_image)

  updated = joke_operations.generate_joke_images(joke, "medium")

  assert updated.setup_image_url == "setup-url"
  assert updated.punchline_image_url == "punch-url"
  assert updated.setup_image_url_upscaled is None
  assert updated.punchline_image_url_upscaled is None


def test_generate_joke_images_moves_draft_to_unreviewed(mock_image_generation):
  """generate_joke_images should transition DRAFT jokes to UNREVIEWED."""
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_description="setup desc",
    punchline_image_description="punch desc",
    state=models.JokeState.DRAFT,
  )
  mock_image_generation.generate_pun_images.return_value = (
    models.Image(url="setup-url"),
    models.Image(url="punch-url"),
  )

  updated = joke_operations.generate_joke_images(joke, "medium")

  assert updated.state == models.JokeState.UNREVIEWED


def test_generate_joke_images_generates_descriptions_when_missing(
    mock_scene_prompts, mock_image_generation):
  """generate_joke_images should backfill descriptions before rendering."""
  _ = mock_scene_prompts
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    setup_image_description=None,
    punchline_image_description=None,
  )
  mock_image_generation.generate_pun_images.return_value = (
    models.Image(
      url="setup-url",
      original_prompt="detailed setup image",
      final_prompt="setup prompt",
    ),
    models.Image(
      url="punch-url",
      original_prompt="detailed punchline image",
      final_prompt="punch prompt",
    ),
  )

  updated = joke_operations.generate_joke_images(joke, "medium")

  assert updated.setup_image_description == "detailed setup image"
  assert updated.punchline_image_description == "detailed punchline image"
  mock_image_generation.generate_pun_images.assert_called_once()


def test_generate_joke_images_missing_scene_idea_raises():
  """generate_joke_images should raise when scene ideas are missing."""
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    setup_scene_idea=None,
    punchline_scene_idea="idea",
    setup_image_description=None,
    punchline_image_description=None,
  )

  with pytest.raises(joke_operations.JokePopulationError, match='scene ideas'):
    joke_operations.generate_joke_images(joke, "medium")


def test_modify_image_scene_ideas_updates_in_memory(mock_firestore,
                                                    mock_scene_prompts):
  """modify_image_scene_ideas should call prompt helper and update in memory."""
  _ = mock_scene_prompts
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="setup",
    punchline_text="punch",
    setup_scene_idea="old setup scene",
    punchline_scene_idea="old punch scene",
    generation_metadata=models.GenerationMetadata(),
  )

  updated = joke_operations.modify_image_scene_ideas(
    joke=joke,
    setup_suggestion="make it sillier",
    punchline_suggestion="add confetti",
  )

  assert updated.setup_scene_idea == "updated setup scene"
  assert updated.punchline_scene_idea == "updated punchline scene"
  assert updated.generation_metadata.generations
  mock_firestore.upsert_punny_joke.assert_not_called()


def test_generate_image_descriptions_sets_fields(mock_scene_prompts):
  """generate_image_descriptions should fill description fields."""
  _ = mock_scene_prompts
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    generation_metadata=models.GenerationMetadata(),
  )

  result = joke_operations.generate_image_descriptions(joke)

  assert result.setup_image_description == "detailed setup image"
  assert result.punchline_image_description == "detailed punchline image"
  assert result.generation_metadata.generations


def test_regenerate_scene_ideas_replaces_scene_ideas(monkeypatch):
  """regenerate_scene_ideas should rebuild scene ideas and append metadata."""

  def fake_generate(*_args, **_kwargs):
    return ("new scene setup", "new scene punch",
            models.SingleGenerationMetadata(model_name="regen"))

  monkeypatch.setattr(
    joke_operations.joke_operation_prompts,
    "generate_joke_scene_ideas",
    fake_generate,
  )

  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="old setup",
    punchline_text="old punch",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    generation_metadata=models.GenerationMetadata(),
  )

  updated = joke_operations.regenerate_scene_ideas(joke)

  assert updated.setup_scene_idea == "new scene setup"
  assert updated.punchline_scene_idea == "new scene punch"
  assert updated.generation_metadata.generations


def test_to_response_joke_strips_embedding():
  """to_response_joke should remove embedding fields."""
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
  )
  response = joke_operations.to_response_joke(joke)

  assert response["key"] == "joke-1"
  assert 'zzz_joke_text_embedding' not in response


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


def test_upscale_joke_override_forces_upscale(mock_firestore,
                                              mock_image_client,
                                              mock_cloud_storage):
  """Override parameter should force re-upscaling even if URLs exist."""
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url="https://storage.googleapis.com/example/punchline.png",
    setup_image_url_upscaled="http://example.com/existing_setup.png",
    punchline_image_url_upscaled="http://example.com/existing_punchline.png",
    generation_metadata=models.GenerationMetadata(),
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance
  mock_client_instance.upscale_image.side_effect = [
    models.Image(url_upscaled="http://example.com/new_setup.png",
                 generation_metadata=models.GenerationMetadata()),
    models.Image(url_upscaled="http://example.com/new_punchline.png",
                 generation_metadata=models.GenerationMetadata()),
  ]

  mock_cloud_storage.extract_gcs_uri_from_image_url.side_effect = [
    "gs://example/setup.png", "gs://example/punchline.png"
  ]

  joke_operations.upscale_joke("joke1", overwrite=True)

  assert mock_client_instance.upscale_image.call_count == 2


def test_upscale_joke_high_quality_replaces_main_images(
  mock_firestore,
  mock_image_client,
  mock_cloud_storage,
  monkeypatch,
):
  """High quality upscaling should replace the primary image with downscaled copy."""
  mock_joke = models.PunnyJoke(
    key="joke1",
    setup_text="test",
    punchline_text="test",
    setup_image_url="https://storage.googleapis.com/example/setup.png",
    punchline_image_url=None,
    generation_metadata=models.GenerationMetadata(),
  )
  mock_firestore.get_punny_joke.return_value = mock_joke

  mock_client_instance = MagicMock()
  mock_image_client.get_client.return_value = mock_client_instance

  upscale_metadata = models.GenerationMetadata()
  upscale_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="hq"))
  mock_client_instance.upscale_image.return_value = models.Image(
    url_upscaled="http://example.com/upscaled_setup.png",
    gcs_uri_upscaled="gs://example/upscaled_setup.png",
    generation_metadata=upscale_metadata,
  )

  original_bytes = _encode_test_image((1024, 1024))
  upscaled_bytes = _encode_test_image((2048, 2048))  # x2 upscale from 1024

  def fake_download_bytes(gcs_uri: str) -> bytes:
    if gcs_uri == "gs://example/setup.png":
      return original_bytes
    if gcs_uri == "gs://example/upscaled_setup.png":
      return upscaled_bytes
    raise AssertionError(f"Unexpected download URI: {gcs_uri}")

  def fake_download_image(gcs_uri: str) -> Image.Image:
    """Mock download_image_from_gcs to return a PIL Image."""
    bytes_data = fake_download_bytes(gcs_uri)
    return Image.open(BytesIO(bytes_data))

  mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"
  mock_cloud_storage.download_bytes_from_gcs.side_effect = fake_download_bytes
  mock_cloud_storage.download_image_from_gcs.side_effect = fake_download_image
  mock_cloud_storage.get_image_gcs_uri.return_value = "gs://example/downscaled_setup.png"
  mock_cloud_storage.get_final_image_url.return_value = "http://cdn/downscaled_setup.png"

  uploaded_payloads: list[tuple[bytes, str, str]] = []

  def fake_upload(*, content_bytes: bytes, gcs_uri: str, content_type: str):
    uploaded_payloads.append((content_bytes, gcs_uri, content_type))
    assert gcs_uri == "gs://example/downscaled_setup.png"
    assert content_type == "image/png"
    return gcs_uri

  mock_cloud_storage.upload_bytes_to_gcs.side_effect = fake_upload

  class FakeEditor:

    def scale_image(self, image: Image.Image,
                    scale_factor: float) -> Image.Image:
      new_width = max(1, int(round(image.width * scale_factor)))
      new_height = max(1, int(round(image.height * scale_factor)))
      return image.resize((new_width, new_height), Image.Resampling.NEAREST)

  monkeypatch.setattr(joke_operations.image_editor, "ImageEditor",
                      lambda: FakeEditor())

  result = joke_operations.upscale_joke("joke1", high_quality=True)

  assert result.setup_image_url == "http://cdn/downscaled_setup.png"
  assert result.setup_image_url_upscaled == "http://example.com/upscaled_setup.png"
  assert uploaded_payloads, "Should upload newly downscaled image"
  assert len(result.generation_metadata.generations) == 1
  mock_firestore.update_punny_joke.assert_called_once()
  update_payload = mock_firestore.update_punny_joke.call_args.args[1]
  assert update_payload["setup_image_url"] == "http://cdn/downscaled_setup.png"
  assert update_payload["all_setup_image_urls"][
    0] == "http://cdn/downscaled_setup.png"
  assert "https://storage.googleapis.com/example/setup.png" in update_payload[
    "all_setup_image_urls"]


def _encode_test_image(size: tuple[int, int]) -> bytes:
  """Create an in-memory PNG image of the requested size."""
  image = Image.new("RGB", size, color=(255, 0, 0))
  buffer = BytesIO()
  image.save(buffer, format="PNG")
  return buffer.getvalue()


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
      "book_id": None,
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
      book_id=None,
    )

    mock_search_doc_ref, _ = mock_search_collection
    joke_operations.sync_joke_to_search_collection(joke, None)

    # Verify set was not called since nothing changed
    mock_search_doc_ref.set.assert_not_called()

  def test_writes_book_id_when_missing_from_search_doc(self,
                                                       mock_search_collection,
                                                       mock_firestore):
    """Test that a missing book_id field is explicitly written as null."""
    _, search_doc_state = mock_search_collection

    search_doc_state["doc"] = {
      "state": models.JokeState.PUBLISHED.value,
      "is_public": True,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
      is_public=True,
      book_id=None,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert "book_id" in synced
    assert synced["book_id"] is None

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
    """Jokes no longer store embeddings; do not write embedding without new_embedding."""
    _, search_doc_state = mock_search_collection

    # Search doc has no embedding
    search_doc_state["doc"] = {}

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
    )

    joke_operations.sync_joke_to_search_collection(joke, None)

    synced = search_doc_state["doc"]
    assert "text_embedding" not in synced

  def test_does_not_overwrite_existing_embedding_when_no_new_embedding(
      self, mock_search_collection, mock_firestore):
    """Test that existing embedding in search doc is preserved when no new embedding provided."""
    _, search_doc_state = mock_search_collection

    existing_embedding = Vector([1.0, 2.0, 3.0])
    search_doc_state["doc"] = {
      "text_embedding": existing_embedding,
    }

    joke = models.PunnyJoke(
      key="joke1",
      setup_text="Test setup",
      punchline_text="Test punchline",
      state=models.JokeState.PUBLISHED,
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


def test_to_response_joke_serializes_datetime():
  """to_response_joke should convert datetime objects to ISO strings."""
  now = datetime.datetime.now(datetime.timezone.utc)
  joke = models.PunnyJoke(
    key="joke-1",
    setup_text="Setup",
    punchline_text="Punch",
    public_timestamp=now,
  )

  response = joke_operations.to_response_joke(joke)

  assert response["key"] == "joke-1"
  assert response["public_timestamp"] == now.isoformat()
  assert isinstance(response["public_timestamp"], str)


def test_to_response_joke_serializes_datetime_with_nanoseconds():
  """to_response_joke should convert DatetimeWithNanoseconds to strings."""
  # Simulate DatetimeWithNanoseconds from Firestore
  now = datetime_helpers.DatetimeWithNanoseconds.now(datetime.timezone.utc)

  joke = models.PunnyJoke(
    key="joke-2",
    setup_text="Setup",
    punchline_text="Punch",
    public_timestamp=now,
  )

  response = joke_operations.to_response_joke(joke)

  assert response["public_timestamp"] == now.isoformat()
  assert isinstance(response["public_timestamp"], str)
