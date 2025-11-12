"""Unit tests for image_operations module."""

from __future__ import annotations

import datetime as std_datetime
import unittest
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from common import image_operations
from services import image_editor


def _create_image_bytes(color: str) -> bytes:
  """Create dummy 1024x1024 PNG image bytes of the given color."""
  pil_image = Image.new('RGB', (1024, 1024), color=color)
  buffer = BytesIO()
  pil_image.save(buffer, format='PNG')
  return buffer.getvalue()


class RecordingImageEditor(image_editor.ImageEditor):
  """ImageEditor subclass that records paste calls."""

  def __init__(self):
    super().__init__()
    self.create_calls: list[tuple[int, int]] = []
    self.paste_calls: list[tuple[int, int]] = []

  def create_blank_image(self, width: int, height: int, color=(255, 255, 255)):
    self.create_calls.append((width, height))
    return super().create_blank_image(width, height, color)

  def paste_image(self, base_image, image_to_paste, x: int, y: int):
    self.paste_calls.append((x, y, image_to_paste.size))
    return super().paste_image(base_image, image_to_paste, x, y)


class CreateAdAssetsTest(unittest.TestCase):
  """Tests for create_ad_assets function."""

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.datetime.datetime')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_ad_assets_success(self, mock_datetime, mock_storage,
                                    mock_firestore):
    """create_ad_assets composes images and stores URL."""
    fixed_dt = std_datetime.datetime(2025, 1, 2, 3, 4, 5, 6000)
    mock_datetime.now.return_value = fixed_dt

    mock_joke = SimpleNamespace(
      key='joke123',
      setup_image_url='https://cdn.example.com/setup.png',
      punchline_image_url='https://cdn.example.com/punchline.png',
    )
    mock_firestore.get_punny_joke.return_value = mock_joke

    mock_firestore_db = MagicMock()
    mock_metadata_doc = MagicMock()
    (mock_firestore_db.collection.return_value.document.return_value.
     collection.return_value.document.return_value) = mock_metadata_doc
    mock_firestore.db.return_value = mock_firestore_db
    metadata_snapshot = MagicMock()
    metadata_snapshot.exists = False
    mock_metadata_doc.get.return_value = metadata_snapshot

    setup_bytes = _create_image_bytes('red')
    punchline_bytes = _create_image_bytes('blue')

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract
    mock_storage.download_bytes_from_gcs.side_effect = (
      lambda gcs_uri: setup_bytes
      if gcs_uri.endswith('setup.png') else punchline_bytes)

    expected_timestamp = fixed_dt.strftime("%Y%m%d_%H%M%S_%f")
    expected_gcs_uri = (
      f'gs://test-bucket/joke123_ad_landscape_{expected_timestamp}.png')
    mock_storage.get_final_image_url.return_value = 'https://cdn.example.com/ad.png'

    editor = RecordingImageEditor()

    result = image_operations.create_ad_assets('joke123', editor)

    self.assertEqual(result, ['https://cdn.example.com/ad.png'])
    mock_firestore.get_punny_joke.assert_called_once_with('joke123')
    self.assertEqual(editor.create_calls, [(2048, 1024)])
    self.assertEqual(editor.paste_calls, [(0, 0, (1024, 1024)),
                                          (1024, 0, (1024, 1024))])

    mock_storage.upload_bytes_to_gcs.assert_called_once()
    upload_args, upload_kwargs = mock_storage.upload_bytes_to_gcs.call_args
    self.assertIsInstance(upload_args[0], (bytes, bytearray))
    self.assertEqual(upload_args[1], expected_gcs_uri)
    self.assertEqual(upload_args[2], "image/png")
    self.assertFalse(upload_kwargs)

    mock_storage.get_final_image_url.assert_called_once_with(expected_gcs_uri,
                                                             width=2048)
    mock_metadata_doc.set.assert_called_once_with(
      {'ad_creative_landscape': 'https://cdn.example.com/ad.png'}, merge=True)
    mock_metadata_doc.get.assert_called_once()

  @patch('common.image_operations.firestore.get_punny_joke', return_value=None)
  def test_create_ad_assets_missing_joke(self, mock_get_joke):
    with self.assertRaisesRegex(ValueError, 'Joke not found'):
      image_operations.create_ad_assets('missing-joke')
    mock_get_joke.assert_called_once_with('missing-joke')

  @patch('common.image_operations.firestore')
  def test_create_ad_assets_missing_images(self, mock_firestore):
    mock_joke = SimpleNamespace(key='joke123',
                                setup_image_url=None,
                                punchline_image_url=None)
    mock_firestore.get_punny_joke.return_value = mock_joke

    with self.assertRaisesRegex(ValueError, 'missing required image URLs'):
      image_operations.create_ad_assets('joke123')

    mock_firestore.get_punny_joke.assert_called_once_with('joke123')

  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.firestore')
  def test_create_ad_assets_returns_existing_metadata(self, mock_firestore,
                                                      mock_storage):
    """Existing metadata should short-circuit without generating new assets."""
    mock_joke = SimpleNamespace(
      key='jokeABC',
      setup_image_url='https://cdn.example.com/setup.png',
      punchline_image_url='https://cdn.example.com/punchline.png',
    )
    mock_firestore.get_punny_joke.return_value = mock_joke

    mock_firestore_db = MagicMock()
    mock_metadata_doc = MagicMock()
    (mock_firestore_db.collection.return_value.document.return_value.
     collection.return_value.document.return_value) = mock_metadata_doc
    mock_firestore.db.return_value = mock_firestore_db

    metadata_snapshot = MagicMock()
    metadata_snapshot.exists = True
    metadata_snapshot.to_dict.return_value = {
      'ad_creative_landscape': 'https://cdn.example.com/existing.png'
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    mock_editor = Mock(spec=image_editor.ImageEditor)

    result = image_operations.create_ad_assets('jokeABC', mock_editor)

    self.assertEqual(result, ['https://cdn.example.com/existing.png'])
    mock_editor.create_blank_image.assert_not_called()
    mock_editor.paste_image.assert_not_called()
    mock_storage.extract_gcs_uri_from_image_url.assert_not_called()
    mock_storage.download_bytes_from_gcs.assert_not_called()
    mock_storage.upload_bytes_to_gcs.assert_not_called()
    mock_storage.get_final_image_url.assert_not_called()
    mock_metadata_doc.set.assert_not_called()
    mock_metadata_doc.get.assert_called_once()
    mock_firestore.get_punny_joke.assert_called_once_with('jokeABC')


if __name__ == '__main__':
  unittest.main()
