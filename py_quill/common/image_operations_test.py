"""Unit tests for image_operations module."""

from __future__ import annotations

import datetime as std_datetime
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
import zipfile

from common import image_operations
from PIL import Image
from services import image_client, image_editor


def _create_image_bytes(
    color: str,
    size: tuple[int, int] = (1024, 1024),
) -> bytes:
  """Create dummy PNG image bytes of the given color and size."""
  pil_image = Image.new('RGB', size, color=color)
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

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri in (
          image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI,
          image_operations._AD_BACKGROUND_SQUARE_DESK_URI,
          image_operations._AD_BACKGROUND_SQUARE_CORKBOARD_URI,
      ):
        return _make_image('white', (1024, 1280))
      if gcs_uri.endswith('setup.png'):
        return _make_image('red')
      return _make_image('blue')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

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
    mock_storage.download_image_from_gcs.assert_not_called()
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
    mock_storage.download_image_from_gcs.return_value = Image.open(
      BytesIO(bg_buffer.getvalue()))

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

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri in (
          image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI,
          image_operations._AD_BACKGROUND_SQUARE_DESK_URI,
          image_operations._AD_BACKGROUND_SQUARE_CORKBOARD_URI,
      ):
        return _make_image('white', (1024, 1280))
      if gcs_uri.endswith('setup.png'):
        return _make_image('red')
      return _make_image('blue')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

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


