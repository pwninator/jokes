"""Unit tests for image_operations module."""

from __future__ import annotations

import datetime as std_datetime
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from common import image_operations
from PIL import Image
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

  def paste_image(self,
                  base_image,
                  image_to_paste,
                  x: int,
                  y: int,
                  add_shadow: bool = False):
    self.paste_calls.append((x, y, image_to_paste.size))
    return super().paste_image(base_image,
                               image_to_paste,
                               x,
                               y,
                               add_shadow=add_shadow)


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
    bg_img = Image.new('RGB', (1024, 1280), color='white')
    bg_buffer = BytesIO()
    bg_img.save(bg_buffer, format='PNG')
    bg_bytes = bg_buffer.getvalue()

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _download_side_effect(gcs_uri: str):
      if gcs_uri in (
          image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI,
          image_operations._AD_BACKGROUND_SQUARE_DESK_URI,
          image_operations._AD_BACKGROUND_SQUARE_CORKBOARD_URI,
      ):
        return bg_bytes
      if gcs_uri.endswith('setup.png'):
        return setup_bytes
      return punchline_bytes

    mock_storage.download_bytes_from_gcs.side_effect = _download_side_effect

    expected_timestamp = fixed_dt.strftime("%Y%m%d_%H%M%S_%f")
    landscape_gcs_uri = (
      f'gs://test-bucket/joke123_ad_landscape_{expected_timestamp}.png')
    portrait_drawing_gcs_uri = (
      f'gs://test-bucket/joke123_ad_square_drawing_{expected_timestamp}.png')
    portrait_desk_gcs_uri = (
      f'gs://test-bucket/joke123_ad_square_desk_{expected_timestamp}.png')
    portrait_corkboard_gcs_uri = (
      f'gs://test-bucket/joke123_ad_square_corkboard_{expected_timestamp}.png')
    mock_storage.get_final_image_url.side_effect = [
      'https://cdn.example.com/ad_landscape.png',
      'https://cdn.example.com/ad_square_drawing.png',
      'https://cdn.example.com/ad_square_desk.png',
      'https://cdn.example.com/ad_square_corkboard.png',
    ]

    editor = RecordingImageEditor()

    result = image_operations.create_ad_assets('joke123', editor)

    self.assertEqual(result, [
      'https://cdn.example.com/ad_landscape.png',
      'https://cdn.example.com/ad_square_drawing.png',
      'https://cdn.example.com/ad_square_desk.png',
      'https://cdn.example.com/ad_square_corkboard.png',
    ])
    mock_firestore.get_punny_joke.assert_called_once_with('joke123')
    # Landscape created via blank canvas; portrait uses background image
    self.assertEqual(editor.create_calls, [(2048, 1024)])
    # Verify landscape paste operations: setup and punchline side-by-side
    landscape_pastes = editor.paste_calls[:2]
    self.assertEqual(len(landscape_pastes), 2)
    self.assertEqual(landscape_pastes[0][2], (1024, 1024))  # setup image size
    self.assertEqual(landscape_pastes[1][2],
                     (1024, 1024))  # punchline image size
    # Portrait pastes: should have 3 portrait variations * 2 images each (setup + punchline)
    # Total pastes: 2 (landscape) + 6 (portrait) = 8
    self.assertEqual(len(editor.paste_calls), 8)

    self.assertEqual(mock_storage.upload_bytes_to_gcs.call_count, 4)
    upload_calls = mock_storage.upload_bytes_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].args[1], landscape_gcs_uri)
    self.assertEqual(upload_calls[1].args[1], portrait_drawing_gcs_uri)
    self.assertEqual(upload_calls[2].args[1], portrait_desk_gcs_uri)
    self.assertEqual(upload_calls[3].args[1], portrait_corkboard_gcs_uri)
    for call in upload_calls:
      self.assertIsInstance(call.args[0], (bytes, bytearray))
      self.assertEqual(call.args[2], "image/png")
      self.assertEqual(call.kwargs, {})

    mock_storage.get_final_image_url.assert_any_call(landscape_gcs_uri,
                                                     width=2048)
    mock_storage.get_final_image_url.assert_any_call(portrait_drawing_gcs_uri,
                                                     width=1024)
    mock_storage.get_final_image_url.assert_any_call(portrait_desk_gcs_uri,
                                                     width=1024)
    mock_storage.get_final_image_url.assert_any_call(
      portrait_corkboard_gcs_uri, width=1024)
    mock_metadata_doc.set.assert_called_once_with(
      {
        'ad_creative_landscape':
        'https://cdn.example.com/ad_landscape.png',
        'ad_creative_square_drawing':
        'https://cdn.example.com/ad_square_drawing.png',
        'ad_creative_square_desk':
        'https://cdn.example.com/ad_square_desk.png',
        'ad_creative_square_corkboard':
        'https://cdn.example.com/ad_square_corkboard.png',
      },
      merge=True)
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
      'ad_creative_landscape':
      'https://cdn.example.com/existing_landscape.png',
      'ad_creative_square_drawing':
      'https://cdn.example.com/existing_square_drawing.png',
      'ad_creative_square_desk':
      'https://cdn.example.com/existing_square_desk.png',
      'ad_creative_square_corkboard':
      'https://cdn.example.com/existing_square_corkboard.png',
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    mock_editor = Mock(spec=image_editor.ImageEditor)

    result = image_operations.create_ad_assets('jokeABC',
                                               mock_editor,
                                               overwrite=False)

    self.assertEqual(result, [
      'https://cdn.example.com/existing_landscape.png',
      'https://cdn.example.com/existing_square_drawing.png',
      'https://cdn.example.com/existing_square_desk.png',
      'https://cdn.example.com/existing_square_corkboard.png',
    ])
    mock_editor.create_blank_image.assert_not_called()
    mock_editor.paste_image.assert_not_called()
    mock_storage.extract_gcs_uri_from_image_url.assert_not_called()
    mock_storage.download_bytes_from_gcs.assert_not_called()
    mock_storage.upload_bytes_to_gcs.assert_not_called()
    mock_storage.get_final_image_url.assert_not_called()
    mock_metadata_doc.set.assert_not_called()
    mock_metadata_doc.get.assert_called_once()
    mock_firestore.get_punny_joke.assert_called_once_with('jokeABC')


