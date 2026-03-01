"""Unit tests for image_operations module."""

from __future__ import annotations

import datetime as std_datetime
import hashlib
import math
import unittest
import zipfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

from agents import constants
from common import amazon_redirect, image_operations, joke_notes_sheet_operations, models
from PIL import Image, ImageFont
from services import image_editor, pdf_client

_TEST_LANDSCAPE_PANEL_WIDTH = image_operations._AD_LANDSCAPE_CANVAS_WIDTH // 2
_TEST_LANDSCAPE_PANEL_HEIGHT = image_operations._AD_LANDSCAPE_CANVAS_HEIGHT


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
  final_prompt: str | None = None,
  original_prompt: str | None = None,
) -> SimpleNamespace:
  """Create a minimal image-like object for tests."""
  return SimpleNamespace(
    gcs_uri=gcs_uri,
    url=url,
    model_thought=model_thought,
    generation_metadata=models.GenerationMetadata(),
    final_prompt=final_prompt,
    original_prompt=original_prompt,
  )


class RecordingImageEditor(image_editor.ImageEditor):
  """ImageEditor subclass that records paste calls."""

  def __init__(self):
    super().__init__()
    self.create_calls: list[tuple[int, int]] = []
    self.paste_calls: list[tuple[int, int]] = []
    self.scale_calls: list[tuple[int, int]] = []

  def create_blank_image(self, width: int, height: int, color=(255, 255, 255)):
    self.create_calls.append((width, height))
    return super().create_blank_image(width, height, color)

  def scale_image(
    self,
    image: Image.Image,
    scale_factor: float | None = None,
    new_width: int | None = None,
    new_height: int | None = None,
  ) -> Image.Image:
    if new_width is not None and new_height is not None:
      self.scale_calls.append((new_width, new_height))
    return super().scale_image(
      image,
      scale_factor=scale_factor,
      new_width=new_width,
      new_height=new_height,
    )

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
    mock_storage.upload_image_to_gcs.side_effect = (
      lambda _image, _base, _ext, *, gcs_uri: (gcs_uri, b""))

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
    self.assertEqual(editor.create_calls, [(
      image_operations._AD_LANDSCAPE_CANVAS_WIDTH,
      image_operations._AD_LANDSCAPE_CANVAS_HEIGHT,
    )])
    # Verify landscape paste operations: setup and punchline side-by-side
    landscape_pastes = editor.paste_calls[:2]
    self.assertEqual(len(landscape_pastes), 2)
    self.assertEqual(landscape_pastes[0][2], (
      _TEST_LANDSCAPE_PANEL_WIDTH,
      _TEST_LANDSCAPE_PANEL_HEIGHT,
    ))  # setup image size
    self.assertEqual(landscape_pastes[1][2], (
      _TEST_LANDSCAPE_PANEL_WIDTH,
      _TEST_LANDSCAPE_PANEL_HEIGHT,
    ))  # punchline image size
    # Portrait pastes: should have 3 portrait variations * 2 images each (setup + punchline)
    # Total pastes: 2 (landscape) + 6 (portrait) = 8
    self.assertEqual(len(editor.paste_calls), 8)

    # Scale calls include 2 landscape panel resizes + 6 square resizes
    expected_scale_calls = [
      (_TEST_LANDSCAPE_PANEL_WIDTH, _TEST_LANDSCAPE_PANEL_HEIGHT),
      (_TEST_LANDSCAPE_PANEL_WIDTH, _TEST_LANDSCAPE_PANEL_HEIGHT),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
      (image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
       image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX),
    ]
    self.assertCountEqual(editor.scale_calls, expected_scale_calls)

    self.assertEqual(mock_storage.upload_image_to_gcs.call_count, 4)
    upload_calls = mock_storage.upload_image_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].kwargs["gcs_uri"], landscape_gcs_uri)
    self.assertEqual(upload_calls[1].kwargs["gcs_uri"],
                     portrait_drawing_gcs_uri)
    self.assertEqual(upload_calls[2].kwargs["gcs_uri"], portrait_desk_gcs_uri)
    self.assertEqual(upload_calls[3].kwargs["gcs_uri"],
                     portrait_corkboard_gcs_uri)
    for call in upload_calls:
      self.assertIsInstance(call.args[0], Image.Image)
      self.assertEqual(call.args[2], "png")
      self.assertIn("gcs_uri", call.kwargs)

    mock_storage.get_final_image_url.assert_any_call(
      landscape_gcs_uri,
      width=image_operations._AD_LANDSCAPE_CANVAS_WIDTH,
    )
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

    image_out, width = image_operations._compose_square_drawing_ad_image(
      editor,
      setup,
      punchline,
      background_uri=image_operations._AD_BACKGROUND_SQUARE_DRAWING_URI)

    self.assertIsInstance(image_out, Image.Image)
    self.assertEqual(width, 1024)
    self.assertEqual(editor.scale_calls, [
      (
        image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
        image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
      ),
      (
        image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
        image_operations._AD_SQUARE_JOKE_IMAGE_SIZE_PX,
      ),
    ])
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
      'ad_creative_square_drawing':
      'https://cdn.example.com/existing_portrait_drawing.png',
      'ad_creative_square_desk':
      'https://cdn.example.com/existing_portrait_desk.png',
      'ad_creative_square_corkboard':
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
    mock_storage.upload_image_to_gcs.side_effect = (
      lambda _image, _base, _ext, *, gcs_uri: (gcs_uri, b""))

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
    self.assertEqual(mock_storage.upload_image_to_gcs.call_count, 4)
    upload_calls = mock_storage.upload_image_to_gcs.call_args_list
    self.assertEqual(upload_calls[0].kwargs["gcs_uri"], landscape_gcs_uri)
    self.assertEqual(upload_calls[1].kwargs["gcs_uri"],
                     portrait_drawing_gcs_uri)
    self.assertEqual(upload_calls[2].kwargs["gcs_uri"], portrait_desk_gcs_uri)
    self.assertEqual(upload_calls[3].kwargs["gcs_uri"],
                     portrait_corkboard_gcs_uri)

    # Metadata updated with new URLs
    mock_storage.get_final_image_url.assert_any_call(
      landscape_gcs_uri,
      width=image_operations._AD_LANDSCAPE_CANVAS_WIDTH,
    )
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
      # Handle style reference images which might be passed in
      if uri in constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS:
        return f'gs://bucket/{uri.split("/")[-1]}'
      raise AssertionError(f'Unexpected URI: {uri}')

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

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
      self.assertIsInstance(kwargs['setup_image'], models.Image)
      self.assertEqual(kwargs['setup_image'].url,
                       'https://cdn.example.com/setup.png')
      self.assertIsInstance(kwargs['punchline_image'], models.Image)
      self.assertEqual(kwargs['punchline_image'].url,
                       'https://cdn.example.com/punchline.png')

      style_refs = kwargs['style_reference_images']
      self.assertEqual(len(style_refs),
                       len(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS))
      for idx, img in enumerate(style_refs):
        self.assertIsInstance(img, models.Image)
        self.assertEqual(img.url,
                         constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[idx])

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
          final_prompt='final-setup-prompt',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=generated_punchline_url,
          model_thought='punchline-thought',
          final_prompt='final-punchline-prompt',
        ),
        setup_prompt='final-setup-prompt',
        punchline_prompt='final-punchline-prompt',
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
        'book_page_setup_image_prompt':
        'final-setup-prompt',
        'book_page_punchline_image_prompt':
        'final-punchline-prompt',
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
        'book_page_ready':
        False,
      })

    # Verify we didn't download images
    mock_storage.download_image_from_gcs.assert_not_called()

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

    self.assertEqual(result[0].url,
                     'https://cdn.example.com/existing_setup.jpg')
    self.assertEqual(result[1].url,
                     'https://cdn.example.com/existing_punchline.jpg')
    mock_firestore.update_punny_joke.assert_not_called()
    self.assertEqual(mock_storage.extract_gcs_uri_from_image_url.call_count, 2)
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
      if uri in constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS:
        return f'gs://bucket/{uri.split("/")[-1]}'
      raise AssertionError(f'Unexpected URI: {uri}')

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

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
      self.assertIsInstance(kwargs['setup_image'], models.Image)
      self.assertIsInstance(kwargs['punchline_image'], models.Image)
      self.assertTrue(kwargs['add_print_margins'])

      style_refs = kwargs['style_reference_images']
      self.assertEqual(len(style_refs),
                       len(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS))

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
          final_prompt='new-setup-prompt',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=new_punchline_url,
          model_thought='punchline-thought',
          final_prompt='new-punchline-prompt',
        ),
        setup_prompt='new-setup-prompt',
        punchline_prompt='new-punchline-prompt',
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
        'book_page_setup_image_prompt':
        'new-setup-prompt',
        'book_page_punchline_image_prompt':
        'new-punchline-prompt',
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
        'book_page_ready':
        False,
      })
    mock_storage.download_image_from_gcs.assert_not_called()

  @patch('common.image_operations.generate_book_pages_style_update')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_book_pages_style_update_branch(self, mock_storage,
                                                 mock_firestore,
                                                 mock_style_generate):
    mock_joke = SimpleNamespace(
      key='jokeSTYLE',
      setup_text='Why did the burger run',
      punchline_text='Because it saw the fryer',
      setup_image_url='https://cdn.example.com/setup.png',
      punchline_image_url='https://cdn.example.com/punchline.png',
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
      return f"gs://bucket/{uri.split('/')[-1]}"

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    generated_setup_url = 'https://cdn.example.com/style_setup.png'
    generated_punchline_url = 'https://cdn.example.com/style_punchline.png'
    simple_setup_url = 'https://cdn.example.com/simple_setup.png'
    simple_punchline_url = 'https://cdn.example.com/simple_punchline.png'

    style_result = image_operations._BookPageGenerationResult(
      simple_setup_image=_make_fake_image_model(
        gcs_uri='gs://bucket/simple_setup.png', url=simple_setup_url),
      simple_punchline_image=_make_fake_image_model(
        gcs_uri='gs://bucket/simple_punchline.png', url=simple_punchline_url),
      generated_setup_image=_make_fake_image_model(
        gcs_uri='gs://bucket/style_setup.png',
        url=generated_setup_url,
        model_thought='style-setup',
        final_prompt='style-prompt',
      ),
      generated_punchline_image=_make_fake_image_model(
        gcs_uri='gs://bucket/style_punchline.png',
        url=generated_punchline_url,
        model_thought='style-punchline',
        final_prompt='style-prompt',
      ),
      setup_prompt='style-prompt',
      punchline_prompt='style-prompt',
    )

    mock_style_generate.return_value = style_result

    setup_image, punchline_image = (
      image_operations.generate_and_populate_book_pages('jokeSTYLE',
                                                        style_update=True))

    self.assertEqual(setup_image.url, generated_setup_url)
    self.assertEqual(punchline_image.url, generated_punchline_url)
    mock_style_generate.assert_called_once()
    _, kwargs = mock_style_generate.call_args
    self.assertIn('setup_text', kwargs)
    self.assertIn('punchline_text', kwargs)
    self.assertEqual(kwargs['setup_text'], 'Why did the burger run')
    self.assertEqual(kwargs['punchline_text'], 'Because it saw the fryer')
    self.assertTrue(kwargs['add_print_margins'])

    self.assertIsInstance(kwargs['setup_image'], models.Image)
    self.assertEqual(kwargs['setup_image'].url,
                     'https://cdn.example.com/setup.png')
    self.assertIsInstance(kwargs['punchline_image'], models.Image)
    self.assertEqual(kwargs['punchline_image'].url,
                     'https://cdn.example.com/punchline.png')

    mock_firestore.update_punny_joke.assert_called_once()
    mock_storage.download_image_from_gcs.assert_not_called()

  @patch('common.image_operations.image_client')
  @patch('common.image_operations.cloud_storage')
  def test_style_update_punchline_uses_generated_setup_ref_and_prompt_hint(
      self, mock_storage, mock_image_client):
    image_operations._get_style_update_reference_images.cache_clear()

    setup_image_model = _make_fake_image_model(
      gcs_uri='gs://bucket/setup.png', url='https://cdn.example.com/setup.png')
    punchline_image_model = _make_fake_image_model(
      gcs_uri='gs://bucket/punchline.png',
      url='https://cdn.example.com/punchline.png')

    # PIL images to return when downloading in _get_simple_book_page
    setup_pil = Image.open(BytesIO(_create_image_bytes('red')))
    punchline_pil = Image.open(BytesIO(_create_image_bytes('blue')))

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    def _download_side_effect(uri: str):
      if uri == 'gs://bucket/setup.png':
        return setup_pil
      if uri == 'gs://bucket/punchline.png':
        return punchline_pil
      # Default empty image for style refs if needed, but they are mocked via models.Image
      return Image.open(BytesIO(_create_image_bytes('white')))

    mock_storage.download_image_from_gcs.side_effect = _download_side_effect

    generated_calls = []

    class FakeClient:

      def generate_image(self, prompt, reference_images):
        generated_calls.append((prompt, reference_images))
        return _make_fake_image_model(
          gcs_uri=f'gs://generated/{len(generated_calls)}',
          url=f'https://cdn.example.com/generated/{len(generated_calls)}',
          final_prompt=prompt,
        )

      def outpaint_image(self, **kwargs):
        return _make_fake_image_model(
          gcs_uri='gs://generated/simple',
          url='https://cdn.example.com/simple.png',
        )

    mock_image_client.get_client.return_value = FakeClient()

    result = image_operations.generate_book_pages_style_update(
      setup_image=setup_image_model,
      punchline_image=punchline_image_model,
      setup_text='Setup text here',
      punchline_text='Punchline text here',
      output_file_name_base='joke123_book_page',
      additional_setup_instructions='setup extra',
      additional_punchline_instructions='punch extra',
    )

    self.assertEqual(len(generated_calls), 2)

    setup_prompt, setup_refs = generated_calls[0]
    punch_prompt, punch_refs = generated_calls[1]

    self.assertIn('Setup text here', setup_prompt)
    self.assertIn('setup extra', setup_prompt)
    self.assertIn('Punchline text here', punch_prompt)
    self.assertIn('punch extra', punch_prompt)
    self.assertIn('PREVIOUS_PANEL', punch_prompt)
    self.assertIn('must exactly match its characters', punch_prompt)

    self.assertIs(setup_refs[0], setup_image_model)
    self.assertIs(punch_refs[0], result.generated_setup_image)

    # Check that style refs are passed as models.Image
    canvas_ref = [
      r for r in punch_refs
      if isinstance(r, models.Image) and 'canvas' in r.url
    ]
    ref1_ref = [
      r for r in punch_refs if isinstance(r, models.Image) and 'lion' in r.url
    ]  # wait, url is constant

    # We can check URLs of style refs
    style_ref_urls = [r.url for r in punch_refs if isinstance(r, models.Image)]
    self.assertIn(constants.STYLE_REFERENCE_CANVAS_IMAGE_URL, style_ref_urls)
    self.assertIn(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
                  style_ref_urls)
    self.assertIn(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
                  style_ref_urls)

  @patch('common.image_operations.generate_book_pages_with_nano_banana_pro')
  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.config.IMAGE_BUCKET_NAME', 'test-bucket')
  def test_create_book_pages_uses_book_page_base_when_requested(
      self, mock_storage, mock_firestore, mock_generate_pages):
    mock_joke = SimpleNamespace(
      key='jokeXYZ',
      setup_image_url='https://cdn.example.com/original_setup.png',
      punchline_image_url='https://cdn.example.com/original_punch.png',
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
      'book_page_setup_image_url': 'https://cdn.example.com/book_setup.jpg',
      'book_page_punchline_image_url':
      'https://cdn.example.com/book_punch.jpg',
    }
    mock_metadata_doc.get.return_value = metadata_snapshot

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    generated_setup_uri = 'gs://generated/book_setup.png'
    generated_punch_uri = 'gs://generated/book_punch.png'
    simple_setup_uri = 'gs://generated/simple_setup.png'
    simple_punch_uri = 'gs://generated/simple_punch.png'
    new_setup_url = 'https://cdn.example.com/new_setup.jpg'
    new_punchline_url = 'https://cdn.example.com/new_punchline.jpg'
    simple_setup_url = 'https://cdn.example.com/simple_setup.png'
    simple_punchline_url = 'https://cdn.example.com/simple_punchline.png'

    def _stub_generation(**kwargs):
      self.assertIsInstance(kwargs['setup_image'], models.Image)
      self.assertEqual(kwargs['setup_image'].url,
                       'https://cdn.example.com/book_setup.jpg')
      self.assertIsInstance(kwargs['punchline_image'], models.Image)
      self.assertEqual(kwargs['punchline_image'].url,
                       'https://cdn.example.com/book_punch.jpg')
      self.assertFalse(kwargs['add_print_margins'])
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
          final_prompt='new-setup-prompt',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=new_punchline_url,
          model_thought='punchline-thought',
          final_prompt='new-punchline-prompt',
        ),
        setup_prompt='new-setup-prompt',
        punchline_prompt='new-punchline-prompt',
      )

    mock_generate_pages.side_effect = _stub_generation

    setup_image_result, punchline_image_result = (
      image_operations.generate_and_populate_book_pages(
        'jokeXYZ',
        overwrite=True,
        base_image_source='book_page',
      ))

    self.assertEqual(setup_image_result.url, new_setup_url)
    self.assertEqual(punchline_image_result.url, new_punchline_url)
    mock_generate_pages.assert_called_once()
    mock_storage.extract_gcs_uri_from_image_url.assert_any_call(
      'https://cdn.example.com/book_setup.jpg')
    mock_storage.extract_gcs_uri_from_image_url.assert_any_call(
      'https://cdn.example.com/book_punch.jpg')
    update_call = mock_firestore.update_punny_joke.call_args
    self.assertEqual(update_call.args[0], 'jokeXYZ')

  @patch(
    'common.image_operations.cloud_storage.extract_gcs_uri_from_image_url')
  @patch('common.image_operations.firestore')
  def test_create_book_pages_invalid_base_image_source_raises(
      self, mock_firestore, mock_extract):
    mock_joke = SimpleNamespace(
      key='jokeXYZ',
      setup_image_url='https://cdn.example.com/original_setup.png',
      punchline_image_url='https://cdn.example.com/original_punch.png',
    )
    mock_firestore.get_punny_joke.return_value = mock_joke

    mock_firestore_db = MagicMock()
    mock_metadata_doc = MagicMock()
    (mock_firestore_db.collection.return_value.document.return_value.
     collection.return_value.document.return_value) = mock_metadata_doc
    mock_firestore.db.return_value = mock_firestore_db

    metadata_snapshot = MagicMock()
    metadata_snapshot.exists = True
    metadata_snapshot.to_dict.return_value = {}
    mock_metadata_doc.get.return_value = metadata_snapshot

    mock_extract.side_effect = lambda uri: f'gs://bucket/{uri.split(' / ')[-1]}'

    with self.assertRaisesRegex(ValueError, 'Invalid base_image_source'):
      image_operations.generate_and_populate_book_pages(
        'jokeXYZ', overwrite=True, base_image_source='not-valid')

  @patch('common.image_operations.generate_book_pages_with_nano_banana_pro')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations.firestore')
  def test_create_book_pages_falls_back_to_original_when_book_pages_missing(
      self, mock_firestore, mock_storage, mock_generate_pages):
    mock_joke = SimpleNamespace(
      key='jokeFallback',
      setup_image_url='https://cdn.example.com/original_setup.png',
      punchline_image_url='https://cdn.example.com/original_punch.png',
      setup_image_description='desc',
      punchline_image_description='desc',
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
    metadata_snapshot.to_dict.return_value = {}
    mock_metadata_doc.get.return_value = metadata_snapshot

    def _extract(uri):
      return f'gs://bucket/{uri.split("/")[-1]}'

    mock_storage.extract_gcs_uri_from_image_url.side_effect = _extract

    generated_setup_uri = 'gs://generated/book_setup.png'
    generated_punch_uri = 'gs://generated/book_punch.png'
    simple_setup_uri = 'gs://generated/simple_setup.png'
    simple_punch_uri = 'gs://generated/simple_punch.png'
    new_setup_url = 'https://cdn.example.com/new_setup.jpg'
    new_punchline_url = 'https://cdn.example.com/new_punchline.jpg'
    simple_setup_url = 'https://cdn.example.com/simple_setup.png'
    simple_punchline_url = 'https://cdn.example.com/simple_punchline.png'

    def _stub_generation(**kwargs):
      self.assertIsInstance(kwargs['setup_image'], models.Image)
      self.assertEqual(kwargs['setup_image'].url,
                       'https://cdn.example.com/original_setup.png')
      self.assertIsInstance(kwargs['punchline_image'], models.Image)
      self.assertEqual(kwargs['punchline_image'].url,
                       'https://cdn.example.com/original_punch.png')
      self.assertTrue(kwargs['add_print_margins'])
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
          final_prompt='new-setup-prompt',
        ),
        generated_punchline_image=_make_fake_image_model(
          gcs_uri=generated_punch_uri,
          url=new_punchline_url,
          model_thought='punchline-thought',
          final_prompt='new-punchline-prompt',
        ),
        setup_prompt='new-setup-prompt',
        punchline_prompt='new-punchline-prompt',
      )

    mock_generate_pages.side_effect = _stub_generation

    setup_image_result, punchline_image_result = (
      image_operations.generate_and_populate_book_pages(
        'jokeFallback',
        overwrite=True,
        base_image_source='book_page',
      ))

    self.assertEqual(setup_image_result.url, new_setup_url)
    self.assertEqual(punchline_image_result.url, new_punchline_url)
    mock_storage.extract_gcs_uri_from_image_url.assert_any_call(
      'https://cdn.example.com/original_setup.png')
    mock_storage.extract_gcs_uri_from_image_url.assert_any_call(
      'https://cdn.example.com/original_punch.png')