class CreateBookPagesTest(unittest.TestCase):
  """Tests for create_book_pages function."""

  @patch('common.image_operations.image_client.get_client')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.datetime.datetime')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_book_pages_success(self, mock_datetime, mock_storage,
                                     mock_firestore, mock_get_client):
    fixed_dt = std_datetime.datetime(2025, 3, 4, 5, 6, 7, 8000)
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

    def _extract(uri):
      return f'gs://bucket/{uri.split(' / ')[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    setup_outpaint_uri = 'gs://generated/setup_outpaint.png'
    punchline_outpaint_uri = 'gs://generated/punchline_outpaint.png'
    setup_upscaled_uri = 'gs://generated/setup_outpaint_upscale_x2.png'
    punchline_upscaled_uri = 'gs://generated/punchline_outpaint_upscale_x2.png'

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri.endswith('setup.png'):
        return _make_image('red')
      if gcs_uri.endswith('punchline.png'):
        return _make_image('blue')
      if gcs_uri == setup_outpaint_uri:
        return _make_image('red', (1150, 1174))
      if gcs_uri == punchline_outpaint_uri:
        return _make_image('blue', (1150, 1174))
      if gcs_uri == setup_upscaled_uri:
        return _make_image('red', (2300, 2348))
      if gcs_uri == punchline_upscaled_uri:
        return _make_image('blue', (2300, 2348))
      raise AssertionError(f'Unexpected GCS URI: {gcs_uri}')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

    expected_timestamp = fixed_dt.strftime('%Y%m%d_%H%M%S_%f')
    setup_gcs_uri = (
      f'gs://test-bucket/joke123_book_page_setup_{expected_timestamp}.jpg')
    punchline_gcs_uri = (
      f'gs://test-bucket/joke123_book_page_punchline_{expected_timestamp}.jpg')

    mock_storage.get_public_url.side_effect = [
      'https://cdn.example.com/book_page_setup.jpg',
      'https://cdn.example.com/book_page_punchline.jpg',
    ]

    outpaint_calls = []
    upscale_calls = []

    def _make_outpaint_client(page_label: str):

      def _outpaint_image(**kwargs):
        outpaint_calls.append((page_label, kwargs))
        return SimpleNamespace(gcs_uri=(setup_outpaint_uri if page_label ==
                                        'setup' else punchline_outpaint_uri))

      return SimpleNamespace(outpaint_image=_outpaint_image)

    def _make_upscale_client(page_label: str):

      def _upscale_image(*args, **kwargs):
        upscale_calls.append((page_label, kwargs))
        return SimpleNamespace(
          gcs_uri=(setup_outpaint_uri
                   if page_label == 'setup' else punchline_outpaint_uri),
          gcs_uri_upscaled=(setup_upscaled_uri if page_label == 'setup' else
                            punchline_upscaled_uri),
        )

      return SimpleNamespace(upscale_image=_upscale_image)

    def _get_client_side_effect(label, model, file_name_base, **_kwargs):
      self.assertEqual(label, 'book_page_generation')
      if model == image_client.ImageModel.DUMMY_OUTPAINTER:
        page_label = 'setup' if 'setup' in file_name_base else 'punchline'
        return _make_outpaint_client(page_label)
      if model == image_client.ImageModel.IMAGEN_4_UPSCALE:
        page_label = 'setup' if 'setup' in file_name_base else 'punchline'
        return _make_upscale_client(page_label)
      raise AssertionError(f'Unexpected model {model}')

    mock_get_client.side_effect = _get_client_side_effect

    editor = image_editor.ImageEditor()

    result = image_operations.create_book_pages(
      'joke123',
      use_nano_banana_pro=False,
      image_editor_instance=editor,
    )

    self.assertEqual(result, (
      'https://cdn.example.com/book_page_setup.jpg',
      'https://cdn.example.com/book_page_punchline.jpg',
    ))
    mock_firestore.get_punny_joke.assert_called_once_with('joke123')
    self.assertEqual(len(outpaint_calls), 2)
    self.assertEqual(len(upscale_calls), 2)

    # Verify margins include 5% base plus bleed (38px after scaling).
    setup_margins = outpaint_calls[0][1] if outpaint_calls[0][
      0] == 'setup' else outpaint_calls[1][1]
    punchline_margins = outpaint_calls[0][1] if outpaint_calls[0][
      0] == 'punchline' else outpaint_calls[1][1]

    self.assertEqual(setup_margins['top'], 75)
    self.assertEqual(setup_margins['bottom'], 75)
    self.assertEqual(setup_margins['left'], 51)
    self.assertEqual(setup_margins['right'], 75)

    self.assertEqual(punchline_margins['top'], 75)
    self.assertEqual(punchline_margins['bottom'], 75)
    self.assertEqual(punchline_margins['left'], 75)
    self.assertEqual(punchline_margins['right'], 51)

    for page_label, kwargs in upscale_calls:
      self.assertEqual(kwargs['upscale_factor'], 'x2')
      self.assertEqual(kwargs['mime_type'], 'image/png')
      self.assertIsNone(kwargs['compression_quality'])
      expected_uri = (setup_outpaint_uri
                      if page_label == 'setup' else punchline_outpaint_uri)
      self.assertEqual(kwargs['gcs_uri'], expected_uri)
      self.assertFalse(kwargs.get('save_to_firestore', True))

    self.assertEqual(mock_storage.upload_bytes_to_gcs.call_count, 2)
    upload_calls = mock_storage.upload_bytes_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].args[1], setup_gcs_uri)
    self.assertEqual(upload_calls[1].args[1], punchline_gcs_uri)
    for call in upload_calls:
      self.assertIsInstance(call.args[0], (bytes, bytearray))
      self.assertEqual(call.args[2], 'image/jpeg')

      img = Image.open(BytesIO(call.args[0]))
      self.assertEqual(img.mode, 'CMYK')
      self.assertEqual(img.format, 'JPEG')
      self.assertEqual(img.size[1], 1876)
      self.assertEqual(img.size[0], 1838)
      # Verify print DPI is preserved at 300x300.
      self.assertEqual(img.info.get('dpi'), (300, 300))

    mock_storage.get_public_url.assert_any_call(setup_gcs_uri)
    mock_storage.get_public_url.assert_any_call(punchline_gcs_uri)

    mock_metadata_doc.set.assert_called_once_with(
      {
        'book_page_setup_image_url':
        'https://cdn.example.com/book_page_setup.jpg',
        'book_page_punchline_image_url':
        'https://cdn.example.com/book_page_punchline.jpg',
      },
      merge=True)
    mock_metadata_doc.get.assert_called_once()

  @patch('common.image_operations.firestore.get_punny_joke', return_value=None)
  def test_create_book_pages_missing_joke(self, mock_get_joke):
    with self.assertRaisesRegex(ValueError, 'Joke not found'):
      image_operations.create_book_pages('missing-joke')
    mock_get_joke.assert_called_once_with('missing-joke')

  @patch('common.image_operations.firestore')
  def test_create_book_pages_missing_images(self, mock_firestore):
    mock_joke = SimpleNamespace(
      key='joke123',
      setup_image_url=None,
      punchline_image_url=None,
    )
    mock_firestore.get_punny_joke.return_value = mock_joke

    with self.assertRaisesRegex(ValueError, 'does not have image URLs'):
      image_operations.create_book_pages('joke123')

    mock_firestore.get_punny_joke.assert_called_once_with('joke123')

  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.firestore')
  def test_create_book_pages_returns_existing_metadata(self, mock_firestore,
                                                       mock_storage):
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
      'book_page_setup_image_url':
      'https://cdn.example.com/existing_setup.jpg',
      'book_page_punchline_image_url':
      'https://cdn.example.com/existing_punchline.jpg',
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    mock_editor = Mock(spec=image_editor.ImageEditor)

    result = image_operations.create_book_pages(
      'jokeABC',
      use_nano_banana_pro=False,
      image_editor_instance=mock_editor,
      overwrite=False,
    )

    self.assertEqual(result, (
      'https://cdn.example.com/existing_setup.jpg',
      'https://cdn.example.com/existing_punchline.jpg',
    ))
    mock_editor.scale_image.assert_not_called()
    mock_editor.crop_image.assert_not_called()
    mock_storage.extract_gcs_uri_from_image_url.assert_not_called()
    mock_storage.download_image_from_gcs.assert_not_called()
    mock_storage.upload_bytes_to_gcs.assert_not_called()
    mock_storage.get_public_url.assert_not_called()
    mock_metadata_doc.set.assert_not_called()
    mock_metadata_doc.get.assert_called_once()
    mock_firestore.get_punny_joke.assert_called_once_with('jokeABC')

  @patch('common.image_operations.image_client.get_client')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.datetime.datetime')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_book_pages_overwrite_true_generates_new(
      self, mock_datetime, mock_storage, mock_firestore, mock_get_client):
    fixed_dt = std_datetime.datetime(2025, 4, 5, 6, 7, 8, 9000)
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
      'book_page_setup_image_url':
      'https://cdn.example.com/existing_setup.jpg',
      'book_page_punchline_image_url':
      'https://cdn.example.com/existing_punchline.jpg',
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    def _extract(uri):
      return f'gs://bucket/{uri.split(' / ')[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    setup_outpaint_uri = 'gs://generated/setup_outpaint.png'
    punchline_outpaint_uri = 'gs://generated/punchline_outpaint.png'
    setup_upscaled_uri = 'gs://generated/setup_outpaint_upscale_x2.png'
    punchline_upscaled_uri = 'gs://generated/punchline_outpaint_upscale_x2.png'

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri.endswith('setup.png'):
        return _make_image('red')
      if gcs_uri.endswith('punchline.png'):
        return _make_image('blue')
      if gcs_uri == setup_outpaint_uri:
        return _make_image('red', (1150, 1174))
      if gcs_uri == punchline_outpaint_uri:
        return _make_image('blue', (1150, 1174))
      if gcs_uri == setup_upscaled_uri:
        return _make_image('red', (2300, 2348))
      if gcs_uri == punchline_upscaled_uri:
        return _make_image('blue', (2300, 2348))
      raise AssertionError(f'Unexpected GCS URI: {gcs_uri}')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

    expected_timestamp = fixed_dt.strftime('%Y%m%d_%H%M%S_%f')
    setup_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_book_page_setup_{expected_timestamp}.jpg')
    punchline_gcs_uri = (
      f'gs://test-bucket/jokeXYZ_book_page_punchline_{expected_timestamp}.jpg')

    mock_storage.get_public_url.side_effect = [
      'https://cdn.example.com/new_setup.jpg',
      'https://cdn.example.com/new_punchline.jpg',
    ]

    def _make_outpaint_client(page_label: str):

      def _outpaint_image(**kwargs):
        return SimpleNamespace(gcs_uri=(setup_outpaint_uri if page_label ==
                                        'setup' else punchline_outpaint_uri))

      return SimpleNamespace(outpaint_image=_outpaint_image)

    def _make_upscale_client(page_label: str):

      def _upscale_image(*args, **kwargs):
        return SimpleNamespace(
          gcs_uri=(setup_outpaint_uri
                   if page_label == 'setup' else punchline_outpaint_uri),
          gcs_uri_upscaled=(setup_upscaled_uri if page_label == 'setup' else
                            punchline_upscaled_uri),
        )

      return SimpleNamespace(upscale_image=_upscale_image)

    def _get_client_side_effect(label, model, file_name_base, **_kwargs):
      if model == image_client.ImageModel.DUMMY_OUTPAINTER:
        page_label = 'setup' if 'setup' in file_name_base else 'punchline'
        return _make_outpaint_client(page_label)
      if model == image_client.ImageModel.IMAGEN_4_UPSCALE:
        page_label = 'setup' if 'setup' in file_name_base else 'punchline'
        return _make_upscale_client(page_label)
      raise AssertionError(f'Unexpected model {model}')

    mock_get_client.side_effect = _get_client_side_effect

    editor = image_editor.ImageEditor()

    result = image_operations.create_book_pages(
      'jokeXYZ',
      use_nano_banana_pro=False,
      image_editor_instance=editor,
      overwrite=True,
    )

    self.assertEqual(result, (
      'https://cdn.example.com/new_setup.jpg',
      'https://cdn.example.com/new_punchline.jpg',
    ))

    self.assertEqual(mock_storage.upload_bytes_to_gcs.call_count, 2)
    upload_calls = mock_storage.upload_bytes_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].args[1], setup_gcs_uri)
    self.assertEqual(upload_calls[1].args[1], punchline_gcs_uri)

    mock_storage.get_public_url.assert_any_call(setup_gcs_uri)
    mock_storage.get_public_url.assert_any_call(punchline_gcs_uri)
    mock_metadata_doc.set.assert_called_once()


