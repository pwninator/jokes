"""Tests for pdf_client."""

from io import BytesIO
from unittest import mock

import pytest
from common import models
from PIL import Image
from services import pdf_client


@pytest.fixture
def mock_download_image():
  with mock.patch('services.cloud_storage.download_image_from_gcs') as mock_fn:
    yield mock_fn


def create_test_image(color='red', width=100, height=100):
  img = Image.new('RGB', (width, height), color=color)
  return img


def test_create_pdf_mixed_inputs(mock_download_image):
  # Prepare inputs
  img1 = create_test_image('red')

  img2 = create_test_image('blue')
  img2_bytes = BytesIO()
  img2.save(img2_bytes, format='PNG')
  img2_bytes_val = img2_bytes.getvalue()

  img3 = create_test_image('green')
  img3_uri = 'gs://bucket/green.png'

  img4 = create_test_image('yellow')
  img4_model = models.Image(gcs_uri='gs://bucket/yellow.png')

  # Mock download behavior
  def side_effect(uri):
    if uri == img3_uri:
      return img3
    if uri == img4_model.gcs_uri:
      return img4
    raise ValueError(f"Unexpected URI: {uri}")

  mock_download_image.side_effect = side_effect

  # Run
  pdf_bytes = pdf_client.create_pdf(
    [img1, img2_bytes_val, img3_uri, img4_model])

  # Assert
  assert pdf_bytes.startswith(b'%PDF')
  # Verify mock calls
  assert mock_download_image.call_count == 2
  mock_download_image.assert_any_call(img3_uri)
  mock_download_image.assert_any_call(img4_model.gcs_uri)


def test_create_pdf_resizing(mock_download_image):
  img = create_test_image('red', width=100, height=100)

  # Target dimensions
  target_w, target_h = 200, 300

  # Run
  # Note: img2pdf puts the image into the PDF. We can verify the logic by mocking PIL.Image.resize
  # However, verifying the PDF content dimension is harder without a PDF parser.
  # We will mock Image.resize to ensure it's called correctly.

  with mock.patch('PIL.Image.Image.resize', wraps=img.resize) as mock_resize:
    # Use the mock image object wrapper so we can track calls on the instances?
    # Actually, wrapping the method on the class works if we want to catch all calls.
    # But since we create new images inside create_pdf (e.g. from bytes), it's trickier.
    # The simplest way is to pass a PIL image and mock its resize method,
    # but create_pdf might copy/convert it.

    # Let's rely on the fact that we pass a PIL image directly in this test case.
    # But create_pdf does: if isinstance(image_item, Image.Image): img = image_item
    # Then img.resize(...)

    # So if we mock the resize method on the instance we pass:
    with mock.patch.object(img, 'resize', wraps=img.resize) as mock_resize:
      pdf_bytes = pdf_client.create_pdf([img],
                                        page_width=target_w,
                                        page_height=target_h)

      assert pdf_bytes.startswith(b'%PDF')
      mock_resize.assert_called_once_with((target_w, target_h),
                                          Image.Resampling.LANCZOS)


def test_create_pdf_invalid_input():
  with pytest.raises(ValueError, match="Unsupported image type"):
    pdf_client.create_pdf([123])


def test_create_pdf_model_no_uri():
  img_model = models.Image(gcs_uri=None)
  with pytest.raises(ValueError, match="Image model has no GCS URI"):
    pdf_client.create_pdf([img_model])


def test_create_pdf_download_failure(mock_download_image):
  mock_download_image.side_effect = Exception("Download failed")
  with pytest.raises(Exception, match="Download failed"):
    pdf_client.create_pdf(['gs://bucket/fail.png'])