class GetSimpleBookPageTest(unittest.TestCase):
  """Tests for _get_simple_book_page."""

  @patch('common.image_operations.image_client.get_client')
  @patch('common.image_operations.cloud_storage')
  def test_get_simple_book_page_without_margins_returns_existing(
      self, mock_storage, mock_get_client):
    image_model = models.Image(
      gcs_uri='gs://bucket/source.png',
      url='https://cdn.example.com/source.png',
    )
    mock_storage.download_image_from_gcs.return_value = Image.new(
      'RGB',
      (2048, 2048),
      color='red',
    )

    result = image_operations._get_simple_book_page(
      image_model,
      'simple',
      add_print_margins=False,
    )

    self.assertIs(result, image_model)
    mock_storage.upload_image_to_gcs.assert_not_called()
    mock_storage.get_image_gcs_uri.assert_not_called()
    mock_get_client.assert_not_called()

  @patch('common.image_operations.image_client.get_client')
  @patch('common.image_operations.cloud_storage')
  def test_get_simple_book_page_without_margins_resizes(
      self, mock_storage, mock_get_client):
    mock_storage.download_image_from_gcs.return_value = Image.new(
      'RGB',
      (512, 512),
      color='red',
    )
    mock_storage.get_image_gcs_uri.return_value = 'gs://bucket/simple.png'
    mock_storage.get_final_image_url.return_value = (
      'https://cdn.example.com/simple.png')

    def _upload_image(image, file_name_base, extension, *, gcs_uri=None):
      self.assertEqual(image.size, (2048, 2048))
      self.assertEqual(file_name_base, 'simple')
      self.assertEqual(extension, 'png')
      self.assertEqual(gcs_uri, 'gs://bucket/simple.png')
      return gcs_uri, b'bytes'

    mock_storage.upload_image_to_gcs.side_effect = _upload_image

    result = image_operations._get_simple_book_page(
      models.Image(
        gcs_uri='gs://bucket/source.png',
        url='https://cdn.example.com/source.png',
      ),
      'simple',
      add_print_margins=False,
    )

    self.assertEqual(result.gcs_uri, 'gs://bucket/simple.png')
    self.assertEqual(result.url, 'https://cdn.example.com/simple.png')
    mock_get_client.assert_not_called()

  @patch('common.image_operations.image_client.get_client')
  @patch('common.image_operations.cloud_storage')
  def test_get_simple_book_page_with_margins_uses_outpaint(
      self, mock_storage, mock_get_client):
    input_image = Image.new('RGB', (1024, 1024), color='blue')
    mock_storage.download_image_from_gcs.return_value = input_image
    mock_storage.get_image_gcs_uri.return_value = 'gs://bucket/simple.png'

    recorded = {}

    class FakeClient:

      def outpaint_image(self, **kwargs):
        recorded.update(kwargs)
        return models.Image(
          gcs_uri='gs://bucket/outpaint.png',
          url='https://cdn.example.com/outpaint.png',
        )

    mock_get_client.return_value = FakeClient()

    result = image_operations._get_simple_book_page(
      models.Image(
        gcs_uri='gs://bucket/source.png',
        url='https://cdn.example.com/source.png',
      ),
      'simple',
      add_print_margins=True,
    )

    margin_pixels = math.ceil(input_image.width * 0.1)
    max_margin = max(1, (2048 // 2) - 1)
    margin_pixels = min(margin_pixels, max_margin)
    inner_size = max(1, 2048 - (margin_pixels * 2))

    self.assertEqual(recorded['gcs_uri'], 'gs://bucket/simple.png')
    self.assertEqual(recorded['top'], margin_pixels)
    self.assertEqual(recorded['bottom'], margin_pixels)
    self.assertEqual(recorded['left'], margin_pixels)
    self.assertEqual(recorded['right'], margin_pixels)
    self.assertEqual(recorded['pil_image'].size, (inner_size, inner_size))
    self.assertEqual(result.gcs_uri, 'gs://bucket/outpaint.png')
    self.assertEqual(result.url, 'https://cdn.example.com/outpaint.png')


class AddPageNumberToImageTest(unittest.TestCase):
  """Tests for rendering page numbers onto book pages."""

  def test_setup_page_positions_and_stroke(self):
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 20, 30)
    with patch('common.image_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.image_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        image_operations._add_page_number_to_image(
          image,
          page_number=3,
          total_pages=12,
          is_punchline=False,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )

    mock_get_font.assert_called_once_with(
      profile.page_number_font_size_px)
    offset = profile.page_number_offset_px
    stroke_width = max(
      1,
      int(
        round(profile.page_number_font_size_px *
              image_operations._PAGE_NUMBER_STROKE_RATIO)))
    draw_mock.textbbox.assert_called_once_with(
      (0, 0),
      '3',
      font=fake_font,
      stroke_width=stroke_width,
    )
    text_call = draw_mock.text.call_args
    self.assertEqual(text_call[0][0], (200 - offset - 20, 200 - offset - 30))
    self.assertEqual(text_call[0][1], '3')
    self.assertEqual(text_call[1]['stroke_width'], stroke_width)
    self.assertEqual(text_call[1]['stroke_fill'],
                     image_operations._PAGE_NUMBER_STROKE_COLOR)

  def test_punchline_page_positions_use_left_margin(self):
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 14, 20)
    with patch('common.image_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.image_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        image_operations._add_page_number_to_image(
          image,
          page_number=1,
          total_pages=5,
          is_punchline=True,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )

    mock_get_font.assert_called_once_with(
      profile.page_number_font_size_px)
    offset = profile.page_number_offset_px
    stroke_width = max(
      1,
      int(
        round(profile.page_number_font_size_px *
              image_operations._PAGE_NUMBER_STROKE_RATIO)))
    text_call = draw_mock.text.call_args
    self.assertEqual(text_call[0][0], (offset, 200 - offset - 20))
    self.assertEqual(text_call[0][1], '1')
    self.assertEqual(text_call[1]['stroke_width'], stroke_width)

  def test_font_size_static_value(self):
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 10, 10)
    with patch('common.image_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.image_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        image_operations._add_page_number_to_image(
          image,
          page_number=1,
          total_pages=99,
          is_punchline=False,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )
        image_operations._add_page_number_to_image(
          image,
          page_number=10,
          total_pages=2,
          is_punchline=False,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )

    requested_sizes = [entry[0][0] for entry in mock_get_font.call_args_list]
    self.assertEqual(
      requested_sizes,
      [
        profile.page_number_font_size_px,
        profile.page_number_font_size_px
      ],
    )