class ZipJokePageImagesTest(unittest.TestCase):
  """Tests for zip_joke_page_images function."""

  @patch('common.image_operations.cloud_storage.get_public_url')
  @patch('common.image_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.image_operations.cloud_storage.download_bytes_from_gcs')
  @patch(
    'common.image_operations.cloud_storage.extract_gcs_uri_from_image_url')
  @patch('common.image_operations.firestore')
  def test_zip_joke_page_images_builds_zip_and_uploads(
    self,
    mock_firestore,
    mock_extract_gcs_uri,
    mock_download_bytes,
    mock_upload_bytes,
    mock_get_public_url,
  ):
    """zip_joke_page_images should upload a ZIP and return its public URL."""
    joke_ids = ['joke1']

    # Firestore metadata for book pages
    mock_db = MagicMock()
    mock_firestore.db.return_value = mock_db

    jokes_collection = MagicMock()

    def collection_side_effect(name):
      if name == "jokes":
        return jokes_collection
      return MagicMock()

    mock_db.collection.side_effect = collection_side_effect

    mock_joke_doc = MagicMock()
    mock_joke_doc.exists = True

    metadata_doc = MagicMock()
    metadata_snapshot = MagicMock()
    metadata_snapshot.exists = True
    setup_url = "http://example.com/setup1.jpg"
    punch_url = "http://example.com/punch1.png"
    metadata_snapshot.to_dict.return_value = {
      "book_page_setup_image_url": setup_url,
      "book_page_punchline_image_url": punch_url,
    }
    metadata_doc.get.return_value = metadata_snapshot

    def jokes_document_side_effect(doc_id):
      joke_ref = MagicMock()
      if doc_id == "joke1":
        joke_ref.get.return_value = mock_joke_doc
        metadata_collection = MagicMock()
        metadata_collection.document.return_value = metadata_doc
        joke_ref.collection.return_value = metadata_collection
      return joke_ref

    jokes_collection.document.side_effect = jokes_document_side_effect

    # Cloud Storage helpers
    def extract_side_effect(url):
      if url == setup_url:
        return "gs://bucket/setup1.jpg"
      if url == punch_url:
        return "gs://bucket/punch1.png"
      raise ValueError(f"Unexpected URL {url}")

    mock_extract_gcs_uri.side_effect = extract_side_effect

    setup_image = Image.new('RGB', (10, 10), 'red')
    punch_image = Image.new('RGB', (10, 10), 'blue')
    setup_buffer = BytesIO()
    punch_buffer = BytesIO()
    setup_image.save(setup_buffer, format='JPEG')
    punch_image.save(punch_buffer, format='JPEG')
    setup_bytes = setup_buffer.getvalue()
    punch_bytes = punch_buffer.getvalue()

    def download_side_effect(gcs_uri):
      if gcs_uri == "gs://bucket/setup1.jpg":
        return setup_bytes
      if gcs_uri == "gs://bucket/punch1.png":
        return punch_bytes
      raise ValueError(f"Unexpected GCS URI {gcs_uri}")

    mock_download_bytes.side_effect = download_side_effect

    mock_get_public_url.return_value = 'https://cdn.example.com/book.zip'

    # Act
    result_url = image_operations.zip_joke_page_images(joke_ids)

    # Assert URL is returned
    self.assertEqual(result_url, 'https://cdn.example.com/book.zip')

    # One ZIP upload with application/zip content type
    mock_upload_bytes.assert_called_once()
    upload_args, upload_kwargs = mock_upload_bytes.call_args
    self.assertIsInstance(upload_args[0], (bytes, bytearray))
    self.assertEqual(upload_args[2], 'application/zip')
    self.assertEqual(upload_kwargs, {})

    # Inspect ZIP structure
    zip_bytes = upload_args[0]
    with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zip_file:
      names = sorted(zip_file.namelist())
      self.assertEqual(names, [
        '002_intro.jpg',
        '003_setup1.jpg',
        '004_punch1.png',
      ])

      # Intro page exists and is non-empty
      intro_bytes = zip_file.read('002_intro.jpg')
      self.assertIsInstance(intro_bytes, (bytes, bytearray))
      self.assertGreater(len(intro_bytes), 0)

      self.assertEqual(zip_file.read('003_setup1.jpg'), setup_bytes)
      self.assertEqual(zip_file.read('004_punch1.png'), punch_bytes)


if __name__ == '__main__':
  unittest.main()
