"""Unit tests for image_generation module."""

import unittest
from unittest.mock import patch

from common import image_generation, models
from agents import constants


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


class GeneratePunImagesTest(unittest.TestCase):
  """Tests for pun setup/punchline image generation."""

  @patch('common.image_generation.generate_pun_image')
  def test_punchline_includes_style_reference_images(self,
                                                     mock_generate_pun_image):
    """Punchline generation should include the same style refs as setup."""
    # Arrange: return valid images (URLs required by generate_pun_images)
    mock_generate_pun_image.side_effect = [
      models.Image(
        url='http://example.com/setup.png',
        gcs_uri='gs://example/setup.png',
      ),
      models.Image(
        url='http://example.com/punchline.png',
        gcs_uri='gs://example/punchline.png',
      ),
    ]

    # Act
    image_generation.generate_pun_images(
      setup_text='Setup',
      setup_image_description='Setup desc',
      punchline_text='Punchline',
      punchline_image_description='Punchline desc',
      image_quality='low',
    )

    # Assert
    self.assertEqual(mock_generate_pun_image.call_count, 2)

    setup_call = mock_generate_pun_image.call_args_list[0]
    punchline_call = mock_generate_pun_image.call_args_list[1]

    self.assertEqual(
      setup_call.kwargs.get('style_reference_images'),
      constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
    )
    self.assertEqual(
      punchline_call.kwargs.get('style_reference_images'),
      constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
    )


class GeneratePunImageTest(unittest.TestCase):
  """Tests for the generate_pun_image prompt/reference assembly."""

  @patch('common.image_generation.utils.is_emulator', return_value=True)
  @patch('common.image_generation.image_client.ImageClient.generate_image')
  def test_allows_previous_image_and_style_refs(
    self,
    mock_generate_image,
    _mock_is_emulator,
  ):
    """generate_pun_image should accept both previous_image and style refs."""
    # Arrange
    generated = models.Image(
      url='http://example.com/generated.png',
      gcs_uri='gs://example/generated.png',
    )
    mock_generate_image.return_value = generated

    prev = 'gs://example/setup.png'
    style_refs = constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS

    # Act
    image = image_generation.generate_pun_image(
      pun_text='Hello',
      image_description='A test image.',
      image_quality='low',
      previous_image=prev,
      style_reference_images=style_refs,
    )

    # Assert
    self.assertEqual(image.url, generated.url)
    self.assertIn('prior panel image', image.final_prompt)
    self.assertIn('style reference images', image.final_prompt)

    # First ref should be prior panel, followed by the style refs (4)
    args, _kwargs = mock_generate_image.call_args
    reference_images = args[1]
    self.assertEqual(reference_images[0], prev)
    self.assertEqual(reference_images[1:], style_refs)
