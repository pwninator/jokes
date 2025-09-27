"""Tests for the joke_operations module."""
from unittest.mock import MagicMock, Mock

import pytest
from common import joke_operations, models


@pytest.fixture(name="mock_services")
def mock_services_fixture(monkeypatch):
    """Fixture that mocks external services using monkeypatch."""
    mock_firestore = Mock()
    mock_image_client = Mock()
    mock_cloud_storage = Mock()

    monkeypatch.setattr(joke_operations, 'firestore', mock_firestore)
    monkeypatch.setattr(joke_operations, 'image_client', mock_image_client)
    monkeypatch.setattr(joke_operations, 'cloud_storage', mock_cloud_storage)

    return mock_firestore, mock_image_client, mock_cloud_storage


def test_upscale_joke_success(mock_services):
    """Test that upscale_joke successfully upscales a joke's images."""
    # Arrange
    mock_firestore, mock_image_client, mock_cloud_storage = mock_services

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
        generation_metadata=models.GenerationMetadata()
    )
    mock_upscaled_punchline_image = models.Image(
        url_upscaled="http://example.com/new_punchline.png",
        generation_metadata=models.GenerationMetadata()
    )
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


def test_upscale_joke_idempotent(mock_services):
    """Test that upscale_joke is idempotent and returns immediately if images are already upscaled."""
    # Arrange
    mock_firestore, mock_image_client, _ = mock_services

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


def test_upscale_joke_not_found(mock_services):
    """Test that upscale_joke raises ValueError if joke is not found."""
    # Arrange
    mock_firestore, _, _ = mock_services
    mock_firestore.get_punny_joke.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Joke not found: joke1"):
        joke_operations.upscale_joke("joke1")


def test_upscale_joke_only_one_image(mock_services):
    """Test that upscale_joke only upscales the missing image."""
    # Arrange
    mock_firestore, mock_image_client, mock_cloud_storage = mock_services

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
        generation_metadata=models.GenerationMetadata()
    )
    mock_client_instance.upscale_image.return_value = mock_upscaled_setup_image

    mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

    # Act
    upscaled_joke = joke_operations.upscale_joke("joke1")

    # Assert
    mock_firestore.get_punny_joke.assert_called_once_with("joke1")
    mock_client_instance.upscale_image.assert_called_once()
    assert upscaled_joke.setup_image_url_upscaled == "http://example.com/new_setup.png"
    assert upscaled_joke.punchline_image_url_upscaled == "http://example.com/existing_punchline.png"


def test_upscale_joke_missing_one_image_url(mock_services):
    """Test that upscale_joke only upscales the available image if one is missing."""
    # Arrange
    mock_firestore, mock_image_client, mock_cloud_storage = mock_services

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
        generation_metadata=models.GenerationMetadata()
    )
    mock_client_instance.upscale_image.return_value = mock_upscaled_setup_image

    mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

    # Act
    upscaled_joke = joke_operations.upscale_joke("joke1")

    # Assert
    mock_firestore.get_punny_joke.assert_called_once_with("joke1")
    mock_client_instance.upscale_image.assert_called_once()
    assert upscaled_joke.setup_image_url_upscaled == "http://example.com/new_setup.png"
    assert upscaled_joke.punchline_image_url_upscaled is None


def test_upscale_joke_updates_metadata(mock_services):
    """Test that upscale_joke correctly updates the generation_metadata."""
    # Arrange
    mock_firestore, mock_image_client, mock_cloud_storage = mock_services

    initial_metadata = models.GenerationMetadata()
    initial_metadata.add_generation(models.SingleGenerationMetadata(model_name="initial_model"))

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
    upscale_metadata.add_generation(models.SingleGenerationMetadata(model_name="upscale_model"))
    mock_upscaled_image = models.Image(
        url_upscaled="http://example.com/new_setup.png",
        generation_metadata=upscale_metadata
    )
    mock_client_instance.upscale_image.return_value = mock_upscaled_image

    mock_cloud_storage.extract_gcs_uri_from_image_url.return_value = "gs://example/setup.png"

    # Act
    upscaled_joke = joke_operations.upscale_joke("joke1")

    # Assert
    assert len(upscaled_joke.generation_metadata.generations) == 2
    assert upscaled_joke.generation_metadata.generations[0].model_name == "initial_model"
    assert upscaled_joke.generation_metadata.generations[1].model_name == "upscale_model"