class ExportJokePageFilesTest(unittest.TestCase):
  """Tests for joke-book ZIP/PDF export."""

  @patch('common.image_operations._save_jpeg_bytes', return_value=b'enhanced')
  def test_enhance_kdp_export_page_bytes_uses_profile_encoder_settings(
    self,
    mock_save_jpeg_bytes,
  ):
    """KDP export enhancement should use the active profile JPEG settings."""
    page_image = Image.new('RGB', (32, 32), 'red')
    buffer = BytesIO()
    page_image.save(buffer, format='JPEG', quality=100)

    mock_editor = MagicMock()
    mock_editor.enhance_image.return_value = Image.new('RGB', (32, 32), 'blue')
    profile = image_operations._EBOOK_EXPORT_PROFILE

    enhanced_bytes = image_operations._enhance_kdp_export_page_bytes(
      buffer.getvalue(),
      profile=profile,
      editor=mock_editor,
    )

    self.assertEqual(enhanced_bytes, b'enhanced')
    mock_editor.enhance_image.assert_called_once()
    self.assertEqual(mock_editor.enhance_image.call_args.kwargs, {})
    mock_save_jpeg_bytes.assert_called_once()
    self.assertEqual(
      mock_save_jpeg_bytes.call_args.kwargs,
      dict(
        quality=profile.jpeg_quality,
        subsampling=profile.jpeg_subsampling,
        progressive=profile.jpeg_progressive,
        color_mode='RGB',
      ),
    )

  @patch('common.image_operations._add_page_number_to_image',
         side_effect=lambda image, **_kwargs: image)
  def test_convert_for_book_export_trims_inner_binding_edge(
    self,
    _mock_add_page_number,
  ):
    """Punchline pages trim right; setup pages trim left."""
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    source_image = Image.new('RGB', (32, 32), 'red')
    mock_editor = MagicMock()
    scaled_image = Image.new('RGB', (10, 10), 'white')
    trimmed_punchline = Image.new('RGB',
                                  (profile.final_width_px,
                                   profile.final_height_px),
                                  'blue')
    trimmed_setup = Image.new('RGB',
                              (profile.final_width_px,
                               profile.final_height_px),
                              'green')
    mock_editor.scale_image.return_value = scaled_image
    mock_editor.trim_edges.side_effect = [trimmed_punchline, trimmed_setup]

    _ = image_operations._convert_for_book_export(
      source_image,
      is_left_page=True,
      page_number=1,
      total_pages=2,
      color_mode='RGB',
      profile=profile,
      image_editor_instance=mock_editor,
    )
    _ = image_operations._convert_for_book_export(
      source_image,
      is_left_page=False,
      page_number=2,
      total_pages=2,
      color_mode='RGB',
      profile=profile,
      image_editor_instance=mock_editor,
    )

    punchline_call = mock_editor.trim_edges.call_args_list[0]
    self.assertEqual(punchline_call.kwargs['left'], 0)
    self.assertEqual(punchline_call.kwargs['right'],
                     profile.output_bleed_size_px)

    setup_call = mock_editor.trim_edges.call_args_list[1]
    self.assertEqual(setup_call.kwargs['left'],
                     profile.output_bleed_size_px)
    self.assertEqual(setup_call.kwargs['right'], 0)

  @patch('common.image_operations._create_qr_code_image')
  @patch('common.image_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_add_review_qr_to_page_overlays_qr(
    self,
    mock_get_review_url,
    mock_create_qr_code_image,
  ):
    """Review QR overlay should paste the generated QR at the profile location."""
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    base_image = Image.new(
      'RGB',
      (profile.pre_trim_width_px, profile.pre_trim_height_px),
      'white',
    )
    buffer = BytesIO()
    base_image.save(buffer, format='JPEG', quality=100)

    qr_image = Image.new(
      'RGB',
      (profile.qr_size_px, profile.qr_size_px),
      'black',
    )
    mock_get_review_url.return_value = 'https://example.com/review'
    mock_create_qr_code_image.return_value = qr_image

    updated_page = image_operations._add_review_qr_to_page(
      image_operations.BookPage(
        file_name='999_about.jpg',
        image_bytes=buffer.getvalue(),
      ),
      profile=profile,
      associated_book_key='animal-jokes',
      page_index=4,
      trim_left_px=profile.output_bleed_size_px,
    )

    mock_get_review_url.assert_called_once()
    self.assertEqual(mock_get_review_url.call_args.args,
                     (amazon_redirect.BookKey.ANIMAL_JOKES, ))
    self.assertEqual(mock_get_review_url.call_args.kwargs, {
      'page_type': amazon_redirect.AmazonRedirectPageType.REVIEW,
      'book_format': amazon_redirect.BookFormat.PAPERBACK,
      'source': amazon_redirect.AttributionSource.BOOK_ABOUT_PAGE,
    })
    mock_create_qr_code_image.assert_called_once_with(
      'https://example.com/review',
      size_px=profile.qr_size_px,
    )
    self.assertEqual(updated_page.file_name, '999_about.jpg')
    self.assertIsNotNone(updated_page.hyperlink)
    assert updated_page.hyperlink is not None
    self.assertEqual(updated_page.hyperlink.page_index, 4)
    self.assertEqual(updated_page.hyperlink.url, 'https://example.com/review')
    self.assertEqual(updated_page.hyperlink.x1,
                     profile.qr_x_px - profile.output_bleed_size_px)
    self.assertEqual(updated_page.hyperlink.y1, profile.qr_y_px)
    self.assertEqual(
      updated_page.hyperlink.x2,
      profile.qr_x_px + profile.qr_size_px - profile.output_bleed_size_px,
    )
    self.assertGreater(
      updated_page.hyperlink.y2,
      profile.qr_y_px + profile.qr_size_px,
    )
    updated_image = Image.open(BytesIO(updated_page.image_bytes))
    self.assertEqual(
      updated_image.getpixel((profile.qr_x_px + 10, profile.qr_y_px + 10)),
      (0, 0, 0),
    )

  @patch('common.image_operations._BookPageTextDrawer')
  @patch('common.image_operations._create_qr_code_image')
  @patch('common.image_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_add_review_qr_to_page_adds_cta_caption(
    self,
    mock_get_review_url,
    mock_create_qr_code_image,
    mock_text_drawer,
  ):
    profile = image_operations._PAPERBACK_EXPORT_PROFILE
    mock_get_review_url.return_value = 'https://example.com/review'
    mock_create_qr_code_image.return_value = Image.new('RGB', (10, 10), 'black')
    text_drawer = mock_text_drawer.return_value
    text_drawer.width = 120
    text_drawer.height = 40

    updated_page = image_operations._add_review_qr_to_page(
      image_operations.BookPage(
        file_name='999_about.jpg',
        image_bytes=_create_image_bytes(
          'white',
          size=(
            profile.pre_trim_width_px,
            profile.pre_trim_height_px,
          ),
        ),
      ),
      profile=profile,
      associated_book_key='animal-jokes',
      page_index=4,
      trim_left_px=profile.output_bleed_size_px,
    )

    self.assertIsInstance(updated_page.image_bytes, (bytes, bytearray))
    mock_text_drawer.assert_called_once()
    self.assertEqual(len(mock_text_drawer.call_args.args), 1)
    self.assertIsInstance(mock_text_drawer.call_args.args[0], Image.Image)
    self.assertEqual(mock_text_drawer.call_args.kwargs, {
      'text': profile.qr_label,
      'font_size': profile.qr_label_font_size_px,
    })
    text_drawer.draw_text.assert_called_once_with(
      x=profile.qr_x_px + ((profile.qr_size_px - 120) / 2),
      y=profile.qr_y_px + profile.qr_size_px + profile.qr_label_margin_top_px,
    )
    self.assertEqual(
      updated_page.hyperlink,
      pdf_client.HyperlinkSpec(
        page_index=4,
        url='https://example.com/review',
        x1=profile.qr_x_px - profile.output_bleed_size_px,
        y1=profile.qr_y_px,
        x2=profile.qr_x_px + profile.qr_size_px -
        profile.output_bleed_size_px,
        y2=profile.qr_y_px + profile.qr_size_px +
        profile.qr_label_margin_top_px + 40,
      ),
    )

  @patch('common.image_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_get_about_page_review_bridge_url_uses_book_about_source(
    self,
    mock_get_bridge_url,
  ):
    mock_get_bridge_url.return_value = 'https://example.com/review-bridge'

    result = image_operations._get_about_page_review_bridge_url(
      'animal-jokes',
      book_format=amazon_redirect.BookFormat.EBOOK,
    )

    self.assertEqual(result, 'https://example.com/review-bridge')
    mock_get_bridge_url.assert_called_once_with(
      amazon_redirect.BookKey.ANIMAL_JOKES,
      page_type=amazon_redirect.AmazonRedirectPageType.REVIEW,
      book_format=amazon_redirect.BookFormat.EBOOK,
      source=amazon_redirect.AttributionSource.BOOK_ABOUT_PAGE,
    )

  @patch('common.image_operations._build_book_export_pages')
  @patch('common.image_operations.cloud_storage.get_public_url')
  @patch('common.image_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.image_operations._build_joke_book_export_uris')
  @patch('common.image_operations.pdf_client.create_pdf')
  def test_export_joke_book_files_builds_two_pdfs_without_zip(
    self,
    mock_create_pdf,
    mock_build_export_uris,
    mock_upload_bytes,
    mock_get_public_url,
    mock_build_pages,
  ):
    """export_joke_book_files should upload paperback and ebook PDFs by default."""
    book = models.JokeBook(
      id='book-1',
      book_name='My Book',
      jokes=['joke1'],
      belongs_to_page_gcs_uri='gs://images.quillsstorybook.com/_joke_assets/book/belongs.png',
    )

    paperback_pages = [
      image_operations.BookPage(file_name='001_belongs.jpg', image_bytes=b'pb-1'),
      image_operations.BookPage(
        file_name='999_about.jpg',
        image_bytes=b'pb-2',
        hyperlink=pdf_client.HyperlinkSpec(
          page_index=1,
          url='https://example.com/paperback-review',
          x1=10,
          y1=20,
          x2=30,
          y2=40,
        ),
      ),
    ]
    ebook_pages = [
      image_operations.BookPage(file_name='001_belongs.jpg', image_bytes=b'eb-1'),
      image_operations.BookPage(
        file_name='999_about.jpg',
        image_bytes=b'eb-2',
        hyperlink=pdf_client.HyperlinkSpec(
          page_index=1,
          url='https://example.com/ebook-review',
          x1=11,
          y1=21,
          x2=31,
          y2=41,
        ),
      ),
    ]
    mock_build_pages.side_effect = [paperback_pages, ebook_pages]
    mock_create_pdf.side_effect = [b'%PDF-paperback', b'%PDF-ebook']
    mock_build_export_uris.return_value = (
      'gs://snickerdoodle_temp_files/joke_book_pages.zip',
      'gs://snickerdoodle_temp_files/joke_book_pages_paperback.pdf',
      'gs://snickerdoodle_temp_files/joke_book_pages_ebook.pdf',
    )
    mock_get_public_url.side_effect = [
      'https://cdn.example.com/book_paperback.pdf',
      'https://cdn.example.com/book_ebook.pdf',
    ]

    result = image_operations.export_joke_book_files(book)

    self.assertIsNone(result.zip_url)
    self.assertEqual(result.paperback_pdf_url,
                     'https://cdn.example.com/book_paperback.pdf')
    self.assertEqual(result.ebook_pdf_url, 'https://cdn.example.com/book_ebook.pdf')
    self.assertEqual(mock_upload_bytes.call_count, 2)
    self.assertEqual(mock_upload_bytes.call_args_list[0].args, (
      b'%PDF-paperback',
      'gs://snickerdoodle_temp_files/joke_book_pages_paperback.pdf',
      'application/pdf',
    ))
    self.assertEqual(mock_upload_bytes.call_args_list[1].args, (
      b'%PDF-ebook',
      'gs://snickerdoodle_temp_files/joke_book_pages_ebook.pdf',
      'application/pdf',
    ))
    self.assertEqual(mock_build_pages.call_args_list[0].kwargs['profile'],
                     image_operations._PAPERBACK_EXPORT_PROFILE)
    self.assertEqual(mock_build_pages.call_args_list[1].kwargs['profile'],
                     image_operations._EBOOK_EXPORT_PROFILE)
    self.assertEqual(mock_create_pdf.call_args_list[0].kwargs['quality'],
                     image_operations._PAPERBACK_EXPORT_PROFILE.jpeg_quality)
    self.assertEqual(mock_create_pdf.call_args_list[1].kwargs['quality'],
                     image_operations._EBOOK_EXPORT_PROFILE.jpeg_quality)
    self.assertEqual(
      mock_create_pdf.call_args_list[0].kwargs['hyperlinks'],
      [paperback_pages[1].hyperlink],
    )
    self.assertEqual(
      mock_create_pdf.call_args_list[1].kwargs['hyperlinks'],
      [ebook_pages[1].hyperlink],
    )

  @patch('common.image_operations._build_book_export_pages')
  @patch('common.image_operations.cloud_storage.get_public_url')
  @patch('common.image_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.image_operations._build_joke_book_export_uris')
  @patch('common.image_operations.pdf_client.create_pdf')
  def test_export_joke_book_files_optionally_uploads_paperback_zip(
    self,
    mock_create_pdf,
    mock_build_export_uris,
    mock_upload_bytes,
    mock_get_public_url,
    mock_build_pages,
  ):
    book = models.JokeBook(
      id='book-1',
      book_name='My Book',
      jokes=['joke1'],
      belongs_to_page_gcs_uri='gs://images.quillsstorybook.com/_joke_assets/book/belongs.png',
    )
    paperback_pages = [
      image_operations.BookPage(file_name='001.jpg', image_bytes=b'pb-1'),
    ]
    ebook_pages = [
      image_operations.BookPage(file_name='001.jpg', image_bytes=b'eb-1'),
    ]
    mock_build_pages.side_effect = [paperback_pages, ebook_pages]
    mock_create_pdf.side_effect = [b'%PDF-paperback', b'%PDF-ebook']
    mock_build_export_uris.return_value = (
      'gs://snickerdoodle_temp_files/joke_book_pages.zip',
      'gs://snickerdoodle_temp_files/joke_book_pages_paperback.pdf',
      'gs://snickerdoodle_temp_files/joke_book_pages_ebook.pdf',
    )
    mock_get_public_url.side_effect = [
      'https://cdn.example.com/book.zip',
      'https://cdn.example.com/book_paperback.pdf',
      'https://cdn.example.com/book_ebook.pdf',
    ]

    result = image_operations.export_joke_book_files(
      book,
      export_zip_paperback=True,
    )

    self.assertEqual(result.zip_url, 'https://cdn.example.com/book.zip')
    self.assertEqual(mock_upload_bytes.call_count, 3)
    zip_upload_args = mock_upload_bytes.call_args_list[0].args
    self.assertEqual(zip_upload_args[1],
                     'gs://snickerdoodle_temp_files/joke_book_pages.zip')
    self.assertEqual(zip_upload_args[2], 'application/zip')


