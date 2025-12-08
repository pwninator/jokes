"""Unit tests for image_generation module."""

import unittest
from unittest.mock import patch

from common import image_generation, models


class ModifyImageTest(unittest.TestCase):
  """Tests for the modify_image function."""

  @patch('common.image_generation.cloud_storage.download_bytes_from_gcs')
  @patch('common.image_generation.image_client.ImageClient.generate_image')
  def test_modify_image_success(self, mock_generate_image,
                                mock_download_bytes):
    """Test that modify_image successfully modifies an image."""
    # Arrange
    mock_download_bytes.return_value = b'test_image_bytes'

    mock_generated_image = models.Image(
      url='http://new-image.com/test.png',
      gcs_uri='gs://new-image/test.png',
    )
    mock_generate_image.return_value = mock_generated_image

    image = models.Image(
      url='http://example.com/test.png',
      gcs_uri='gs://example/test.png',
    )
    instruction = 'make it better'

    # Act
    new_image = image_generation.modify_image(image, instruction)

    # Assert
    expected_prompt = "make it better Make sure to the exact same artistic style, color palette, background texture, and overall aesthetic as the original image. Make sure the characters, objects, fonts, color palette, etc. are consistent."
    mock_download_bytes.assert_called_once_with('gs://example/test.png')
    mock_generate_image.assert_called_once_with(
      expected_prompt,
      reference_images=[b'test_image_bytes'],
      save_to_firestore=False,
    )
    self.assertEqual(new_image.url, 'http://new-image.com/test.png')
    self.assertEqual(new_image.original_prompt, instruction)
    self.assertEqual(new_image.final_prompt, instruction)
"""Remove obsolete _strip_prompt_preamble tests; prompt assembly no longer strips."""
