import unittest
from unittest.mock import MagicMock, patch, ANY
from PIL import Image
from io import BytesIO

# from google.genai import types  # No longer needed with ImageGenerationModel API
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

  def test_upscale_image_not_implemented(self):
    """Test that calling upscale_image on a client that does not implement it raises a NotImplementedError."""
    with self.assertRaises(NotImplementedError):
      self.openai_client.upscale_image(gcs_uri="gs://test/image.png",
                                       upscale_factor="x2",
                                       mime_type="image/png",
                                       compression_quality=None)

  def test_upscale_image_model_validation(self):
    """Test that upscale_image raises an error if the model is not IMAGEN_1."""
    with self.assertRaisesRegex(
        ValueError,
        "Upscaling is only supported for the imagegeneration@002 model."):
      self.imagen4_client.upscale_image(gcs_uri="gs://test/image.png",
                                        upscale_factor="x2",
                                        mime_type="image/png",
                                        compression_quality=None)

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
  @patch('services.image_client.VertexImage.load_from_file')
  def test_upscale_image_internal_imagen(self, mock_load_from_file,
                                         mock_get_upscaled_uri,
                                         mock_create_client):
    """Test the ImagenClient._upscale_image_internal method."""
    # Ensure a fresh model client is created for this test.
    image_client._CLIENTS_BY_MODEL.clear()

    mock_model_client = MagicMock()
    mock_create_client.return_value = mock_model_client

    mock_upscaled_image = MagicMock()
    mock_upscaled_image._gcs_uri = "gs://test/image_upscale_2048.png"  # pylint: disable=protected-access
    mock_model_client.upscale_image.return_value = mock_upscaled_image

    mock_get_upscaled_uri.return_value = "gs://test/image_upscale_2048.png"

    # pylint: disable=protected-access
    gcs_uri = self.imagen1_client._upscale_image_internal(
      "gs://test/image.png", "x2", "image/jpeg", 90)

    mock_load_from_file.assert_called_once_with(location="gs://test/image.png")
    mock_model_client.upscale_image.assert_called_once_with(
      image=mock_load_from_file.return_value,
      upscale_factor="x2",
      output_gcs_uri="gs://test/image_upscale_2048.png",
      output_mime_type="image/jpeg",
      output_compression_quality=90,
    )
    mock_get_upscaled_uri.assert_called_once_with("gs://test/image.png", "x2")
    self.assertEqual(gcs_uri, "gs://test/image_upscale_2048.png")

  @patch('services.image_client.cloud_storage.download_bytes_from_gcs')
  @patch('services.image_client.cloud_storage.get_image_gcs_uri')
  @patch('services.image_client.VertexImage')
  @patch('services.image_client.ImagenClient._create_model_client')
  def test_outpaint_image_internal_imagen(
    self,
    mock_create_client,
    mock_vertex_image,
    mock_get_image_gcs_uri,
    mock_download_bytes,
  ):
    """Test the ImagenClient._outpaint_image_internal method using edit_image."""
    # Ensure a fresh model client is created.
    image_client._CLIENTS_BY_MODEL.clear()

    # Prepare a dummy 10x10 PNG as the original image.
    mock_download_bytes.return_value = _get_dummy_image_bytes()

    # Mock the model client returned by _create_model_client.
    mock_model_client = MagicMock()
    mock_create_client.return_value = mock_model_client

    # Mock the VertexImage constructor to track base_image and mask instances.
    base_vertex_image = MagicMock(name='base_vertex_image')
    mask_vertex_image = MagicMock(name='mask_vertex_image')
    mock_vertex_image.side_effect = [base_vertex_image, mask_vertex_image]

    # Mock output GCS URI for the edited image.
    mock_get_image_gcs_uri.return_value = "gs://test/outpaint_output.png"

    # Configure edit_image response to return a generated image with a GCS URI.
    generated_image = MagicMock()
    generated_image._gcs_uri = "gs://test/image_outpainted.png"  # pylint: disable=protected-access
    response = MagicMock()
    response.images = [generated_image]
    mock_model_client.edit_image.return_value = response

    # Call the internal outpaint method.
    # Using a non-zero margin to exercise mask/canvas logic.
    result_uri = self.imagen1_client._outpaint_image_internal(
      "gs://test/image.png",
      top=2,
      bottom=3,
      left=4,
      right=5,
      prompt="Extend the background",
    )

    # Original image should be loaded from GCS.
    mock_download_bytes.assert_called_once_with("gs://test/image.png")

    # A new output GCS URI should be requested for the edited image.
    mock_get_image_gcs_uri.assert_called_once_with("test.png", "png")

    # VertexImage should be constructed twice: once for base image, once for mask.
    self.assertEqual(mock_vertex_image.call_count, 2)

    # edit_image should be called with the correct parameters.
    mock_model_client.edit_image.assert_called_once_with(
      prompt="Extend the background",
      base_image=base_vertex_image,
      mask=mask_vertex_image,
      edit_mode="outpainting",
      mask_dilation=0.03,
      output_mime_type="image/png",
      output_gcs_uri="gs://test/outpaint_output.png",
      safety_filter_level="block_few",
      person_generation="allow_adult",
    )

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
  @patch('services.image_client.GeminiImageClient._outpaint_image_internal')
  def test_outpaint_image_with_gcs_uri(
    self,
    mock_outpaint_internal,
    mock_get_final_image_url,
    mock_create_image,
  ):
    """Test outpaint_image when a gcs_uri is provided."""
    mock_outpaint_internal.return_value = "gs://test/outpainted.png"
    mock_get_final_image_url.return_value = "http://example.com/outpainted.png"

    result = self.gemini_client.outpaint_image(
      top=10,
      gcs_uri="gs://test/image.png",
      prompt="Extend the sky",
    )

    mock_outpaint_internal.assert_called_once_with(
      "gs://test/image.png",
      top=10,
      bottom=0,
      left=0,
      right=0,
      prompt="Extend the sky",
    )
    mock_create_image.assert_called_once_with(ANY)
    self.assertIsInstance(result, models.Image)
    self.assertEqual(result.gcs_uri, "gs://test/outpainted.png")
    self.assertEqual(result.url, "http://example.com/outpainted.png")
    self.assertEqual(result.generation_metadata.generations[0].token_counts,
                     {"images": 1})