if __name__ == '__main__':
  unittest.main()


class CreateJokeNotesSheetImageTest(unittest.TestCase):
  """Tests for create_joke_notes_sheet_image function."""

  @patch('common.joke_notes_sheet_operations.requests.get')
  @patch('common.joke_notes_sheet_operations.cloud_storage')
  def test_create_joke_notes_sheet_image(self, mock_storage,
                                         mock_requests_get):
    template_image = Image.new('RGBA', (3300, 2550), (255, 0, 0, 128))
    template_buffer = BytesIO()
    template_image.save(template_buffer, format='PNG')
    mock_response = Mock()
    mock_response.content = template_buffer.getvalue()
    mock_response.raise_for_status = Mock()
    mock_requests_get.return_value = mock_response

    # Mock joke data
    jokes = [
      models.PunnyJoke(
        key='joke1',
        setup_text='Setup 1',
        punchline_text='Punchline 1',
        setup_image_url='http://test/setup.jpg',
        punchline_image_url='http://test/punchline.jpg',
      ),
      models.PunnyJoke(
        key='joke2',
        setup_text='Setup 2',
        punchline_text='Punchline 2',
        setup_image_url='http://test/setup.jpg',
        punchline_image_url='http://test/punchline.jpg',
      ),
    ]

    # Mock image downloads
    mock_img = Image.new('RGB', (100, 100), 'blue')
    mock_storage.download_image_from_gcs.return_value = mock_img
    mock_storage.extract_gcs_uri_from_image_url.return_value = 'gs://test/img.jpg'

    # Run function
    result = joke_notes_sheet_operations._create_joke_notes_sheet_image(jokes)

    # Verify result is a PIL image
    self.assertIsInstance(result, Image.Image)
    self.assertEqual(result.size, (3300, 2550))
    self.assertEqual(result.mode, 'RGB')

    # Verify calls
    # 2 jokes * 2 images = 4 downloads
    self.assertEqual(mock_storage.download_image_from_gcs.call_count, 4)
    mock_requests_get.assert_called_once_with(
      joke_notes_sheet_operations._JOKE_NOTES_BRANDED5_URL,
      timeout=10,
    )


