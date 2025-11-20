import unittest
from unittest.mock import MagicMock, patch, ANY
from PIL import Image
from io import BytesIO

from services import image_client
from common import models


def _get_dummy_image_bytes():
  """Create a dummy PNG image and return its bytes."""
  pil_image = Image.new('RGB', (10, 10), color='red')
  byte_arr = BytesIO()
  pil_image.save(byte_arr, format='PNG')
  return byte_arr.getvalue()


class ImageClientTest(unittest.TestCase):

  def setUp(self):
    self.imagen1_client = image_client.ImagenClient(
      label="test",
      model=image_client.ImageModel.IMAGEN_1,
      file_name_base="test.png",
    )
    self.imagen4_client = image_client.ImagenClient(
      label="test",
      model=image_client.ImageModel.IMAGEN_4_0_STANDARD,
      file_name_base="test.png",
    )
    self.openai_client = image_client.OpenAiImageClient(
      label="test",
      model=image_client.ImageModel.OPENAI_GPT_IMAGE_1_LOW,
      file_name_base="test.png",
    )
    self.gemini_client = image_client.GeminiImageClient(
      label="test",
      model=image_client.ImageModel.IMAGEN_3_CAPABILITY,
      file_name_base="test.png",
    )

  def test_get_upscale_dimensions_no_outpainting(self):
    """No outpainting should keep canvas and mask aligned with original image."""
    dims = image_client.get_upscale_dimensions(
      original_width=100,
      original_height=80,
      top=0,
      bottom=0,
      left=0,
      right=0,
    )

    self.assertIsInstance(dims, image_client.UpscaleDimensions)
    self.assertEqual(dims.new_canvas_width, 100)
    self.assertEqual(dims.new_canvas_height, 80)
    self.assertEqual(dims.image_x, 0)
    self.assertEqual(dims.image_y, 0)
    self.assertEqual(dims.mask_x, 0)
    self.assertEqual(dims.mask_y, 0)
    self.assertEqual(dims.mask_width, 100)
    self.assertEqual(dims.mask_height, 80)

  def test_get_upscale_dimensions_all_sides(self):
    """Outpainting on all sides should expand canvas and inset mask on each side."""
    dims = image_client.get_upscale_dimensions(
      original_width=100,
      original_height=200,
      top=10,
      bottom=20,
      left=30,
      right=40,
    )

    # Canvas grows by the explicit margins.
    self.assertEqual(dims.new_canvas_width, 100 + 30 + 40)
    self.assertEqual(dims.new_canvas_height, 200 + 10 + 20)

    # Original image is pasted offset by the requested margins.
    self.assertEqual(dims.image_x, 30)
    self.assertEqual(dims.image_y, 10)

    # Horizontal and vertical margins are a fixed fraction of the original size
    # when outpainting.
    expected_h_margin = int(round(100 * image_client.UPSCALE_MARGIN_FRACTION))
    expected_v_margin = int(round(200 * image_client.UPSCALE_MARGIN_FRACTION))

    self.assertEqual(dims.mask_x, 30 + expected_h_margin)
    self.assertEqual(dims.mask_y, 10 + expected_v_margin)
    self.assertEqual(dims.mask_width, max(1, 100 - expected_h_margin * 2))
    self.assertEqual(dims.mask_height, max(1, 200 - expected_v_margin * 2))

  def test_get_upscale_dimensions_horizontal_only(self):
    """Outpainting only horizontally should only inset the mask horizontally."""
    dims = image_client.get_upscale_dimensions(
      original_width=120,
      original_height=60,
      top=0,
      bottom=0,
      left=0,
      right=10,
    )

    expected_margin = int(round(120 * image_client.UPSCALE_MARGIN_FRACTION))

    # Canvas width grows; height stays the same.
    self.assertEqual(dims.new_canvas_width, 120 + 10)
    self.assertEqual(dims.new_canvas_height, 60)

    # Image is pasted at the origin vertically, shifted horizontally.
    self.assertEqual(dims.image_x, 0)
    self.assertEqual(dims.image_y, 0)

    # Vertical mask position and height should match original (no vertical margins).
    self.assertEqual(dims.mask_y, 0)
    self.assertEqual(dims.mask_height, 60)

    # Horizontal mask is inset only on the right side; left edge remains at 0.
    self.assertEqual(dims.mask_x, 0)
    self.assertEqual(dims.mask_width, max(1, 120 - expected_margin))

  def test_get_upscale_dimensions_vertical_only(self):
    """Outpainting only vertically should only inset the mask vertically."""
    dims = image_client.get_upscale_dimensions(
      original_width=50,
      original_height=100,
      top=10,
      bottom=0,
      left=0,
      right=0,
    )

    expected_v_margin = int(round(100 * image_client.UPSCALE_MARGIN_FRACTION))

    # Canvas height grows; width stays the same.
    self.assertEqual(dims.new_canvas_width, 50)
    self.assertEqual(dims.new_canvas_height, 100 + 10)

    # Image is pasted at the origin horizontally, shifted vertically.
    self.assertEqual(dims.image_x, 0)
    self.assertEqual(dims.image_y, 10)

    # Horizontal mask position and width should match original (no horizontal margins).
    self.assertEqual(dims.mask_x, 0)
    self.assertEqual(dims.mask_width, 50)

    # Vertical mask is inset only at the top side.
    self.assertEqual(dims.mask_y, 10 + expected_v_margin)
    self.assertEqual(dims.mask_height, max(1, 100 - expected_v_margin))

  def test_upscale_image_not_implemented(self):
    """Test that calling upscale_image on a client that does not implement it raises a NotImplementedError."""
    with self.assertRaises(NotImplementedError):
      self.openai_client.upscale_image(gcs_uri="gs://test/image.png",
                                       upscale_factor="x2",
                                       mime_type="image/png",
                                       compression_quality=None)

  @patch('services.firestore.create_image')
  @patch('services.image_client._build_generation_metadata')
  @patch('services.image_client.ImagenClient._upscale_image_internal')
  def test_upscale_image_model_validation(self, mock_upscale_internal,
                                          mock_build_metadata,
                                          mock_create_image):
    """Upscale should delegate to _upscale_image_internal for any Imagen model."""
    mock_upscale_internal.return_value = "gs://test/upscaled.png"
    mock_build_metadata.return_value = MagicMock()

    result = self.imagen4_client.upscale_image(gcs_uri="gs://test/image.png",
                                               upscale_factor="x2",
                                               mime_type="image/png",
                                               compression_quality=None)

    mock_upscale_internal.assert_called_once_with("gs://test/image.png",
                                                  upscale_factor="x2",
                                                  mime_type="image/png",
                                                  compression_quality=None)
    self.assertIsInstance(result, models.Image)

  def test_upscale_image_validation(self):
    """Test the validation logic for upscale_image."""
    with self.assertRaisesRegex(
        ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
      self.imagen1_client.upscale_image(upscale_factor="x2",
                                        mime_type="image/png",
                                        compression_quality=None)

    with self.assertRaisesRegex(
        ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
      self.imagen1_client.upscale_image(upscale_factor="x2",
                                        mime_type="image/png",
                                        compression_quality=None,
                                        image=models.Image(),
                                        gcs_uri="gs://test/image.png")

    with self.assertRaisesRegex(ValueError,
                                "The provided image must have a gcs_uri."):
      self.imagen1_client.upscale_image(upscale_factor="x2",
                                        mime_type="image/png",
                                        compression_quality=None,
                                        image=models.Image())

  @patch('services.firestore.create_image')
  @patch('services.image_client.ImagenClient._upscale_image_internal')
  def test_upscale_image_with_gcs_uri(self, mock_upscale_internal,
                                      mock_create_image):
    """Test upscale_image when a gcs_uri is provided."""
    mock_upscale_internal.return_value = "gs://test/upscaled.png"

    result = self.imagen1_client.upscale_image(gcs_uri="gs://test/image.png",
                                               upscale_factor="x2",
                                               mime_type="image/png",
                                               compression_quality=None)

    mock_upscale_internal.assert_called_once_with("gs://test/image.png",
                                                  upscale_factor="x2",
                                                  mime_type="image/png",
                                                  compression_quality=None)
    mock_create_image.assert_called_once_with(ANY)
    self.assertIsInstance(result, models.Image)
    self.assertEqual(result.gcs_uri, "gs://test/image.png")
    self.assertEqual(result.gcs_uri_upscaled, "gs://test/upscaled.png")
    self.assertTrue("width=2048" in result.url_upscaled)
    self.assertEqual(result.generation_metadata.generations[0].token_counts,
                     {"upscale_images": 1})

  @patch('services.firestore.update_image')
  @patch('services.image_client.ImagenClient._upscale_image_internal')
  def test_upscale_image_with_image_object(self, mock_upscale_internal,
                                           mock_update_image):
    """Test upscale_image when an Image object is provided."""
    mock_upscale_internal.return_value = "gs://test/upscaled.png"
    image = models.Image(key="test_key", gcs_uri="gs://test/image.png")

    result = self.imagen1_client.upscale_image(image=image,
                                               upscale_factor="x2",
                                               mime_type="image/png",
                                               compression_quality=None)

    mock_upscale_internal.assert_called_once_with("gs://test/image.png",
                                                  upscale_factor="x2",
                                                  mime_type="image/png",
                                                  compression_quality=None)
    mock_update_image.assert_called_once_with(image)
    self.assertIs(result, image)
    self.assertEqual(result.gcs_uri_upscaled, "gs://test/upscaled.png")
    self.assertTrue("width=2048" in result.url_upscaled)
    self.assertEqual(result.generation_metadata.generations[0].token_counts,
                     {"upscale_images": 1})

  @patch('services.image_client.ImagenClient._create_model_client')
  @patch('services.image_client._get_upscaled_gcs_uri')
  @patch('services.image_client.genai_types.Image.from_file')
  def test_upscale_image_internal_imagen(self, mock_from_file,
                                         mock_get_upscaled_uri,
                                         mock_create_client):
    """Test the ImagenClient._upscale_image_internal method."""
    # Ensure a fresh model client is created for this test.
    image_client._CLIENTS_BY_MODEL.clear()

    mock_model_client = MagicMock()
    mock_models = MagicMock()
    mock_model_client.models = mock_models
    mock_create_client.return_value = mock_model_client

    mock_upscaled_image = MagicMock()
    mock_upscaled_image.image = MagicMock()
    mock_upscaled_image.image.gcs_uri = "gs://test/image_upscale_2048.png"
    mock_models.upscale_image.return_value = MagicMock(
      generated_images=[mock_upscaled_image])

    mock_get_upscaled_uri.return_value = "gs://test/image_upscale_2048.png"

    # pylint: disable=protected-access
    gcs_uri = self.imagen1_client._upscale_image_internal(
      "gs://test/image.png", "x2", "image/jpeg", 90)

    mock_from_file.assert_called_once_with(location="gs://test/image.png")
    mock_models.upscale_image.assert_called_once()
    mock_get_upscaled_uri.assert_called_once_with("gs://test/image.png", "x2")
    self.assertEqual(gcs_uri, "gs://test/image_upscale_2048.png")

  @patch('services.image_client.ImagenClient._create_model_client')
  def test_outpaint_image_internal_imagen(
    self,
    mock_create_client,
  ):
    """Test the ImagenClient._outpaint_image_internal method using edit_image."""
    # Ensure a fresh model client is created.
    image_client._CLIENTS_BY_MODEL.clear()

    # Mock the model client returned by _create_model_client.
    mock_model_client = MagicMock()
    mock_models = MagicMock()
    mock_model_client.models = mock_models
    mock_create_client.return_value = mock_model_client

    # Configure edit_image response to return a generated image with a GCS URI.
    generated_image = MagicMock()
    generated_image.image = MagicMock()
    generated_image.image.gcs_uri = "gs://test/image_outpainted.png"
    response = MagicMock()
    response.generated_images = [generated_image]
    mock_models.edit_image.return_value = response

    # Create a PIL.Image from dummy bytes for testing.
    dummy_image_bytes = _get_dummy_image_bytes()
    pil_image = Image.open(BytesIO(dummy_image_bytes)).convert("RGB")
    output_gcs_uri = "gs://test/image_20240101120000_outpaint.png"

    # Call the internal outpaint method.
    # Using a non-zero margin to exercise mask/canvas logic.
    result_uri = self.imagen1_client._outpaint_image_internal(
      pil_image,
      output_gcs_uri,
      top=2,
      bottom=3,
      left=4,
      right=5,
      prompt="Extend the background",
    )

    # edit_image should be called once on the underlying models client.
    self.assertEqual(mock_models.edit_image.call_count, 1)
    # Verify output_gcs_uri was passed to edit_image.
    call_args = mock_models.edit_image.call_args
    self.assertEqual(call_args[1]["config"].output_gcs_uri, output_gcs_uri)

    # The internal method should return the GCS URI of the generated image.
    self.assertEqual(result_uri, "gs://test/image_outpainted.png")

  def test_outpaint_image_validation(self):
    """Test validation logic for outpaint_image."""
    with self.assertRaisesRegex(
        ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
      self.gemini_client.outpaint_image(top=10)

    with self.assertRaisesRegex(
        ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
      self.gemini_client.outpaint_image(
        top=10,
        image=models.Image(),
        gcs_uri="gs://test/image.png",
      )

    with self.assertRaisesRegex(ValueError,
                                "The provided image must have a gcs_uri."):
      self.gemini_client.outpaint_image(
        top=10,
        image=models.Image(),
      )

    with self.assertRaisesRegex(
        ValueError,
        "At least one of 'top', 'bottom', 'left', or 'right' must be greater than 0.",
    ):
      self.gemini_client.outpaint_image(gcs_uri="gs://test/image.png")

  @patch('services.firestore.create_image')
  @patch('services.cloud_storage.get_final_image_url')
  @patch('services.cloud_storage.download_bytes_from_gcs')
  @patch('services.image_client.GeminiImageClient._outpaint_image_internal')
  def test_outpaint_image_with_gcs_uri(
    self,
    mock_outpaint_internal,
    mock_download_bytes,
    mock_get_final_image_url,
    mock_create_image,
  ):
    """Test outpaint_image when a gcs_uri is provided."""
    # Mock downloading image bytes.
    mock_download_bytes.return_value = _get_dummy_image_bytes()
    mock_outpaint_internal.return_value = "gs://test/outpainted.png"
    mock_get_final_image_url.return_value = "http://example.com/outpainted.png"

    result = self.gemini_client.outpaint_image(
      top=10,
      gcs_uri="gs://test/image.png",
      prompt="Extend the sky",
    )

    # Verify image was downloaded from GCS.
    mock_download_bytes.assert_called_once_with("gs://test/image.png")
    
    # Verify _outpaint_image_internal was called with PIL.Image and output_gcs_uri.
    self.assertEqual(mock_outpaint_internal.call_count, 1)
    call_args = mock_outpaint_internal.call_args
    # First positional arg should be a PIL.Image.
    self.assertIsInstance(call_args[0][0], Image.Image)
    # Second positional arg should be the output_gcs_uri string.
    self.assertIsInstance(call_args[0][1], str)
    self.assertIn("_outpaint", call_args[0][1])
    # Verify other parameters.
    self.assertEqual(call_args[1]["top"], 10)
    self.assertEqual(call_args[1]["bottom"], 0)
    self.assertEqual(call_args[1]["left"], 0)
    self.assertEqual(call_args[1]["right"], 0)
    self.assertEqual(call_args[1]["prompt"], "Extend the sky")
    
    mock_create_image.assert_called_once_with(ANY)
    self.assertIsInstance(result, models.Image)
    self.assertEqual(result.gcs_uri, "gs://test/outpainted.png")
    self.assertEqual(result.url, "http://example.com/outpainted.png")
    self.assertEqual(result.generation_metadata.generations[0].token_counts,
                     {"images": 1})
