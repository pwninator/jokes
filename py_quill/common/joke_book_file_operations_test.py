"""Unit tests for joke_book_file_operations module."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from common import amazon_redirect, joke_book_file_operations, models
from PIL import Image, ImageFont
from services import pdf_client


class AddPageNumberToImageTest(unittest.TestCase):
  """Tests for rendering page numbers onto book pages."""

  def test_setup_page_positions_and_stroke(self):
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 20, 30)
    with patch('common.joke_book_file_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.joke_book_file_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        joke_book_file_operations._add_page_number_to_image(
          image,
          page_number=3,
          total_pages=12,
          is_punchline=False,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )

    mock_get_font.assert_called_once_with(profile.page_number_font_size_px)
    offset = profile.page_number_offset_px
    stroke_width = max(
      1,
      int(
        round(profile.page_number_font_size_px *
              joke_book_file_operations._PAGE_NUMBER_STROKE_RATIO)))
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
                     joke_book_file_operations._PAGE_NUMBER_STROKE_COLOR)

  def test_punchline_page_positions_use_left_margin(self):
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 14, 20)
    with patch('common.joke_book_file_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.joke_book_file_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        joke_book_file_operations._add_page_number_to_image(
          image,
          page_number=1,
          total_pages=5,
          is_punchline=True,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )

    mock_get_font.assert_called_once_with(profile.page_number_font_size_px)
    offset = profile.page_number_offset_px
    stroke_width = max(
      1,
      int(
        round(profile.page_number_font_size_px *
              joke_book_file_operations._PAGE_NUMBER_STROKE_RATIO)))
    text_call = draw_mock.text.call_args
    self.assertEqual(text_call[0][0], (offset, 200 - offset - 20))
    self.assertEqual(text_call[0][1], '1')
    self.assertEqual(text_call[1]['stroke_width'], stroke_width)

  def test_font_size_static_value(self):
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    image = Image.new('RGB', (200, 200), color='grey')
    draw_mock = MagicMock()
    draw_mock.textbbox.return_value = (0, 0, 10, 10)
    with patch('common.joke_book_file_operations.ImageDraw.Draw',
               return_value=draw_mock):
      fake_font = ImageFont.load_default()
      with patch('common.joke_book_file_operations.get_text_font',
                 return_value=fake_font) as mock_get_font:
        joke_book_file_operations._add_page_number_to_image(
          image,
          page_number=1,
          total_pages=99,
          is_punchline=False,
          font_size=profile.page_number_font_size_px,
          offset_from_edge=profile.page_number_offset_px,
        )
        joke_book_file_operations._add_page_number_to_image(
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
        profile.page_number_font_size_px,
      ],
    )


class ExportJokePageFilesTest(unittest.TestCase):
  """Tests for joke-book ZIP/PDF export."""

  def test_enhance_book_export_page_image_uses_default_editor_args(self):
    """Book export enhancement should call enhance_image with default args."""
    page_image = Image.new('RGB', (32, 32), 'red')
    mock_editor = MagicMock()
    mock_editor.enhance_image.return_value = Image.new('RGB', (32, 32), 'blue')

    enhanced_image = joke_book_file_operations._enhance_book_export_page_image(
      page_image,
      editor=mock_editor,
    )

    self.assertIsInstance(enhanced_image, Image.Image)
    mock_editor.enhance_image.assert_called_once()
    self.assertEqual(mock_editor.enhance_image.call_args.kwargs, {})
    self.assertEqual(enhanced_image.mode, 'RGB')

  def test_convert_for_book_export_returns_pre_trim_image_without_trimming(
    self,
  ):
    """Page conversion should leave trimming for the later encode step."""
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    source_image = Image.new('RGB', (32, 32), 'red')
    mock_editor = MagicMock()
    scaled_image = Image.new('RGB', (10, 10), 'white')
    mock_editor.scale_image.return_value = scaled_image

    result = joke_book_file_operations._convert_for_book_export(
      source_image,
      profile=profile,
      image_editor_instance=mock_editor,
    )

    self.assertIs(result, scaled_image)
    mock_editor.trim_edges.assert_not_called()

  @patch('common.joke_book_file_operations._add_page_number_to_image')
  def test_trim_and_add_page_numbers_uses_shared_page_side_logic(
    self,
    mock_add_page_number,
  ):
    """The final pass should trim inner edges and add numbers by page parity."""
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    right_page = joke_book_file_operations.BookPage(
      file_name='setup.jpg',
      image=Image.new(
        'RGB',
        (profile.pre_trim_width_px, profile.pre_trim_height_px),
        'white',
      ),
      page_number=1,
    )
    left_page = joke_book_file_operations.BookPage(
      file_name='punchline.jpg',
      image=Image.new(
        'RGB',
        (profile.pre_trim_width_px, profile.pre_trim_height_px),
        'white',
      ),
      page_number=2,
    )

    joke_book_file_operations._trim_and_add_page_numbers(
      [right_page, left_page],
      profile=profile,
    )

    self.assertEqual(right_page.image.size,
                     (profile.final_width_px, profile.final_height_px))
    self.assertEqual(left_page.image.size,
                     (profile.final_width_px, profile.final_height_px))
    self.assertEqual(mock_add_page_number.call_count, 2)
    self.assertEqual(mock_add_page_number.call_args_list[0].kwargs, {
      'page_number': 1,
      'total_pages': 2,
      'is_punchline': False,
      'font_size': profile.page_number_font_size_px,
      'offset_from_edge': profile.page_number_offset_px,
    })
    self.assertEqual(mock_add_page_number.call_args_list[1].kwargs, {
      'page_number': 2,
      'total_pages': 2,
      'is_punchline': True,
      'font_size': profile.page_number_font_size_px,
      'offset_from_edge': profile.page_number_offset_px,
    })

  def test_book_page_trim_shifts_hyperlink_after_left_trim(self):
    """Trimming left should shift hyperlink coordinates into final page space."""
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    page = joke_book_file_operations.BookPage(
      file_name='about.jpg',
      image=Image.new(
        'RGB',
        (profile.pre_trim_width_px, profile.pre_trim_height_px),
        'white',
      ),
      hyperlink=pdf_client.HyperlinkSpec(
        url='https://example.com/review',
        x1=100,
        y1=200,
        x2=300,
        y2=400,
      ),
    )

    page.trim(
      trim_left=profile.output_bleed_size_px,
      trim_right=0,
    )

    self.assertEqual(
      page.hyperlink,
      pdf_client.HyperlinkSpec(
        url='https://example.com/review',
        x1=100 - profile.output_bleed_size_px,
        y1=200,
        x2=300 - profile.output_bleed_size_px,
        y2=400,
      ),
    )
    self.assertEqual(page.image.size,
                     (profile.final_width_px, profile.final_height_px))

  @patch('common.joke_book_file_operations._create_qr_code_image')
  @patch(
    'common.joke_book_file_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_add_review_qr_to_page_overlays_qr(
    self,
    mock_get_review_url,
    mock_create_qr_code_image,
  ):
    """Review QR overlay should paste the generated QR at the profile location."""
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    base_image = Image.new(
      'RGB',
      (profile.pre_trim_width_px, profile.pre_trim_height_px),
      'white',
    )

    qr_image = Image.new(
      'RGB',
      (profile.qr_size_px, profile.qr_size_px),
      'black',
    )
    mock_get_review_url.return_value = 'https://example.com/review'
    mock_create_qr_code_image.return_value = qr_image

    page = joke_book_file_operations.BookPage(
      file_name='999_about.jpg',
      image=base_image,
    )
    joke_book_file_operations._add_review_qr_to_page(
      page,
      profile=profile,
      associated_book_key='animal-jokes',
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
    self.assertEqual(page.file_name, '999_about.jpg')
    self.assertIsNotNone(page.hyperlink)
    assert page.hyperlink is not None
    self.assertEqual(page.hyperlink.url, 'https://example.com/review')
    self.assertEqual(page.hyperlink.x1, profile.qr_x_px)
    self.assertEqual(page.hyperlink.y1, profile.qr_y_px)
    self.assertEqual(
      page.hyperlink.x2,
      profile.qr_x_px + profile.qr_size_px,
    )
    self.assertGreater(
      page.hyperlink.y2,
      profile.qr_y_px + profile.qr_size_px,
    )
    self.assertEqual(
      page.image.getpixel((profile.qr_x_px + 10, profile.qr_y_px + 10)),
      (0, 0, 0),
    )

  @patch('common.joke_book_file_operations._BookPageTextDrawer')
  @patch('common.joke_book_file_operations._create_qr_code_image')
  @patch(
    'common.joke_book_file_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_add_review_qr_to_page_adds_cta_caption(
    self,
    mock_get_review_url,
    mock_create_qr_code_image,
    mock_text_drawer,
  ):
    profile = joke_book_file_operations._PAPERBACK_EXPORT_PROFILE
    mock_get_review_url.return_value = 'https://example.com/review'
    mock_create_qr_code_image.return_value = Image.new('RGB', (10, 10), 'black')
    text_drawer = mock_text_drawer.return_value
    text_drawer.width = 120
    text_drawer.height = 40

    page = joke_book_file_operations.BookPage(
      file_name='999_about.jpg',
      image=Image.new(
        'RGB',
        (
          profile.pre_trim_width_px,
          profile.pre_trim_height_px,
        ),
        'white',
      ),
    )
    joke_book_file_operations._add_review_qr_to_page(
      page,
      profile=profile,
      associated_book_key='animal-jokes',
    )

    self.assertIsInstance(page.image, Image.Image)
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
      page.hyperlink,
      pdf_client.HyperlinkSpec(
        url='https://example.com/review',
        x1=profile.qr_x_px,
        y1=profile.qr_y_px,
        x2=profile.qr_x_px + profile.qr_size_px,
        y2=profile.qr_y_px + profile.qr_size_px +
        profile.qr_label_margin_top_px + 40,
      ),
    )

  @patch(
    'common.joke_book_file_operations.amazon_redirect.get_amazon_redirect_bridge_url')
  def test_get_about_page_review_bridge_url_uses_book_about_source(
    self,
    mock_get_bridge_url,
  ):
    mock_get_bridge_url.return_value = 'https://example.com/review-bridge'

    result = joke_book_file_operations._get_about_page_review_bridge_url(
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

  @patch('common.joke_book_file_operations._build_book_export_pages')
  @patch('common.joke_book_file_operations.cloud_storage.get_public_url')
  @patch('common.joke_book_file_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.joke_book_file_operations._build_joke_book_export_uris')
  @patch('common.joke_book_file_operations.pdf_client.create_pdf')
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
      joke_book_file_operations.BookPage(
        file_name='001_belongs.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        _image_bytes=b'pb-1',
      ),
      joke_book_file_operations.BookPage(
        file_name='999_about.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        hyperlink=pdf_client.HyperlinkSpec(
          url='https://example.com/paperback-review',
          x1=10,
          y1=20,
          x2=30,
          y2=40,
        ),
        _image_bytes=b'pb-2',
      ),
    ]
    ebook_pages = [
      joke_book_file_operations.BookPage(
        file_name='001_belongs.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        _image_bytes=b'eb-1',
      ),
      joke_book_file_operations.BookPage(
        file_name='999_about.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        hyperlink=pdf_client.HyperlinkSpec(
          url='https://example.com/ebook-review',
          x1=11,
          y1=21,
          x2=31,
          y2=41,
        ),
        _image_bytes=b'eb-2',
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

    result = joke_book_file_operations.export_joke_book_files(book)

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
                     joke_book_file_operations._PAPERBACK_EXPORT_PROFILE)
    self.assertEqual(mock_build_pages.call_args_list[1].kwargs['profile'],
                     joke_book_file_operations._EBOOK_EXPORT_PROFILE)
    self.assertTrue(
      all(
        isinstance(image_item, tuple) and isinstance(image_item[0],
                                                     (bytes, bytearray))
        for image_item in mock_create_pdf.call_args_list[0].args[0]))
    self.assertTrue(
      all(
        isinstance(image_item, tuple) and isinstance(image_item[0],
                                                     (bytes, bytearray))
        for image_item in mock_create_pdf.call_args_list[1].args[0]))
    self.assertEqual(mock_create_pdf.call_args_list[0].kwargs['quality'],
                     joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.jpeg_quality)
    self.assertEqual(mock_create_pdf.call_args_list[1].kwargs['quality'],
                     joke_book_file_operations._EBOOK_EXPORT_PROFILE.jpeg_quality)
    self.assertEqual(mock_create_pdf.call_args_list[0].args[0],
                     [(page.image_bytes, page.hyperlink)
                      for page in paperback_pages])
    self.assertEqual(mock_create_pdf.call_args_list[1].args[0],
                     [(page.image_bytes, page.hyperlink)
                      for page in ebook_pages])

  @patch('common.joke_book_file_operations._build_book_export_pages')
  @patch('common.joke_book_file_operations.cloud_storage.get_public_url')
  @patch('common.joke_book_file_operations.cloud_storage.upload_bytes_to_gcs')
  @patch('common.joke_book_file_operations._build_joke_book_export_uris')
  @patch('common.joke_book_file_operations.pdf_client.create_pdf')
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
      joke_book_file_operations.BookPage(
        file_name='001.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._PAPERBACK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        _image_bytes=b'pb-1',
      ),
    ]
    ebook_pages = [
      joke_book_file_operations.BookPage(
        file_name='001.jpg',
        image=Image.new(
          'RGB',
          (
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_width_px,
            joke_book_file_operations._EBOOK_EXPORT_PROFILE.final_height_px,
          ),
          'white',
        ),
        _image_bytes=b'eb-1',
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
      'https://cdn.example.com/book.zip',
      'https://cdn.example.com/book_paperback.pdf',
      'https://cdn.example.com/book_ebook.pdf',
    ]

    result = joke_book_file_operations.export_joke_book_files(
      book,
      export_zip_paperback=True,
    )

    self.assertEqual(result.zip_url, 'https://cdn.example.com/book.zip')
    self.assertEqual(mock_upload_bytes.call_count, 3)
    zip_upload_args = mock_upload_bytes.call_args_list[2].args
    self.assertEqual(zip_upload_args[1],
                     'gs://snickerdoodle_temp_files/joke_book_pages.zip')
    self.assertEqual(zip_upload_args[2], 'application/zip')


if __name__ == '__main__':
  unittest.main()