class CreateJokeNotesSheetTest(unittest.TestCase):
  """Tests for create_joke_notes_sheet function."""

  @patch(
    'common.joke_notes_sheet_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.joke_notes_sheet_operations.pdf_client.create_pdf')
  @patch('common.joke_notes_sheet_operations._create_joke_notes_sheet_images')
  @patch('common.joke_notes_sheet_operations.cloud_storage.gcs_file_exists')
  @patch('common.joke_notes_sheet_operations.firestore.upsert_joke_sheet')
  def test_get_joke_notes_sheet_uploads_when_missing(
    self,
    mock_upsert_joke_sheet,
    mock_gcs_file_exists,
    mock_create_image,
    mock_create_pdf,
    mock_upload_bytes,
  ):
    notes_image = Image.new('RGB', (100, 100), 'white')
    mock_create_image.return_value = [notes_image]
    mock_create_pdf.return_value = b'pdf-bytes'
    mock_gcs_file_exists.return_value = False

    jokes = [
      models.PunnyJoke(
        key='joke1',
        setup_text='Setup',
        punchline_text='Punchline',
        num_saved_users_fraction=0.4,
      ),
    ]

    def _echo_sheet(sheet):
      sheet.key = "sheet-1"
      return sheet

    mock_upsert_joke_sheet.side_effect = _echo_sheet
    result = joke_notes_sheet_operations.ensure_joke_notes_sheet(jokes,
                                                                 quality=42)

    expected_hash_source = (
      'joke1|quality=42|branded=True|'
      f'version={joke_notes_sheet_operations._JOKE_NOTES_SHEET_VERSION}')
    expected_stem = hashlib.sha256(
      expected_hash_source.encode('utf-8')).hexdigest()
    expected_pdf_gcs_uri = (
      f"{joke_notes_sheet_operations._PDF_DIR_GCS_URI}/{expected_stem}.pdf")
    expected_image_gcs_uri = (
      f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_stem}.png")

    self.assertEqual(result.pdf_gcs_uri, expected_pdf_gcs_uri)
    self.assertEqual(result.image_gcs_uri, expected_image_gcs_uri)
    self.assertEqual(result.image_gcs_uris, [expected_image_gcs_uri])
    self.assertEqual(result.key, "sheet-1")

    # Two existence checks: PDF then PNG.
    self.assertEqual(mock_gcs_file_exists.call_count, 2)
    mock_gcs_file_exists.assert_any_call(expected_pdf_gcs_uri)
    mock_gcs_file_exists.assert_any_call(expected_image_gcs_uri)

    # Firestore upsert receives the sheet object.
    self.assertEqual(mock_upsert_joke_sheet.call_count, 1)
    upserted_sheet = mock_upsert_joke_sheet.call_args[0][0]
    self.assertEqual(upserted_sheet.joke_ids, ['joke1'])
    self.assertIsNone(upserted_sheet.category_id)
    self.assertEqual(upserted_sheet.pdf_gcs_uri, expected_pdf_gcs_uri)
    self.assertEqual(upserted_sheet.image_gcs_uri, expected_image_gcs_uri)
    self.assertEqual(upserted_sheet.image_gcs_uris, [expected_image_gcs_uri])
    self.assertAlmostEqual(upserted_sheet.avg_saved_users_fraction, 0.4)

    mock_create_image.assert_called_once_with(jokes, branded=True)
    mock_create_pdf.assert_called_once_with([notes_image], quality=42)
    # Two uploads: PNG and PDF.
    self.assertEqual(mock_upload_bytes.call_count, 2)
    calls = mock_upload_bytes.call_args_list
    self.assertEqual(calls[0].kwargs["gcs_uri"], expected_image_gcs_uri)
    self.assertEqual(calls[0].kwargs["content_type"], "image/png")
    self.assertIsInstance(calls[0].kwargs["content_bytes"], (bytes, bytearray))
    self.assertEqual(calls[1].kwargs["gcs_uri"], expected_pdf_gcs_uri)
    self.assertEqual(calls[1].kwargs["content_type"], "application/pdf")
    self.assertEqual(calls[1].kwargs["content_bytes"], b"pdf-bytes")

  @patch(
    'common.joke_notes_sheet_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.joke_notes_sheet_operations.pdf_client.create_pdf')
  @patch('common.joke_notes_sheet_operations._create_joke_notes_sheet_images')
  @patch('common.joke_notes_sheet_operations.cloud_storage.gcs_file_exists')
  @patch('common.joke_notes_sheet_operations.firestore.upsert_joke_sheet')
  def test_get_joke_notes_sheet_returns_cached_uri_when_exists(
    self,
    mock_upsert_joke_sheet,
    mock_gcs_file_exists,
    mock_create_image,
    mock_create_pdf,
    mock_upload_bytes,
  ):
    mock_gcs_file_exists.return_value = True

    def _echo_sheet(sheet):
      sheet.key = "sheet-1"
      return sheet

    mock_upsert_joke_sheet.side_effect = _echo_sheet

    jokes = [
      models.PunnyJoke(
        key='b',
        setup_text='Setup',
        punchline_text='Punchline',
        num_saved_users_fraction=0.2,
      ),
      models.PunnyJoke(
        key='a',
        setup_text='Setup',
        punchline_text='Punchline',
        num_saved_users_fraction=0.6,
      ),
    ]

    result = joke_notes_sheet_operations.ensure_joke_notes_sheet(
      jokes,
      quality=42,
    )

    expected_hash = hashlib.sha256(
      ('a|b|quality=42|branded=True|'
       f'version={joke_notes_sheet_operations._JOKE_NOTES_SHEET_VERSION}')
      .encode('utf-8')).hexdigest()
    expected_pdf_gcs_uri = (
      f"{joke_notes_sheet_operations._PDF_DIR_GCS_URI}/{expected_hash}.pdf")
    expected_image_gcs_uri = (
      f"{joke_notes_sheet_operations._IMAGE_DIR_GCS_URI}/{expected_hash}.png")
    self.assertEqual(result.pdf_gcs_uri, expected_pdf_gcs_uri)
    self.assertEqual(result.image_gcs_uri, expected_image_gcs_uri)
    self.assertEqual(result.image_gcs_uris, [expected_image_gcs_uri])
    self.assertEqual(result.key, "sheet-1")
    self.assertAlmostEqual(result.avg_saved_users_fraction, 0.4)

    self.assertEqual(mock_gcs_file_exists.call_count, 2)
    mock_gcs_file_exists.assert_any_call(expected_pdf_gcs_uri)
    mock_gcs_file_exists.assert_any_call(expected_image_gcs_uri)

    self.assertEqual(mock_upsert_joke_sheet.call_count, 1)
    mock_create_image.assert_not_called()
    mock_create_pdf.assert_not_called()
    mock_upload_bytes.assert_not_called()