class ComposePortraitDrawingTest(unittest.TestCase):

  @patch('common.image_operations.cloud_storage')
  def test_compose_portrait_drawing_positions_and_size(self, mock_storage):
    # Prepare background
    bg_img = Image.new('RGB', (1024, 1280), color='white')
    bg_buffer = BytesIO()
    bg_img.save(bg_buffer, format='PNG')
    mock_storage.download_bytes_from_gcs.return_value = bg_buffer.getvalue()

    # Prepare setup/punchline
    setup = Image.new('RGB', (1024, 1024), color='red')
    punchline = Image.new('RGB', (1024, 1024), color='blue')

    editor = RecordingImageEditor()

    bytes_out, width = image_operations._compose_square_drawing_ad_image(
      editor,
      setup,
      punchline,
      background_uri=image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI)

    self.assertIsInstance(bytes_out, (bytes, bytearray))
    self.assertEqual(width, 1024)
    # Verify both setup and punchline images are pasted
    self.assertEqual(len(editor.paste_calls), 2)
    # Both should be rotated/scaled versions (smaller than original 1024x1024)
    for paste_call in editor.paste_calls:
      self.assertLess(paste_call[2][0], 1024)  # width < 1024
      self.assertLess(paste_call[2][1], 1024)  # height < 1024

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.datetime.datetime')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_ad_assets_overwrite_true_generates_new(
      self, mock_datetime, mock_storage, mock_firestore):
    # Arrange existing metadata
    fixed_dt = std_datetime.datetime(2025, 2, 3, 4, 5, 6, 7000)
    mock_datetime.now.return_value = fixed_dt

    mock_joke = SimpleNamespace(
      key='jokeXYZ',
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
      'ad_creative_landscape':
      'https://cdn.example.com/existing_landscape.png',
      'ad_creative_portrait_drawing':
      'https://cdn.example.com/existing_portrait_drawing.png',
      'ad_creative_portrait_desk':
      'https://cdn.example.com/existing_portrait_desk.png',
      'ad_creative_portrait_corkboard':
      'https://cdn.example.com/existing_portrait_corkboard.png',
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    # Image bytes for setup/punchline and backgrounds
    setup_bytes = _create_image_bytes('red')
    punchline_bytes = _create_image_bytes('blue')
    bg_img = Image.new('RGB', (1024, 1280), color='white')
    bg_buffer = BytesIO()
    bg_img.save(bg_buffer, format='PNG')
    bg_bytes = bg_buffer.getvalue()

    def _extract(uri):
      return f'gs://bucket/{uri.split(' / ')[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _download_side_effect(gcs_uri: str):
      if gcs_uri in (
          image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI,
          image_operations._AD_BACKGROUND_SQUARE_DESK_URI,
          image_operations._AD_BACKGROUND_SQUARE_CORKBOARD_URI,
      ):
        return bg_bytes
      if gcs_uri.endswith('setup.png'):
        return setup_bytes
      return punchline_bytes

    mock_storage.download_bytes_from_gcs.side_effect = _download_side_effect

    expected_timestamp = fixed_dt.strftime('%Y%m%d_%H%M%S_%f')
    landscape_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_ad_landscape_{expected_timestamp}.png')
    portrait_drawing_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_ad_square_drawing_{expected_timestamp}.png')
    portrait_desk_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_ad_square_desk_{expected_timestamp}.png')
    portrait_corkboard_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_ad_square_corkboard_{expected_timestamp}.png')

    mock_storage.get_final_image_url.side_effect = [
      'https://cdn.example.com/new_landscape.png',
      'https://cdn.example.com/new_portrait_drawing.png',
      'https://cdn.example.com/new_portrait_desk.png',
      'https://cdn.example.com/new_portrait_corkboard.png',
    ]

    editor = RecordingImageEditor()

    # Act with overwrite=True
    result = image_operations.create_ad_assets('jokeXYZ',
                                               editor,
                                               overwrite=True)

    # Assert new assets generated
    self.assertEqual(result, [
      'https://cdn.example.com/new_landscape.png',
      'https://cdn.example.com/new_portrait_drawing.png',
      'https://cdn.example.com/new_portrait_desk.png',
      'https://cdn.example.com/new_portrait_corkboard.png',
    ])

    # Four uploads with expected URIs
    self.assertEqual(mock_storage.upload_bytes_to_gcs.call_count, 4)
    upload_calls = mock_storage.upload_bytes_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].args[1], landscape_gcs_uri)
    self.assertEqual(upload_calls[1].args[1], portrait_drawing_gcs_uri)
    self.assertEqual(upload_calls[2].args[1], portrait_desk_gcs_uri)
    self.assertEqual(upload_calls[3].args[1], portrait_corkboard_gcs_uri)

    # Metadata updated with new URLs
    mock_storage.get_final_image_url.assert_any_call(landscape_gcs_uri,
                                                     width=2048)
    mock_storage.get_final_image_url.assert_any_call(portrait_drawing_gcs_uri,
                                                     width=1024)
    mock_storage.get_final_image_url.assert_any_call(portrait_desk_gcs_uri,
                                                     width=1024)
    mock_storage.get_final_image_url.assert_any_call(
      portrait_corkboard_gcs_uri, width=1024)
    mock_metadata_doc.set.assert_called_once()


if __name__ == '__main__':
  unittest.main()
