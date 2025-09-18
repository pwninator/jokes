import unittest
from unittest.mock import MagicMock, patch, ANY
from PIL import Image
from io import BytesIO

from services import image_client
from common import models

def _get_dummy_image_bytes():
    """Create a dummy PNG image and return its bytes."""
    pil_image = Image.new('RGB', (10, 10), color = 'red')
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

    def test_upscale_image_not_implemented(self):
        """Test that calling upscale_image on a client that does not implement it raises a NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.openai_client.upscale_image(gcs_uri="gs://test/image.png", new_size=2048)

    def test_upscale_image_model_validation(self):
        """Test that upscale_image raises an error if the model is not IMAGEN_1."""
        with self.assertRaisesRegex(ValueError, "Upscaling is only supported for the imagegeneration@002 model."):
            self.imagen4_client.upscale_image(gcs_uri="gs://test/image.png", new_size=2048)

    def test_upscale_image_validation(self):
        """Test the validation logic for upscale_image."""
        with self.assertRaisesRegex(ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
            self.imagen1_client.upscale_image(new_size=2048)

        with self.assertRaisesRegex(ValueError, "Exactly one of 'image' or 'gcs_uri' must be provided."):
            self.imagen1_client.upscale_image(new_size=2048, image=models.Image(), gcs_uri="gs://test/image.png")

        with self.assertRaisesRegex(ValueError, "The provided image must have a gcs_uri."):
            self.imagen1_client.upscale_image(new_size=2048, image=models.Image())

    @patch('services.firestore.create_image')
    @patch('services.image_client.ImagenClient._upscale_image_internal')
    def test_upscale_image_with_gcs_uri(self, mock_upscale_internal, mock_create_image):
        """Test upscale_image when a gcs_uri is provided."""
        mock_upscale_internal.return_value = "gs://test/upscaled.png"

        result = self.imagen1_client.upscale_image(gcs_uri="gs://test/image.png", new_size=2048)

        mock_upscale_internal.assert_called_once_with("gs://test/image.png", 2048)
        mock_create_image.assert_called_once_with(ANY)
        self.assertIsInstance(result, models.Image)
        self.assertEqual(result.gcs_uri, "gs://test/image.png")
        self.assertEqual(result.gcs_uri_upscaled, "gs://test/upscaled.png")
        self.assertTrue("width=2048" in result.url_upscaled)
        self.assertEqual(result.generation_metadata.generations[0].token_counts, {"upscale_images": 1})

    @patch('services.firestore.update_image')
    @patch('services.image_client.ImagenClient._upscale_image_internal')
    def test_upscale_image_with_image_object(self, mock_upscale_internal, mock_update_image):
        """Test upscale_image when an Image object is provided."""
        mock_upscale_internal.return_value = "gs://test/upscaled.png"
        image = models.Image(key="test_key", gcs_uri="gs://test/image.png")

        result = self.imagen1_client.upscale_image(image=image, new_size=2048)

        mock_upscale_internal.assert_called_once_with("gs://test/image.png", 2048)
        mock_update_image.assert_called_once_with(image)
        self.assertIs(result, image)
        self.assertEqual(result.gcs_uri_upscaled, "gs://test/upscaled.png")
        self.assertTrue("width=2048" in result.url_upscaled)
        self.assertEqual(result.generation_metadata.generations[0].token_counts, {"upscale_images": 1})

    @patch('services.image_client.ImagenClient._create_model_client')
    @patch('services.cloud_storage.upload_bytes_to_gcs')
    @patch('services.image_client._get_upscaled_gcs_uri')
    @patch('PIL.Image.open')
    @patch('vertexai.preview.vision_models.Image.load_from_file')
    def test_upscale_image_internal_imagen(self, mock_load_from_file, mock_pil_open, mock_get_upscaled_uri, mock_upload_bytes, mock_create_client):
        """Test the ImagenClient._upscale_image_internal method."""
        mock_model_client = MagicMock()
        mock_create_client.return_value = mock_model_client

        mock_upscaled_image = MagicMock()
        mock_upscaled_image.load_image_bytes.return_value = _get_dummy_image_bytes()
        mock_model_client.upscale_image.return_value = [mock_upscaled_image]

        mock_get_upscaled_uri.return_value = "gs://test/image_upscale_2048.png"
        mock_upload_bytes.return_value = "gs://test/image_upscale_2048.png"

        gcs_uri = self.imagen1_client._upscale_image_internal("gs://test/image.png", 2048)

        mock_load_from_file.assert_called_once_with("gs://test/image.png")
        mock_model_client.upscale_image.assert_called_once_with(
            image=mock_load_from_file.return_value,
            new_size=2048
        )
        mock_get_upscaled_uri.assert_called_once_with("gs://test/image.png", 2048)
        mock_upload_bytes.assert_called_once_with(_get_dummy_image_bytes(), "gs://test/image_upscale_2048.png", content_type="image/png")
        self.assertEqual(gcs_uri, "gs://test/image_upscale_2048.png")