class CreatePinterestPinImageTest(unittest.TestCase):
  """Tests for create_pinterest_pin_image function."""

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_single_joke(self, mock_cloud_storage,
                                                  mock_firestore):
    """create_pinterest_pin_image should create a pin image for a single joke."""
    joke_id = "joke1"

    # Create mock joke
    mock_joke = Mock()
    mock_joke.key = joke_id
    mock_joke.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_setup.png"
    mock_joke.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_punchline.png"

    mock_firestore.get_punny_jokes.return_value = [mock_joke]

    # Create test images (setup, punchline, blocker overlay)
    setup_img = Image.new('RGB', (1024, 1024), color='red')
    punchline_img = Image.new('RGB', (1024, 1024), color='blue')
    blocker_img = Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128))
    mock_cloud_storage.download_image_from_gcs.side_effect = [
      setup_img, punchline_img, blocker_img
    ]

    result = image_operations.create_joke_grid_image_3x2(joke_ids=[joke_id])

    self.assertEqual(result.size, (1000, 500))  # 1 joke = 1000x500
    self.assertEqual(result.mode, 'RGB')

    # Verify images were downloaded (setup, punchline, blocker overlay)
    self.assertEqual(mock_cloud_storage.download_image_from_gcs.call_count, 3)

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_multiple_jokes(self, mock_cloud_storage,
                                                     mock_firestore):
    """create_pinterest_pin_image should create a pin image for multiple jokes."""
    joke_ids = ["joke1", "joke2", "joke3"]

    # Create mock jokes
    mock_jokes = []
    for i, joke_id in enumerate(joke_ids):
      mock_joke = Mock()
      mock_joke.key = joke_id
      mock_joke.setup_image_url = f"https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke{i+1}_setup.png"
      mock_joke.punchline_image_url = f"https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke{i+1}_punchline.png"
      mock_jokes.append(mock_joke)

    mock_firestore.get_punny_jokes.return_value = mock_jokes

    # Create test images (6 joke images + 1 blocker overlay)
    test_images = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
      Image.new('RGB', (1024, 1024), color='purple'),
      Image.new('RGB', (1024, 1024), color='orange'),
      Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128)),  # Blocker overlay
    ]
    mock_cloud_storage.download_image_from_gcs.side_effect = test_images

    result = image_operations.create_joke_grid_image_3x2(joke_ids=joke_ids)

    self.assertEqual(result.size, (1000, 1500))  # 3 jokes = 1000x(3*500)
    self.assertEqual(result.mode, 'RGB')

    # Verify all images were downloaded (2 per joke + 1 blocker overlay)
    self.assertEqual(mock_cloud_storage.download_image_from_gcs.call_count, 7)

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_uses_jokes_list(self, mock_cloud_storage,
                                                      mock_firestore):
    """create_pinterest_pin_image should use provided jokes list order."""
    mock_jokes = []
    for joke_id in ["joke1", "joke2"]:
      mock_joke = Mock()
      mock_joke.key = joke_id
      mock_joke.setup_image_url = f"{joke_id}_setup"
      mock_joke.punchline_image_url = f"{joke_id}_punchline"
      mock_jokes.append(mock_joke)

    test_images = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
    ]
    mock_cloud_storage.download_image_from_gcs.side_effect = test_images

    result = image_operations.create_joke_grid_image_3x2(
      jokes=mock_jokes,
      block_last_panel=False,
    )

    self.assertEqual(result.size, (1000, 1000))
    self.assertEqual(result.mode, 'RGB')
    mock_firestore.get_punny_jokes.assert_not_called()
    self.assertEqual(
      mock_cloud_storage.download_image_from_gcs.call_args_list,
      [
        call("joke1_setup"),
        call("joke1_punchline"),
        call("joke2_setup"),
        call("joke2_punchline"),
      ],
    )

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_respects_input_order(
      self, mock_cloud_storage, mock_firestore):
    """create_pinterest_pin_image should follow the input joke_ids order."""
    joke_ids = ["joke2", "joke1"]

    mock_joke1 = Mock()
    mock_joke1.key = "joke1"
    mock_joke1.setup_image_url = "setup-1"
    mock_joke1.punchline_image_url = "punch-1"

    mock_joke2 = Mock()
    mock_joke2.key = "joke2"
    mock_joke2.setup_image_url = "setup-2"
    mock_joke2.punchline_image_url = "punch-2"

    # Return out of order to ensure we reorder by input.
    mock_firestore.get_punny_jokes.return_value = [mock_joke1, mock_joke2]

    test_images = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
      Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128)),
    ]
    mock_cloud_storage.download_image_from_gcs.side_effect = test_images

    image_operations.create_joke_grid_image_3x2(joke_ids=joke_ids)

    expected_calls = [
      call("setup-2"),
      call("punch-2"),
      call("setup-1"),
      call("punch-1"),
      call(image_operations._PANEL_BLOCKER_OVERLAY_URL_POST_IT),
    ]
    self.assertEqual(
      mock_cloud_storage.download_image_from_gcs.call_args_list,
      expected_calls,
    )

  @patch('common.image_operations.firestore')
  def test_create_pinterest_pin_image_empty_list(self, mock_firestore):
    """create_pinterest_pin_image should raise ValueError for empty joke list."""
    with self.assertRaises(ValueError) as context:
      image_operations.create_joke_grid_image_3x2(joke_ids=[])

    self.assertIn("joke_ids must be a non-empty list", str(context.exception))

  @patch('common.image_operations.firestore')
  def test_create_pinterest_pin_image_joke_not_found(self, mock_firestore):
    """create_pinterest_pin_image should raise ValueError if joke not found."""
    joke_id = "nonexistent"
    mock_firestore.get_punny_jokes.return_value = []

    with self.assertRaises(ValueError) as context:
      image_operations.create_joke_grid_image_3x2(joke_ids=[joke_id])

    self.assertIn("Jokes not found", str(context.exception))
    self.assertIn(joke_id, str(context.exception))

  @patch('common.image_operations.firestore')
  def test_create_pinterest_pin_image_missing_setup_image(
      self, mock_firestore):
    """create_pinterest_pin_image should raise ValueError if joke missing setup image."""
    joke_id = "joke1"

    mock_joke = Mock()
    mock_joke.key = joke_id
    mock_joke.setup_image_url = None
    mock_joke.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_punchline.png"

    mock_firestore.get_punny_jokes.return_value = [mock_joke]

    with self.assertRaises(ValueError) as context:
      image_operations.create_joke_grid_image_3x2(joke_ids=[joke_id])

    self.assertIn("missing setup or punchline image", str(context.exception))
    self.assertIn(joke_id, str(context.exception))

  @patch('common.image_operations.firestore')
  def test_create_pinterest_pin_image_missing_punchline_image(
      self, mock_firestore):
    """create_pinterest_pin_image should raise ValueError if joke missing punchline image."""
    joke_id = "joke1"

    mock_joke = Mock()
    mock_joke.key = joke_id
    mock_joke.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_setup.png"
    mock_joke.punchline_image_url = None

    mock_firestore.get_punny_jokes.return_value = [mock_joke]

    with self.assertRaises(ValueError) as context:
      image_operations.create_joke_grid_image_3x2(joke_ids=[joke_id])

    self.assertIn("missing setup or punchline image", str(context.exception))
    self.assertIn(joke_id, str(context.exception))

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_block_last_panel_false(
      self, mock_cloud_storage, mock_firestore):
    """create_pinterest_pin_image should not download blocker overlay when block_last_panel=False."""
    joke_id = "joke1"

    # Create mock joke
    mock_joke = Mock()
    mock_joke.key = joke_id
    mock_joke.setup_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_setup.png"
    mock_joke.punchline_image_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024/joke1_punchline.png"

    mock_firestore.get_punny_jokes.return_value = [mock_joke]

    # Create test images (only setup and punchline, no blocker overlay)
    setup_img = Image.new('RGB', (1024, 1024), color='red')
    punchline_img = Image.new('RGB', (1024, 1024), color='blue')
    mock_cloud_storage.download_image_from_gcs.side_effect = [
      setup_img, punchline_img
    ]

    result = image_operations.create_joke_grid_image_3x2(
      joke_ids=[joke_id], block_last_panel=False)

    self.assertEqual(result.size, (1000, 500))  # 1 joke = 1000x500
    self.assertEqual(result.mode, 'RGB')

    # Verify only joke images were downloaded, no blocker overlay
    self.assertEqual(mock_cloud_storage.download_image_from_gcs.call_count, 2)

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_pinterest_pin_image_blocker_overlay_positioning_logic(
      self, mock_cloud_storage, mock_firestore):
    """Test blocker overlay positioning logic for different numbers of jokes."""
    # Test with 1 joke
    mock_joke = Mock()
    mock_joke.key = "joke1"
    mock_joke.setup_image_url = "https://images.quillsstorybook.com/joke1_setup.png"
    mock_joke.punchline_image_url = "https://images.quillsstorybook.com/joke1_punchline.png"

    mock_firestore.get_punny_jokes.return_value = [mock_joke]

    setup_img = Image.new('RGB', (1024, 1024), color='red')
    punchline_img = Image.new('RGB', (1024, 1024), color='blue')
    blocker_img = Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128))

    mock_cloud_storage.download_image_from_gcs.side_effect = [
      setup_img, punchline_img, blocker_img
    ]

    result = image_operations.create_joke_grid_image_3x2(joke_ids=["joke1"])

    # For 1 joke: last_row_y = (1 - 1) * 500 = 0
    # Overlay should be at (425, 0 - 75) = (425, -75)
    # But since we can't have negative coordinates in actual paste, let's verify canvas
    self.assertEqual(result.size, (1000, 500))
    self.assertEqual(result.mode, 'RGB')

    # Test with 2 jokes
    mock_jokes = []
    for i in range(2):
      mock_joke = Mock()
      mock_joke.key = f"joke{i+1}"
      mock_joke.setup_image_url = f"https://images.quillsstorybook.com/joke{i+1}_setup.png"
      mock_joke.punchline_image_url = f"https://images.quillsstorybook.com/joke{i+1}_punchline.png"
      mock_jokes.append(mock_joke)

    mock_firestore.get_punny_jokes.return_value = mock_jokes

    test_images_2 = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
      Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128)),
    ]
    mock_cloud_storage.download_image_from_gcs.side_effect = test_images_2

    result_2 = image_operations.create_joke_grid_image_3x2(
      joke_ids=["joke1", "joke2"])

    # For 2 jokes: last_row_y = (2 - 1) * 500 = 500
    # Overlay should be at (425, 500 - 75) = (425, 425)
    # Overlay extends from (425, 425) to (1025, 1025)
    self.assertEqual(result_2.size, (1000, 1000))  # 2 jokes = 1000x(2*500)
    self.assertEqual(result_2.mode, 'RGB')

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  @patch('common.image_operations._compute_joke_grid_divider_color')
  def test_create_pinterest_pin_image_draws_dividers(
    self,
    mock_compute_divider_color,
    mock_cloud_storage,
    mock_firestore,
  ):
    mock_jokes = []
    for i in range(2):
      mock_joke = Mock()
      mock_joke.key = f"joke{i+1}"
      mock_joke.setup_image_url = f"https://images.quillsstorybook.com/joke{i+1}_setup.png"
      mock_joke.punchline_image_url = f"https://images.quillsstorybook.com/joke{i+1}_punchline.png"
      mock_jokes.append(mock_joke)

    mock_firestore.get_punny_jokes.return_value = mock_jokes

    mock_cloud_storage.download_image_from_gcs.side_effect = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
    ]

    divider_color = (10, 20, 30)
    mock_compute_divider_color.return_value = divider_color

    result = image_operations.create_joke_grid_image_3x2(
      joke_ids=["joke1", "joke2"],
      block_last_panel=False,
    )

    self.assertEqual(result.getpixel((10, 499)), divider_color)
    self.assertEqual(result.getpixel((10, 500)), divider_color)
    self.assertEqual(result.getpixel((510, 499)), divider_color)
    self.assertEqual(result.getpixel((510, 500)), divider_color)

  @patch('common.image_operations.firestore')
  @patch('common.image_operations.cloud_storage')
  def test_create_joke_grid_3x2_uses_last_three_jokes(self, mock_cloud_storage,
                                                      mock_firestore):
    """create_joke_grid_image_3x2 should use only the last 3 jokes when more are provided."""
    # Create 5 mock jokes
    joke_ids = ["joke1", "joke2", "joke3", "joke4", "joke5"]
    mock_jokes = []
    for joke_id in joke_ids:
      mock_joke = Mock()
      mock_joke.key = joke_id
      mock_joke.setup_image_url = f"https://images.quillsstorybook.com/{joke_id}_setup.png"
      mock_joke.punchline_image_url = f"https://images.quillsstorybook.com/{joke_id}_punchline.png"
      mock_jokes.append(mock_joke)

    mock_firestore.get_punny_jokes.return_value = mock_jokes

    # Create test images
    test_images = [
      Image.new('RGB', (1024, 1024), color='red'),
      Image.new('RGB', (1024, 1024), color='blue'),
      Image.new('RGB', (1024, 1024), color='green'),
      Image.new('RGB', (1024, 1024), color='yellow'),
      Image.new('RGB', (1024, 1024), color='purple'),
      Image.new('RGB', (1024, 1024), color='orange'),
      Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 128)),  # Blocker overlay
    ]
    mock_cloud_storage.download_image_from_gcs.side_effect = test_images

    result = image_operations.create_joke_grid_image_3x2(joke_ids=joke_ids)

    # Verify that only the last 3 jokes were fetched
    mock_firestore.get_punny_jokes.assert_called_once_with(
      ["joke3", "joke4", "joke5"])

    # Verify the result dimensions (3 jokes = 1000x1500)
    self.assertEqual(result.size, (1000, 1500))
    self.assertEqual(result.mode, 'RGB')

    # Verify that 6 joke images + 1 blocker overlay were downloaded
    self.assertEqual(mock_cloud_storage.download_image_from_gcs.call_count, 7)


