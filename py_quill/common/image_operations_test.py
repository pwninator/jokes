"""Unit tests for image_operations module."""

from __future__ import annotations

import datetime as std_datetime
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
import zipfile

from common import image_operations, models
from PIL import Image
from services import image_editor


def _create_image_bytes(
    color: str,
    size: tuple[int, int] = (1024, 1024),
) -> bytes:
  """Create dummy PNG image bytes of the given color and size."""
  pil_image = Image.new('RGB', size, color=color)
  buffer = BytesIO()
  pil_image.save(buffer, format='PNG')
  return buffer.getvalue()


def _make_fake_image_model(
  *,
  gcs_uri: str,
  url: str,
  model_thought: str | None = None,
) -> SimpleNamespace:
  """Create a minimal image-like object for tests."""
  return SimpleNamespace(
    gcs_uri=gcs_uri,
    url=url,
    model_thought=model_thought,
    generation_metadata=models.GenerationMetadata(),
  )


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

  @patch('common.image_operations.generate_book_pages_with_nano_banana_pro')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_book_pages_success(self, mock_storage, mock_firestore,
                                     mock_generate_pages):
    mock_joke = SimpleNamespace(
      key='joke123',
      setup_image_url='https://cdn.example.com/setup.png',
      punchline_image_url='https://cdn.example.com/punchline.png',
      setup_image_description='setup desc',
      punchline_image_description='punchline desc',
    )
    mock_joke.generation_metadata = models.GenerationMetadata()
    mock_firestore.get_punny_joke.return_value = mock_joke
    mock_firestore.update_punny_joke = MagicMock()

    mock_firestore_db = MagicMock()
    mock_metadata_doc = MagicMock()
    (mock_firestore_db.collection.return_value.document.return_value.
     collection.return_value.document.return_value) = mock_metadata_doc
    mock_firestore.db.return_value = mock_firestore_db

    metadata_snapshot = MagicMock()
    metadata_snapshot.exists = False
    mock_metadata_doc.get.return_value = metadata_snapshot

    def _extract(uri):
      if uri == 'https://cdn.example.com/setup.png':
        return 'gs://bucket/setup.png'
      if uri == 'https://cdn.example.com/punchline.png':
        return 'gs://bucket/punchline.png'
      if uri == image_operations._BOOK_PAGE_STYLE_REFERENCE_IMAGE_URI:
        return 'gs://bucket/style.png'
      raise AssertionError(f'Unexpected URI: {uri}')

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri == 'gs://bucket/setup.png':
        return _make_image('red')
      if gcs_uri == 'gs://bucket/punchline.png':
        return _make_image('blue')
      if gcs_uri == 'gs://bucket/style.png':
        return _make_image('green')
      raise AssertionError(f'Unexpected GCS URI: {gcs_uri}')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

    generated_setup_uri = 'gs://generated/nano_setup.png'
    generated_punch_uri = 'gs://generated/nano_punch.png'
    simple_setup_uri = 'gs://generated/simple_setup.png'
    simple_punch_uri = 'gs://generated/simple_punch.png'
    generated_setup_url = 'https://cdn.example.com/book_page_setup.jpg'
    generated_punchline_url = 'https://cdn.example.com/book_page_punchline.jpg'
    simple_setup_url = 'https://cdn.example.com/simple_setup.png'
    simple_punchline_url = 'https://cdn.example.com/simple_punchline.png'

    def _stub_generation(**kwargs):
      self.assertEqual(kwargs['output_file_name_base'], 'joke123_book_page')
      return SimpleNamespace(
        simple_setup_image=_make_fake_image_model(
          gcs_uri=simple_setup_uri,
          url=simple_setup_url,
        ),
        simple_punchline_image=_make_fake_image_model(
          gcs_uri=simple_punch_uri,
          url=simple_punchline_url,
        ),
        generated_setup_image=_make_fake_image_model(
          gcs_uri=generated_setup_uri,
          url=generated_setup_url,
          model_thought='setup-thought',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=generated_punchline_url,
          model_thought='punchline-thought',
        ),
      )

    mock_generate_pages.side_effect = _stub_generation

    setup_image, punchline_image = (
      image_operations.generate_and_populate_book_pages('joke123'))

    self.assertEqual(setup_image.url, generated_setup_url)
    self.assertEqual(punchline_image.url, generated_punchline_url)
    mock_generate_pages.assert_called_once()
    mock_firestore.get_punny_joke.assert_called_once_with('joke123')
    mock_metadata_doc.get.assert_called_once()
    mock_firestore.update_punny_joke.assert_called_once()

    update_call = mock_firestore.update_punny_joke.call_args
    self.assertEqual(update_call.args[0], 'joke123')
    update_kwargs = update_call.kwargs
    self.assertIn('generation_metadata', update_kwargs['update_data'])
    self.assertEqual(
      update_kwargs['update_metadata'], {
        'book_page_simple_setup_image_url':
        'https://cdn.example.com/simple_setup.png',
        'book_page_simple_punchline_image_url':
        'https://cdn.example.com/simple_punchline.png',
        'book_page_setup_image_model_thought':
        'setup-thought',
        'book_page_punchline_image_model_thought':
        'punchline-thought',
        'book_page_setup_image_url':
        'https://cdn.example.com/book_page_setup.jpg',
        'book_page_punchline_image_url':
        'https://cdn.example.com/book_page_punchline.jpg',
        'all_book_page_setup_image_urls': [
          'https://cdn.example.com/book_page_setup.jpg',
        ],
        'all_book_page_punchline_image_urls': [
          'https://cdn.example.com/book_page_punchline.jpg',
        ],
      })

    mock_metadata_doc.set.assert_not_called()

  @patch('common.image_operations.firestore.get_punny_joke', return_value=None)
  def test_create_book_pages_missing_joke(self, mock_get_joke):
    with self.assertRaisesRegex(ValueError, 'Joke not found'):
      image_operations.generate_and_populate_book_pages('missing-joke')
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
      image_operations.generate_and_populate_book_pages('joke123')

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
    mock_firestore.update_punny_joke = MagicMock()

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

    result = image_operations.generate_and_populate_book_pages(
      'jokeABC',
      overwrite=False,
    )

    self.assertEqual(result, (
      'https://cdn.example.com/existing_setup.jpg',
      'https://cdn.example.com/existing_punchline.jpg',
    ))
    mock_firestore.update_punny_joke.assert_not_called()
    mock_storage.extract_gcs_uri_from_image_url.assert_not_called()
    mock_storage.download_image_from_gcs.assert_not_called()
    mock_storage.upload_bytes_to_gcs.assert_not_called()
    mock_storage.get_public_url.assert_not_called()
    mock_metadata_doc.set.assert_not_called()
    mock_metadata_doc.get.assert_called_once()
    mock_firestore.get_punny_joke.assert_called_once_with('jokeABC')

  @patch('common.image_operations.generate_book_pages_with_nano_banana_pro')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_book_pages_overwrite_true_generates_new(
      self, mock_storage, mock_firestore, mock_generate_pages):
    mock_joke = SimpleNamespace(
      key='jokeXYZ',
      setup_image_url='https://cdn.example.com/setup.png',
      punchline_image_url='https://cdn.example.com/punchline.png',
      setup_image_description='setup desc',
      punchline_image_description='punchline desc',
    )
    mock_joke.generation_metadata = models.GenerationMetadata()
    mock_firestore.get_punny_joke.return_value = mock_joke
    mock_firestore.update_punny_joke = MagicMock()

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
      if uri == 'https://cdn.example.com/setup.png':
        return 'gs://bucket/setup.png'
      if uri == 'https://cdn.example.com/punchline.png':
        return 'gs://bucket/punchline.png'
      if uri == image_operations._BOOK_PAGE_STYLE_REFERENCE_IMAGE_URI:
        return 'gs://bucket/style.png'
      raise AssertionError(f'Unexpected URI: {uri}')

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _make_image(
      color: str, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
      return Image.open(BytesIO(_create_image_bytes(color, size)))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri == 'gs://bucket/setup.png':
        return _make_image('red')
      if gcs_uri == 'gs://bucket/punchline.png':
        return _make_image('blue')
      if gcs_uri == 'gs://bucket/style.png':
        return _make_image('green')
      raise AssertionError(f'Unexpected GCS URI: {gcs_uri}')

    mock_storage.download_image_from_gcs.side_effect = _download_image_side_effect

    generated_setup_uri = 'gs://generated/nano_setup.png'
    generated_punch_uri = 'gs://generated/nano_punch.png'
    simple_setup_uri = 'gs://generated/simple_setup.png'
    simple_punch_uri = 'gs://generated/simple_punch.png'
    new_setup_url = 'https://cdn.example.com/new_setup.jpg'
    new_punchline_url = 'https://cdn.example.com/new_punchline.jpg'
    simple_setup_url = 'https://cdn.example.com/simple_setup.png'
    simple_punchline_url = 'https://cdn.example.com/simple_punchline.png'

    def _stub_generation(**kwargs):
      self.assertEqual(kwargs['output_file_name_base'], 'jokeXYZ_book_page')
      return SimpleNamespace(
        simple_setup_image=_make_fake_image_model(
          gcs_uri=simple_setup_uri,
          url=simple_setup_url,
        ),
        simple_punchline_image=_make_fake_image_model(
          gcs_uri=simple_punch_uri,
          url=simple_punchline_url,
        ),
        generated_setup_image=_make_fake_image_model(
          gcs_uri=generated_setup_uri,
          url=new_setup_url,
          model_thought='setup-thought',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=new_punchline_url,
          model_thought='punchline-thought',
        ),
      )

    mock_generate_pages.side_effect = _stub_generation

    setup_image, punchline_image = (
      image_operations.generate_and_populate_book_pages(
        'jokeXYZ',
        overwrite=True,
      ))

    self.assertEqual(setup_image.url, new_setup_url)
    self.assertEqual(punchline_image.url, new_punchline_url)
    mock_generate_pages.assert_called_once()
    mock_firestore.update_punny_joke.assert_called_once()
    update_call = mock_firestore.update_punny_joke.call_args
    update_kwargs = update_call.kwargs
    self.assertEqual(
      update_kwargs['update_metadata'], {
        'book_page_simple_setup_image_url':
        'https://cdn.example.com/simple_setup.png',
        'book_page_simple_punchline_image_url':
        'https://cdn.example.com/simple_punchline.png',
        'book_page_setup_image_model_thought':
        'setup-thought',
        'book_page_punchline_image_model_thought':
        'punchline-thought',
        'book_page_setup_image_url':
        'https://cdn.example.com/new_setup.jpg',
        'book_page_punchline_image_url':
        'https://cdn.example.com/new_punchline.jpg',
        'all_book_page_setup_image_urls': [
          'https://cdn.example.com/existing_setup.jpg',
          'https://cdn.example.com/new_setup.jpg',
        ],
        'all_book_page_punchline_image_urls': [
          'https://cdn.example.com/existing_punchline.jpg',
          'https://cdn.example.com/new_punchline.jpg',
        ],
      })


class ZipJokePageImagesTest(unittest.TestCase):
  """Tests for zip_joke_page_images function."""

  @patch('common.image_operations._convert_for_print_kdp')
  @patch('common.image_operations.cloud_storage.get_public_url')
  @patch('common.image_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.image_operations.cloud_storage.download_image_from_gcs')
  @patch(
    'common.image_operations.cloud_storage.extract_gcs_uri_from_image_url')
  @patch('common.image_operations.firestore')
  def test_zip_joke_page_images_builds_zip_and_uploads(
    self,
    mock_firestore,
    mock_extract_gcs_uri,
    mock_download_image,
    mock_upload_bytes,
    mock_get_public_url,
    mock_convert_for_print,
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

    def download_side_effect(resource):
      if resource == setup_url:
        return Image.new('RGB', (10, 10), 'red')
      if resource == punch_url:
        return Image.new('RGB', (10, 10), 'blue')
      raise ValueError(f"Unexpected download request {resource}")

    mock_download_image.side_effect = download_side_effect

    mock_convert_for_print.side_effect = [b'setup-kdp', b'punchline-kdp']

    mock_get_public_url.return_value = 'https://cdn.example.com/book.zip'

    # Act
    result_url = image_operations.zip_joke_page_images_for_kdp(joke_ids)

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
        '003_joke1_setup.jpg',
        '004_joke1_punchline.jpg',
      ])

      # Intro page exists and is non-empty
      intro_bytes = zip_file.read('002_intro.jpg')
      self.assertIsInstance(intro_bytes, (bytes, bytearray))
      self.assertGreater(len(intro_bytes), 0)

      self.assertEqual(zip_file.read('003_joke1_setup.jpg'), b'setup-kdp')
      self.assertEqual(zip_file.read('004_joke1_punchline.jpg'),
                       b'punchline-kdp')


if __name__ == '__main__':
  unittest.main()