class PinterestDividerColorTest(unittest.TestCase):
  """Tests for the Pinterest divider color sampling helper."""

  def _relative_luminance(self, rgb):

    def _to_linear(value):
      value /= 255.0
      if value <= 0.04045:
        return value / 12.92
      return ((value + 0.055) / 1.055)**2.4

    r = _to_linear(rgb[0])
    g = _to_linear(rgb[1])
    b = _to_linear(rgb[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

  def _contrast_ratio(self, rgb_a, rgb_b):
    lum_a = self._relative_luminance(rgb_a)
    lum_b = self._relative_luminance(rgb_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)

  def test_compute_pinterest_pin_divider_color_lightens_dark_source(self):
    canvas = Image.new('RGB', (1000, 1000), (10, 10, 10))
    divider_color = image_operations._compute_joke_grid_divider_color(
      canvas,
      2,
    )

    self.assertIsNotNone(divider_color)
    self.assertGreater(
      self._relative_luminance(divider_color),
      self._relative_luminance((10, 10, 10)),
    )
    self.assertAlmostEqual(
      self._contrast_ratio(divider_color, (10, 10, 10)),
      3.0,
      delta=0.2,
    )

  def test_compute_pinterest_pin_divider_color_darkens_light_source(self):
    canvas = Image.new('RGB', (1000, 1000), (240, 240, 240))
    divider_color = image_operations._compute_joke_grid_divider_color(
      canvas,
      2,
    )

    self.assertIsNotNone(divider_color)
    self.assertLess(
      self._relative_luminance(divider_color),
      self._relative_luminance((240, 240, 240)),
    )
    self.assertAlmostEqual(
      self._contrast_ratio(divider_color, (240, 240, 240)),
      3.0,
      delta=0.2,
    )

  def test_compute_pinterest_pin_divider_color_uses_boundary_samples(self):
    canvas = Image.new('RGB', (1000, 1000), (200, 200, 200))
    top_bottom_y = 499
    bottom_top_y = 500

    for x in range(500):
      canvas.putpixel((x, top_bottom_y), (100, 0, 0))
      canvas.putpixel((x, bottom_top_y), (0, 100, 0))

    for x in range(500, 1000):
      canvas.putpixel((x, top_bottom_y), (0, 0, 100))
      canvas.putpixel((x, bottom_top_y), (100, 100, 0))

    divider_color = image_operations._compute_joke_grid_divider_color(
      canvas,
      2,
    )

    self.assertIsNotNone(divider_color)
    self.assertGreater(divider_color[0], divider_color[2])
    self.assertGreater(divider_color[1], divider_color[2])
    self.assertAlmostEqual(
      self._contrast_ratio(divider_color, (50, 50, 25)),
      3.0,
      delta=0.2,
    )


class CreateJokeGiraffeImageTest(unittest.TestCase):
  """Tests for create_joke_giraffe_image."""

  @patch('common.image_operations.cloud_storage')
  def test_create_joke_giraffe_image_stacks_panels(
    self,
    mock_cloud_storage,
  ):
    jokes = [
      models.PunnyJoke(
        setup_text="Setup 1",
        punchline_text="Punchline 1",
        setup_image_url="setup-1",
        punchline_image_url="punch-1",
      ),
      models.PunnyJoke(
        setup_text="Setup 2",
        punchline_text="Punchline 2",
        setup_image_url="setup-2",
        punchline_image_url="punch-2",
      ),
    ]

    mock_cloud_storage.download_image_from_gcs.side_effect = [
      Image.new('RGB', (1024, 1024), color=(255, 0, 0)),
      Image.new('RGB', (1024, 1024), color=(0, 255, 0)),
      Image.new('RGB', (1024, 1024), color=(0, 0, 255)),
      Image.new('RGB', (1024, 1024), color=(255, 255, 0)),
    ]

    result = image_operations.create_joke_giraffe_image(jokes)

    self.assertEqual(result.size, (1024, 4096))
    self.assertEqual(result.getpixel((512, 512)), (255, 0, 0))
    self.assertEqual(result.getpixel((512, 1536)), (0, 255, 0))
    self.assertEqual(result.getpixel((512, 2560)), (0, 0, 255))
    self.assertEqual(result.getpixel((512, 3584)), (255, 255, 0))
    self.assertEqual(
      mock_cloud_storage.download_image_from_gcs.call_args_list,
      [
        call("setup-1"),
        call("punch-1"),
        call("setup-2"),
        call("punch-2"),
      ],
    )

  def test_create_joke_giraffe_image_empty_list_raises(self):
    with self.assertRaisesRegex(ValueError, "jokes must be a non-empty list"):
      image_operations.create_joke_giraffe_image([])

  def test_create_joke_giraffe_image_missing_urls_raises(self):
    joke = models.PunnyJoke(
      setup_text="Setup",
      punchline_text="Punchline",
      setup_image_url="setup-url",
      punchline_image_url=None,
    )
    with self.assertRaisesRegex(ValueError,
                                "missing setup or punchline image URL"):
      image_operations.create_joke_giraffe_image([joke])


class CreateSingleJokeImages4By5Test(unittest.TestCase):
  """Tests for create_single_joke_images_4by5."""

  @patch('common.image_operations.requests.get')
  @patch('common.image_operations.cloud_storage')
  def test_create_single_joke_images_4by5_centers_square(
    self,
    mock_cloud_storage,
    mock_requests_get,
  ):
    image_operations._get_social_background_4x5.cache_clear()

    # Backgrounds at native 2048x2560, distinct colors.
    setup_bg = Image.new('RGB', (2048, 2560), color=(20, 20, 20))
    punchline_bg = Image.new('RGB', (2048, 2560), color=(30, 30, 30))

    setup_img = Image.new('RGB', (900, 900), color=(200, 0, 0))
    punchline_img = Image.new('RGB', (1100, 1100), color=(0, 0, 200))

    def _download_image_side_effect(gcs_uri: str):
      if gcs_uri == "setup-url":
        return setup_img
      if gcs_uri == "punchline-url":
        return punchline_img
      if gcs_uri == image_operations._SOCIAL_BACKGROUND_4X5_SWIPE_REVEAL_URL:
        return setup_bg
      if gcs_uri == image_operations._SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL:
        return punchline_bg
      raise AssertionError(f"Unexpected download uri: {gcs_uri}")

    mock_cloud_storage.download_image_from_gcs.side_effect = (
      _download_image_side_effect)

    joke = models.PunnyJoke(
      setup_text="Setup",
      punchline_text="Punchline",
      setup_image_url="setup-url",
      punchline_image_url="punchline-url",
    )

    images = image_operations.create_single_joke_images_4by5([joke])
    setup_out, punchline_out = images

    self.assertEqual(setup_out.size, (1024, 1280))
    self.assertEqual(punchline_out.size, (1024, 1280))

    # Expect centered paste: square starts at y=128 and ends at y=1151.
    self.assertEqual(setup_out.getpixel((512, 10)), (20, 20, 20))  # header
    self.assertEqual(setup_out.getpixel((512, 127)), (20, 20, 20))
    self.assertEqual(setup_out.getpixel((512, 128)), (200, 0, 0))
    self.assertEqual(setup_out.getpixel((512, 640)), (200, 0, 0))  # center
    self.assertEqual(setup_out.getpixel((512, 1151)), (200, 0, 0))
    self.assertEqual(setup_out.getpixel((512, 1152)), (20, 20, 20))
    self.assertEqual(setup_out.getpixel((512, 1270)), (20, 20, 20))  # footer

    self.assertEqual(punchline_out.getpixel((512, 10)), (30, 30, 30))
    self.assertEqual(punchline_out.getpixel((512, 640)), (0, 0, 200))

    self.assertEqual(
      mock_cloud_storage.download_image_from_gcs.call_args_list,
      [
        call("setup-url"),
        call("punchline-url"),
        call(image_operations._SOCIAL_BACKGROUND_4X5_SWIPE_REVEAL_URL),
        call(image_operations._SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL),
      ],
    )

  def test_create_single_joke_images_4by5_missing_urls_raises(self):
    joke = models.PunnyJoke(
      setup_text="Setup",
      punchline_text="Punchline",
      setup_image_url=None,
      punchline_image_url="punchline-url",
    )
    with self.assertRaisesRegex(ValueError,
                                "missing setup or punchline image URL"):
      image_operations.create_single_joke_images_4by5([joke])

  @patch('common.image_operations.create_joke_grid_image_square')
  @patch('common.image_operations.cloud_storage')
  def test_create_joke_grid_image_4by5_uses_grid_background(
    self,
    mock_cloud_storage,
    mock_square_builder,
  ):
    image_operations._get_social_background_4x5.cache_clear()

    mock_square_builder.return_value = Image.new('RGB', (1000, 1000), 'red')
    mock_cloud_storage.download_image_from_gcs.return_value = Image.new(
      'RGB',
      (2048, 2560),
      'white',
    )

    result = image_operations.create_joke_grid_image_4by5(jokes=[Mock()])

    self.assertEqual(result.size, (1024, 1280))
    mock_cloud_storage.download_image_from_gcs.assert_called_once_with(
      image_operations._SOCIAL_BACKGROUND_4X5_WEBSITE_MORE_URL)
